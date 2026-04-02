"""Tests for TaxExplanationService — AI guidance layer.

These tests verify:
- Explanations are personalised with visa type and years in US
- Dollar amounts are stripped from LLM output (hallucination guard)
- Gemini list-format responses are normalised to dict
- Template fallback fires on missing or invalid LLM responses
- user_context is correctly injected into the prompt user message

All tests mock chat_json so no real LLM call is made.

Run: pytest backend/tests/test_advisor.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.document import CalculationStep, UserContext, AnalysisPreferences
from app.services.tax_advisor import _add_explanations, _build_user_context_block, _template_explanation


def _make_step(
    step_number: int = 1,
    label: str = "Gross Wages (W-2 Box 1)",
    rule_reference: str = "Form W-2, Box 1",
    output_value: str = "$52,000.00",
    is_flag: bool = False,
) -> CalculationStep:
    return CalculationStep(
        step_number=step_number,
        label=label,
        rule_reference=rule_reference,
        input_value="W-2 Box 1",
        output_value=output_value,
        is_flag=is_flag,
        explanation="",
    )


def _make_user_context(
    visa_type: str = "F-1",
    first_us_entry_date: str = "2022-09-01",
) -> UserContext:
    return UserContext(visa_type=visa_type, first_us_entry_date=first_us_entry_date)


# ---------------------------------------------------------------------------
# Test 1: user context block contains visa type and years
# ---------------------------------------------------------------------------

def test_build_user_context_block_contains_visa_and_years():
    """_build_user_context_block must include visa_type and a computed years_in_us value."""
    ctx = _make_user_context(visa_type="F-1", first_us_entry_date="2022-09-01")
    block = _build_user_context_block(ctx)
    assert "F-1" in block
    assert "years_in_us" in block
    # Entry 2022, current year 2025 → 3 years
    assert "3" in block


def test_build_user_context_block_none_returns_empty():
    """When user_context is None, block must be empty string so prompt is unchanged."""
    assert _build_user_context_block(None) == ""


# ---------------------------------------------------------------------------
# Test 2: dollar amounts in LLM output fall back to template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dollar_amount_in_explanation_triggers_template_fallback():
    """If the LLM sneaks a dollar amount into an explanation, it must be stripped
    and replaced with the template explanation — never surfaced to the user."""
    step = _make_step(step_number=1, rule_reference="Form W-2, Box 1")
    bad_response = {"1": "Your wages are $52,000.00 which is the taxable amount."}

    with patch("app.services.tax_advisor.chat_json", new=AsyncMock(return_value=bad_response)):
        result = await _add_explanations([step])

    assert "$" not in result[0].explanation
    # Must not be empty — template fires
    assert result[0].explanation != ""
    assert "Form W-2, Box 1" in result[0].explanation


# ---------------------------------------------------------------------------
# Test 3: Gemini list-format response is normalised
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_list_format_is_normalised():
    """Gemini returns a list of objects instead of a dict. The normaliser must
    convert it to {step_number: explanation} so the merge works correctly."""
    step = _make_step(step_number=1)
    gemini_response = [{"step_number": 1, "explanation": "This is your gross wage income for the year."}]

    with patch("app.services.tax_advisor.chat_json", new=AsyncMock(return_value=gemini_response)):
        result = await _add_explanations([step])

    assert result[0].explanation == "This is your gross wage income for the year."


# ---------------------------------------------------------------------------
# Test 4: missing step in LLM response falls back to template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_step_number_falls_back_to_template():
    """If the LLM omits a step from its response, that step must get the template
    explanation — never an empty string."""
    step = _make_step(step_number=5, rule_reference="IRC §3121(b)(19)")
    # LLM returns explanation for step 1 only, omits step 5
    incomplete_response = {"1": "Some explanation for step 1."}

    with patch("app.services.tax_advisor.chat_json", new=AsyncMock(return_value=incomplete_response)):
        result = await _add_explanations([step])

    assert result[0].explanation != ""
    assert "IRC §3121(b)(19)" in result[0].explanation


# ---------------------------------------------------------------------------
# Test 5: user_context is injected into the prompt user message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_context_injected_into_prompt():
    """When user_context is provided, the visa type and years must appear in the
    user message sent to the LLM — not just in the system prompt."""
    step = _make_step(step_number=1)
    ctx = _make_user_context(visa_type="J-1", first_us_entry_date="2023-01-15")
    captured_messages = []

    async def mock_chat_json(model, messages, **kwargs):
        captured_messages.extend(messages)
        return {"1": "Explanation for step 1."}

    with patch("app.services.tax_advisor.chat_json", new=mock_chat_json):
        await _add_explanations([step], user_context=ctx)

    # The user message (role=user) must contain the filer context
    user_msg = next(m["content"] for m in captured_messages if m["role"] == "user")
    assert "J-1" in user_msg
    assert "years_in_us" in user_msg
