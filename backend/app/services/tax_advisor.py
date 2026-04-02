"""TaxExplanationService — adds plain-English explanations to CalculationStep rows.

This service makes ONE LLM call for all steps at once (batch approach).
It never produces numbers. All arithmetic lives in tax_engine.py.

If the LLM call fails or returns invalid output, every step silently falls
back to a template explanation — the ledger still renders with correct numbers.

AI output validation:
  - Strip any response containing dollar amounts ($N) and use template.
  - If a step_number is missing from the response, use template for that step.
"""

import re
import json
import httpx
from pathlib import Path
from typing import Optional
from app.schemas.document import AnalysisPreferences, CalculationStep, ConfirmedFields, ValidationOutput, TaxReport, UserContext
from app.services.llm_client import chat_json
from app.services.tax_engine import calculate, compute_report_extras

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Regex to detect dollar amounts the AI should not produce
_DOLLAR_RE = re.compile(r'\$\s*[\d,]+')


def _template_explanation(step: CalculationStep) -> str:
    if step.is_flag:
        return (
            f"This flag is triggered by {step.rule_reference}. "
            "Review the rule to confirm whether it applies to your situation."
        )
    return (
        f"This step applies {step.rule_reference}. "
        "The amount shown is determined by that rule for your filing type."
    )


def _build_user_context_block(user_context: Optional[UserContext]) -> str:
    """Build a plain-text block summarising the filer's context for the LLM prompt."""
    if not user_context:
        return ""
    visa = user_context.visa_type or "unknown"
    years_in_us: Optional[int] = None
    if user_context.first_us_entry_date:
        try:
            from app.services.tax_engine import _years_on_visa
            years_in_us = _years_on_visa(user_context.first_us_entry_date)
        except Exception:
            pass
    income_source = getattr(user_context, "income_source", None) or "unknown"
    lines = [
        "FILER CONTEXT (use this to personalise every explanation):",
        f"  visa_type: {visa}",
        f"  years_in_us: {years_in_us if years_in_us is not None else 'unknown'}",
        f"  income_source: {income_source}",
    ]
    return "\n".join(lines)


async def run_tax_analysis(
    confirmed: ConfirmedFields,
    validation: ValidationOutput,
    user_context: Optional[UserContext] = None,
    preferences: Optional[AnalysisPreferences] = None,
) -> TaxReport:
    """Run the full analysis pipeline:
    1. TaxCalculationEngine computes deterministic steps (no LLM)
    2. TaxExplanationService adds plain-English explanations (one LLM call)
    3. Returns a TaxReport with all steps annotated
    """
    # Step 1: Deterministic calculation
    steps, outcome, amount = calculate(confirmed, user_context)

    if not steps:
        return TaxReport(
            document_id=confirmed.document_id,
            calculation_steps=[],
            estimated_outcome="unknown",
            estimated_amount=None,
            outcome_explanation="Required fields are missing. Please review the extracted fields and try again.",
            validation_results=validation.issues,
        )

    # Step 2: AI batch explanation (graceful fallback on any failure)
    steps = await _add_explanations(steps, preferences, user_context)

    # Build outcome explanation from the last non-flag step
    outcome_step = next((s for s in reversed(steps) if not s.is_flag), None)
    outcome_explanation = outcome_step.explanation if outcome_step and outcome_step.explanation else ""

    # Step 3: Compute treaty exemption, ITIN guidance, Form 8843, and 1040NR fields
    extras = compute_report_extras(confirmed, user_context)

    return TaxReport(
        document_id=confirmed.document_id,
        calculation_steps=steps,
        estimated_outcome=outcome,
        estimated_amount=amount,
        outcome_explanation=outcome_explanation,
        validation_results=validation.issues,
        treaty_exempt_amount=extras["treaty_exempt_amount"],
        treaty_country=extras["treaty_country"],
        treaty_article=extras["treaty_article"],
        needs_itin_guidance=extras["needs_itin_guidance"],
        form_8843_data=extras["form_8843_data"],
        wages=extras["wages"],
        gross_income=extras["gross_income"],
        withholding=extras["withholding"],
    )


async def _add_explanations(
    steps: list[CalculationStep],
    preferences: Optional[AnalysisPreferences] = None,
    user_context: Optional[UserContext] = None,
) -> list[CalculationStep]:
    """Call the LLM once to get explanations for all steps.

    Returns steps with .explanation filled.
    Falls back silently to template text on any error.
    """
    system_prompt = (PROMPTS_DIR / "tax_analysis.txt").read_text()
    steps_payload = [
        {
            "step_number": s.step_number,
            "label": s.label,
            "rule_reference": s.rule_reference,
            "input_value": s.input_value,
            "output_value": s.output_value,
            "is_flag": s.is_flag,
        }
        for s in steps
    ]
    # Prepend filer context so the LLM can personalise every explanation
    ctx_block = _build_user_context_block(user_context)
    steps_json = json.dumps(steps_payload, indent=2)
    user_content = f"{ctx_block}\n\n{steps_json}" if ctx_block else steps_json

    try:
        data = await chat_json(
            preferences.model if preferences else None,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.0,
            provider=preferences.provider if preferences else "ollama",
            api_key=preferences.api_key if preferences else None,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise  # propagate auth failures so review.py can return a clear error message
        # Other HTTP errors (5xx, etc.) — fall back to templates
        return [s.model_copy(update={"explanation": _template_explanation(s)}) for s in steps]
    except Exception:
        # LLM unavailable (Ollama down, timeout, etc.) — fall back to templates
        return [s.model_copy(update={"explanation": _template_explanation(s)}) for s in steps]

    # Normalize: some LLMs (e.g. Gemini) return a list of objects instead of the
    # expected dict keyed by step_number. Convert to dict so the merge below works.
    if isinstance(data, list):
        data = {
            str(item.get("step_number", "")): item.get("explanation", "")
            for item in data
            if isinstance(item, dict)
        }

    # Validate and merge explanations
    result = []
    for step in steps:
        raw_explanation = data.get(str(step.step_number), "")

        # Strip any response that contains dollar amounts the AI should not produce
        if _DOLLAR_RE.search(raw_explanation):
            raw_explanation = ""

        explanation = raw_explanation.strip() or _template_explanation(step)
        result.append(step.model_copy(update={"explanation": explanation}))

    return result
