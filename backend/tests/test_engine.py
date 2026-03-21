"""Tests for TaxCalculationEngine — deterministic 2025 IRS math.

These tests require no LLM and run instantly.
They verify the numbers that appear in the Calculation Ledger.

Run: pytest backend/tests/test_engine.py -v
"""

import pytest
from app.schemas.document import ConfirmedFields, FieldValue, UserContext
from app.services.tax_engine import calculate, _apply_brackets, STANDARD_DEDUCTION_SINGLE_2025


def _make_w2_fields(
    wages: str,
    federal_withheld: str,
    ss_withheld: str = "0",
    medicare_withheld: str = "0",
    form_type: str = "W-2",
) -> ConfirmedFields:
    return ConfirmedFields(
        document_id="test-doc",
        confirmed_fields={
            "form_type": FieldValue(value=form_type, source="user_confirmed", confidence=1.0),
            "box_1_wages": FieldValue(value=wages, source="user_confirmed", confidence=1.0),
            "box_2_federal_tax_withheld": FieldValue(value=federal_withheld, source="user_confirmed", confidence=1.0),
            "box_4_social_security_tax": FieldValue(value=ss_withheld, source="user_confirmed", confidence=1.0),
            "box_6_medicare_tax": FieldValue(value=medicare_withheld, source="user_confirmed", confidence=1.0),
        },
    )


def _f1_context(entry_year: str = "2024") -> UserContext:
    return UserContext(
        visa_type="F-1",
        first_us_entry_date=entry_year,
        current_year_days_in_us=200,
    )


def _h1b_context() -> UserContext:
    return UserContext(
        visa_type="H-1B",
    )


# ---------------------------------------------------------------------------
# Test 1: Demo scenario — F-1 Year 2, $52,000 wages, FICA incorrectly withheld
# ---------------------------------------------------------------------------

class TestDemoScenario:
    """The hackathon demo scenario: F-1 student on OPT, $52,000 wages."""

    def setup_method(self):
        # F-1, entry year 2024 → Year 2 in 2025 → FICA exempt
        confirmed = _make_w2_fields(
            wages="52000",
            federal_withheld="8000",
            ss_withheld="3224",
            medicare_withheld="754",
        )
        context = _f1_context(entry_year="2024")
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_returns_steps(self):
        assert len(self.steps) >= 6

    def test_outcome_is_refund(self):
        assert self.outcome == "refund"

    def test_refund_amount_correct(self):
        # Taxable income = 52000 - 14600 = 37400
        # Tax on 37400: 10% on 11925 = 1192.50, 12% on (37400-11925) = 3057.00
        # Total tax = 1192.50 + 3057.00 = 4249.50
        # Refund = 8000 - 4249.50 = 3750.50
        assert self.amount == pytest.approx(3750.50, abs=1.0)

    def test_fica_ss_flag_present(self):
        flag_steps = [s for s in self.steps if s.is_flag and "§3121" in s.rule_reference]
        assert len(flag_steps) >= 1, "FICA SS exemption flag should be present"

    def test_fica_flag_references_form_843(self):
        flag_step = next(s for s in self.steps if s.is_flag and "§3121" in s.rule_reference)
        assert "Form 843" in flag_step.output_value

    def test_step_numbers_are_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))

    def test_all_steps_have_rule_reference(self):
        for step in self.steps:
            assert step.rule_reference, f"Step {step.step_number} missing rule_reference"


# ---------------------------------------------------------------------------
# Test 2: H-1B filer — not FICA exempt, standard calculation
# ---------------------------------------------------------------------------

class TestH1BNoFicaFlag:
    """H-1B workers are not exempt from FICA — no flag should appear."""

    def setup_method(self):
        confirmed = _make_w2_fields(
            wages="52000",
            federal_withheld="8000",
            ss_withheld="3224",  # withheld, but not refundable for H-1B
            medicare_withheld="754",
        )
        context = _h1b_context()
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_no_fica_flag(self):
        flag_steps = [s for s in self.steps if s.is_flag]
        assert len(flag_steps) == 0, "No FICA flag for H-1B filer"

    def test_outcome_is_refund(self):
        assert self.outcome == "refund"

    def test_six_steps_only(self):
        assert len(self.steps) == 6

    def test_refund_amount_matches_federal_only(self):
        assert self.amount == pytest.approx(3750.50, abs=1.0)


# ---------------------------------------------------------------------------
# Test 3: Missing wages — unknown outcome, no steps
# ---------------------------------------------------------------------------

class TestMissingFields:
    """When box_1_wages is absent, engine should return unknown."""

    def setup_method(self):
        confirmed = ConfirmedFields(
            document_id="test-missing",
            confirmed_fields={
                "form_type": FieldValue(value="W-2", source="ocr", confidence=0.9),
                # box_1_wages intentionally absent
                "box_2_federal_tax_withheld": FieldValue(value="8000", source="ocr", confidence=0.9),
            },
        )
        self.steps, self.outcome, self.amount = calculate(confirmed, None)

    def test_outcome_is_unknown(self):
        assert self.outcome == "unknown"

    def test_no_steps_returned(self):
        assert self.steps == []

    def test_amount_is_none(self):
        assert self.amount is None


# ---------------------------------------------------------------------------
# Unit tests for bracket math
# ---------------------------------------------------------------------------

class TestBracketMath:
    def test_zero_income(self):
        assert _apply_brackets(0) == 0.0

    def test_first_bracket_only(self):
        # $10,000 × 10% = $1,000
        assert _apply_brackets(10_000) == pytest.approx(1_000.0)

    def test_standard_deduction_applied(self):
        # $52,000 wages − $14,600 std deduction = $37,400 taxable
        taxable = 52_000 - STANDARD_DEDUCTION_SINGLE_2025
        tax = _apply_brackets(taxable)
        # 10% on $11,925 = $1,192.50
        # 12% on ($37,400 − $11,925) = $3,057.00
        # Total = $4,249.50
        assert tax == pytest.approx(4_249.50, abs=0.01)
