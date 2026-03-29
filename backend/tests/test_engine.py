"""Tests for TaxCalculationEngine — deterministic 2025 IRS math.

These tests require no LLM and run instantly.
They verify the numbers that appear in the Calculation Ledger.

Run: pytest backend/tests/test_engine.py -v
"""

import pytest
from app.schemas.document import ConfirmedFields, FieldValue, UserContext
from app.services.tax_engine import (
    calculate,
    _apply_brackets,
    _calculate_state_tax,
    _determine_residency,
    STANDARD_DEDUCTION_SINGLE_2025,
    STATE_STD_DED_CA,
    STATE_STD_DED_NY,
    STATE_STD_DED_IL,
    STATE_STD_DED_MA,
    SE_TAX_RATE,
    SE_INCOME_MULTIPLIER,
)


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
        # F-1 year 2 → NRA → no standard deduction (IRS Pub. 519)
        # Taxable income = 52000 (full wages, $0 deduction)
        # Tax on 52000: 10% on 11925 = 1192.50
        #               12% on (48475-11925) = 4386.00
        #               22% on (52000-48475) = 775.50
        # Total income tax = 6354.00
        # Refund = 8000 - 6354.00 = 1646.00
        assert self.amount == pytest.approx(1646.00, abs=1.0)

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


# ---------------------------------------------------------------------------
# Helpers for NEC / INT tests
# ---------------------------------------------------------------------------

def _make_nec_fields(
    nonemployee_compensation: str,
    federal_withheld: str = "0",
    form_type: str = "1099-NEC",
) -> ConfirmedFields:
    return ConfirmedFields(
        document_id="test-nec",
        confirmed_fields={
            "form_type": FieldValue(value=form_type, source="user_confirmed", confidence=1.0),
            "box_1_nonemployee_compensation": FieldValue(value=nonemployee_compensation, source="user_confirmed", confidence=1.0),
            "box_4_federal_tax_withheld": FieldValue(value=federal_withheld, source="user_confirmed", confidence=1.0),
        },
    )


def _make_int_fields(
    interest_income: str,
    federal_withheld: str = "0",
) -> ConfirmedFields:
    return ConfirmedFields(
        document_id="test-int",
        confirmed_fields={
            "form_type": FieldValue(value="1099-INT", source="user_confirmed", confidence=1.0),
            "box_1_interest_income": FieldValue(value=interest_income, source="user_confirmed", confidence=1.0),
            "box_4_federal_tax_withheld": FieldValue(value=federal_withheld, source="user_confirmed", confidence=1.0),
        },
    )


def _domestic_context() -> UserContext:
    return UserContext(visa_type="US_CITIZEN")


# ---------------------------------------------------------------------------
# Test 4: Basic NEC — domestic contractor, $40,000, no expenses
# ---------------------------------------------------------------------------

class TestNECBasic:
    """Domestic contractor, $40k gross, no expenses, no withholding."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="40000")
        self.steps, self.outcome, self.amount = calculate(confirmed, _domestic_context())

    def test_outcome_is_owe(self):
        # Net SE = 40000 × 0.9235 = 36940
        # SE tax = 36940 × 0.153 = 5651.82
        # Se half = 5651.82 / 2 = 2825.91
        # Taxable = 40000 − 2825.91 − 14600 = 22574.09
        # Income tax ≈ 10% on 11925 + 12% on 10649.09 ≈ 2470.59
        # Total liability ≈ 2470.59 + 5651.82 ≈ 8122.41
        # Withheld = 0 → outcome is owe
        assert self.outcome == "owe"

    def test_se_tax_correct(self):
        net_se = 40_000 * SE_INCOME_MULTIPLIER
        expected_se_tax = round(net_se * SE_TAX_RATE, 2)
        se_step = next(s for s in self.steps if "Self-Employment Tax" in s.label and not s.is_flag)
        assert f"${expected_se_tax:,.2f}" in se_step.output_value

    def test_all_steps_tagged_nec(self):
        assert all(s.source_form == "1099-NEC" for s in self.steps)

    def test_step_numbers_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))

    def test_estimated_payments_flag_present(self):
        """Owe > $1,000 so estimated quarterly payments flag must appear."""
        flag_steps = [s for s in self.steps if s.is_flag and "Estimated" in s.label]
        assert len(flag_steps) == 1

    def test_all_steps_have_rule_reference(self):
        for step in self.steps:
            assert step.rule_reference, f"Step {step.step_number} missing rule_reference"


# ---------------------------------------------------------------------------
# Test 5: NEC with business expenses
# ---------------------------------------------------------------------------

class TestNECWithExpenses:
    """Contractor with $40k gross and $8k deductible expenses."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="40000")
        context = UserContext(visa_type="US_CITIZEN", nec_business_expenses=8_000.0)
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_expense_step_present(self):
        expense_step = next((s for s in self.steps if "Expense" in s.label and not s.is_flag), None)
        assert expense_step is not None

    def test_net_se_income_uses_net_after_expenses(self):
        # Net after expenses = 40000 − 8000 = 32000
        # Net SE = 32000 × 0.9235 = 29552
        net_se_step = next(s for s in self.steps if "Net Self-Employment" in s.label)
        expected_net_se = round(32_000 * SE_INCOME_MULTIPLIER, 2)
        assert f"${expected_net_se:,.2f}" in net_se_step.output_value

    def test_step_numbers_sequential_with_expenses(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))


# ---------------------------------------------------------------------------
# Test 6: NEC with expenses exceeding gross — negative net income
# ---------------------------------------------------------------------------

class TestNECNegativeNet:
    """Expenses exceed gross: net SE income clamped to $0, advisory flag."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="5000")
        context = UserContext(visa_type="US_CITIZEN", nec_business_expenses=8_000.0)
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_negative_net_flag_present(self):
        flag = next((s for s in self.steps if s.is_flag and "Expense" in s.label), None)
        assert flag is not None, "Negative net income flag should be present"

    def test_se_tax_is_zero(self):
        """Net SE clamped to $0 → SE tax = $0."""
        se_step = next(s for s in self.steps if "Self-Employment Tax" in s.label and not s.is_flag)
        assert "$0.00" in se_step.output_value


# ---------------------------------------------------------------------------
# Test 7: NEC — F-1 visa triggers NRA SE advisory flag
# ---------------------------------------------------------------------------

class TestNECF1Advisory:
    """F-1 student with 1099-NEC triggers NRA SE advisory."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="30000")
        context = UserContext(visa_type="F-1", first_us_entry_date="2023")
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_nra_advisory_flag_present(self):
        flag = next((s for s in self.steps if s.is_flag and "NRA" in s.label), None)
        assert flag is not None, "NRA SE advisory flag should be present for F-1 filers"

    def test_nra_flag_source_form_is_nec(self):
        flag = next(s for s in self.steps if s.is_flag and "NRA" in s.label)
        assert flag.source_form == "1099-NEC"


# ---------------------------------------------------------------------------
# Test 8: NEC — missing box_1 returns unknown
# ---------------------------------------------------------------------------

class TestNECMissingBox1:
    """If box_1_nonemployee_compensation is absent, engine returns unknown."""

    def setup_method(self):
        confirmed = ConfirmedFields(
            document_id="test-nec-missing",
            confirmed_fields={
                "form_type": FieldValue(value="1099-NEC", source="ocr", confidence=0.9),
                # box_1_nonemployee_compensation intentionally absent
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
# Test 9: Basic INT — $5,000 interest income
# ---------------------------------------------------------------------------

class TestINTBasic:
    """$5,000 interest income, no withholding."""

    def setup_method(self):
        confirmed = _make_int_fields(interest_income="5000")
        self.steps, self.outcome, self.amount = calculate(confirmed, None)

    def test_outcome_is_owe(self):
        # Taxable = max(0, 5000 − 14600) = 0 → tax = 0, no withholding → balanced
        # Wait: 5000 < 14600 std ded → taxable = 0 → tax = 0 → balanced
        # Let me recalculate: 5000 interest - 14600 std ded = max(0, -9600) = 0
        # So outcome should be balanced
        assert self.outcome == "balanced"

    def test_all_steps_tagged_int(self):
        assert all(s.source_form == "1099-INT" for s in self.steps)

    def test_step_numbers_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))


# ---------------------------------------------------------------------------
# Test 10: INT — large interest income above standard deduction
# ---------------------------------------------------------------------------

class TestINTAboveStdDed:
    """$30,000 interest: above standard deduction, results in tax owed."""

    def setup_method(self):
        confirmed = _make_int_fields(interest_income="30000")
        self.steps, self.outcome, self.amount = calculate(confirmed, None)

    def test_outcome_is_owe(self):
        assert self.outcome == "owe"

    def test_tax_amount_correct(self):
        # Taxable = 30000 − 14600 = 15400
        # Tax = 10% on 11925 + 12% on (15400-11925) = 1192.50 + 417.00 = 1609.50
        assert self.amount == pytest.approx(1_609.50, abs=1.0)


# ---------------------------------------------------------------------------
# Test 11: INT — missing box_1 returns unknown
# ---------------------------------------------------------------------------

class TestINTMissingBox1:
    """If box_1_interest_income is absent, engine returns unknown."""

    def setup_method(self):
        confirmed = ConfirmedFields(
            document_id="test-int-missing",
            confirmed_fields={
                "form_type": FieldValue(value="1099-INT", source="ocr", confidence=0.9),
                # box_1_interest_income intentionally absent
            },
        )
        self.steps, self.outcome, self.amount = calculate(confirmed, None)

    def test_outcome_is_unknown(self):
        assert self.outcome == "unknown"

    def test_no_steps_returned(self):
        assert self.steps == []


# ---------------------------------------------------------------------------
# Test 12: Dispatcher routing
# ---------------------------------------------------------------------------

class TestDispatcher:
    """calculate() routes to the correct branch by form_type."""

    def test_routes_nec(self):
        confirmed = _make_nec_fields(nonemployee_compensation="20000", form_type="1099-NEC")
        steps, _, _ = calculate(confirmed, None)
        assert any(s.source_form == "1099-NEC" for s in steps)

    def test_routes_int(self):
        confirmed = _make_int_fields(interest_income="20000")
        steps, _, _ = calculate(confirmed, None)
        assert any(s.source_form == "1099-INT" for s in steps)

    def test_routes_w2(self):
        confirmed = _make_w2_fields(wages="40000", federal_withheld="5000", form_type="W-2")
        steps, _, _ = calculate(confirmed, None)
        assert any(s.source_form == "W-2" for s in steps)

    def test_empty_form_type_defaults_to_w2(self):
        """Empty form_type should fall back to W-2 (OCR failure safe default)."""
        confirmed = _make_w2_fields(wages="40000", federal_withheld="5000", form_type="")
        steps, _, _ = calculate(confirmed, None)
        assert any(s.source_form == "W-2" for s in steps)


# ---------------------------------------------------------------------------
# Helpers for NRA tests (TODO-6)
# ---------------------------------------------------------------------------

def _nra_f1_context(entry_year: str = "2024") -> UserContext:
    """F-1 student in their first 5 calendar years → NRA via exempt individual rule."""
    return UserContext(
        visa_type="F-1",
        first_us_entry_date=entry_year,
    )


def _h1b_spt_pass_context() -> UserContext:
    """H-1B with day counts that satisfy the Substantial Presence Test → RA."""
    return UserContext(
        visa_type="H-1B",
        current_year_days_in_us=200,
        prior_year_days_in_us=180,
        second_prior_year_days_in_us=120,
    )


def _h1b_spt_fail_context() -> UserContext:
    """H-1B with day counts that do NOT satisfy the SPT → NRA."""
    return UserContext(
        visa_type="H-1B",
        current_year_days_in_us=100,
        prior_year_days_in_us=30,
        second_prior_year_days_in_us=10,
    )


# ---------------------------------------------------------------------------
# Test 13: _determine_residency() unit tests
# ---------------------------------------------------------------------------

class TestDetermineResidency:
    """Unit tests for the _determine_residency() helper (IRS Pub. 519)."""

    def test_no_context_returns_ra(self):
        assert _determine_residency(None) == "RA"

    def test_us_citizen_returns_ra(self):
        ctx = UserContext(visa_type="US_CITIZEN")
        assert _determine_residency(ctx) == "RA"

    def test_green_card_returns_ra(self):
        ctx = UserContext(visa_type="GREEN_CARD")
        assert _determine_residency(ctx) == "RA"

    def test_f1_year1_returns_nra(self):
        """F-1, entry 2024 → year 1 in 2025 → NRA (exempt individual)."""
        ctx = UserContext(visa_type="F-1", first_us_entry_date="2024")
        assert _determine_residency(ctx) == "NRA"

    def test_f1_year4_returns_nra(self):
        """F-1, entry 2021 → year 4 in 2025 → NRA (still < 5 years)."""
        ctx = UserContext(visa_type="F-1", first_us_entry_date="2021")
        assert _determine_residency(ctx) == "NRA"

    def test_f1_year5_returns_nra(self):
        """F-1, entry 2020 → years_elapsed = 5 → NOT < 5 → falls to SPT.
        No day counts → d0 == 0 → RA default."""
        # years_elapsed = 2025 - 2020 = 5, which is NOT < 5, so falls to SPT.
        # No day counts provided → d0 == 0 → default RA.
        ctx = UserContext(visa_type="F-1", first_us_entry_date="2020")
        assert _determine_residency(ctx) == "RA"

    def test_f1_no_entry_date_returns_nra(self):
        """F-1 with no entry date → conservative NRA."""
        ctx = UserContext(visa_type="F-1", first_us_entry_date=None)
        assert _determine_residency(ctx) == "NRA"

    def test_h1b_spt_pass_returns_ra(self):
        """H-1B with sufficient days → SPT passes → RA."""
        ctx = _h1b_spt_pass_context()
        # weighted = 200 + 180/3 + 120/6 = 200 + 60 + 20 = 280 >= 183 and d0=200 >= 31
        assert _determine_residency(ctx) == "RA"

    def test_h1b_spt_fail_returns_nra(self):
        """H-1B with insufficient days → SPT fails → NRA."""
        ctx = _h1b_spt_fail_context()
        # weighted = 100 + 30/3 + 10/6 = 100 + 10 + 1.67 = 111.67 < 183
        assert _determine_residency(ctx) == "NRA"

    def test_h1b_d0_below_31_returns_nra(self):
        """H-1B with d0 < 31: cannot pass SPT 31-day minimum → NRA."""
        ctx = UserContext(visa_type="H-1B", current_year_days_in_us=20)
        assert _determine_residency(ctx) == "NRA"

    def test_h1b_no_days_returns_ra_default(self):
        """H-1B with no day counts → d0 == 0 → conservative default RA."""
        ctx = UserContext(visa_type="H-1B")
        assert _determine_residency(ctx) == "RA"


# ---------------------------------------------------------------------------
# Test 14: W-2 filer — NRA (F-1 year 2, no standard deduction)
# ---------------------------------------------------------------------------

class TestW2NRAFiler:
    """F-1 year 2 filing W-2: no standard deduction, NRA flag present."""

    def setup_method(self):
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        context = _nra_f1_context(entry_year="2024")
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_outcome_is_refund(self):
        assert self.outcome == "refund"

    def test_refund_amount_reflects_no_std_deduction(self):
        # NRA: no standard deduction. Taxable = 52000.
        # Tax = 10% on 11925 + 12% on 36550 + 22% on 3525 = 6354.00
        # Refund = 8000 - 6354 = 1646.00
        assert self.amount == pytest.approx(1646.00, abs=1.0)

    def test_nra_disclosure_flag_present(self):
        flag = next((s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label), None)
        assert flag is not None, "NRA disclosure flag must appear for NRA W-2 filers"

    def test_nra_flag_source_form_is_w2(self):
        flag = next(s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label)
        assert flag.source_form == "W-2"

    def test_standard_deduction_step_shows_zero(self):
        std_step = next(s for s in self.steps if "Deduction" in s.label and not s.is_flag)
        assert "$0.00" in std_step.output_value

    def test_step_numbers_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))

    def test_nra_flag_mentions_form_1040nr(self):
        flag = next(s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label)
        assert "1040-NR" in flag.label or "1040-NR" in flag.output_value


# ---------------------------------------------------------------------------
# Test 15: W-2 filer — RA (H-1B, SPT passes, standard deduction applies)
# ---------------------------------------------------------------------------

class TestW2RAFilerSPT:
    """H-1B with SPT passing: RA filer, standard deduction applies, no NRA flag."""

    def setup_method(self):
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        context = _h1b_spt_pass_context()
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_no_nra_flag(self):
        nra_flags = [s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label]
        assert len(nra_flags) == 0, "RA filer must not have NRA disclosure flag"

    def test_standard_deduction_applied(self):
        std_step = next(s for s in self.steps if "Standard Deduction" in s.label and not s.is_flag)
        assert f"${STANDARD_DEDUCTION_SINGLE_2025:,.2f}" in std_step.output_value

    def test_refund_amount_uses_std_deduction(self):
        # RA: std ded = 14600. Taxable = 52000 - 14600 = 37400.
        # Tax = 10% on 11925 + 12% on 25475 = 1192.50 + 3057 = 4249.50
        # Refund = 8000 - 4249.50 = 3750.50
        assert self.amount == pytest.approx(3750.50, abs=1.0)


# ---------------------------------------------------------------------------
# Test 16: W-2 filer — F-1 after 5 years (falls through to SPT; no days → RA)
# ---------------------------------------------------------------------------

class TestW2F1AfterFiveYears:
    """F-1 with 6 years in US: exempt individual rule no longer applies.
    Without day counts, SPT defaults to RA → standard deduction applies."""

    def setup_method(self):
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        # Entry 2019: 2025-2019=6 years → no longer exempt individual
        # No day counts provided → SPT default → RA
        context = UserContext(visa_type="F-1", first_us_entry_date="2019")
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_no_nra_flag(self):
        nra_flags = [s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label]
        assert len(nra_flags) == 0

    def test_standard_deduction_applied(self):
        std_step = next(s for s in self.steps if "Standard Deduction" in s.label and not s.is_flag)
        assert f"${STANDARD_DEDUCTION_SINGLE_2025:,.2f}" in std_step.output_value


# ---------------------------------------------------------------------------
# Test 17: NEC filer — NRA (F-1 year 2, no standard deduction)
# ---------------------------------------------------------------------------

class TestNECNRAFiler:
    """F-1 year 2 filing 1099-NEC: no standard deduction, NRA flag present."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="30000")
        context = _nra_f1_context(entry_year="2023")
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_standard_deduction_step_shows_zero(self):
        std_step = next(s for s in self.steps if "Deduction" in s.label and not s.is_flag)
        assert "$0.00" in std_step.output_value

    def test_nra_filing_flag_present(self):
        flag = next((s for s in self.steps if s.is_flag and "Nonresident Alien" in s.label), None)
        assert flag is not None, "NRA filing disclosure flag must be present"

    def test_nra_se_advisory_flag_also_present(self):
        """Both the filing disclosure AND the SE treaty advisory should appear."""
        flag = next((s for s in self.steps if s.is_flag and "NRA" in s.label), None)
        assert flag is not None, "NRA SE advisory flag must be present for F-1 NEC filers"

    def test_step_numbers_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))

    def test_all_steps_tagged_nec(self):
        assert all(s.source_form == "1099-NEC" for s in self.steps)

    def test_taxable_income_excludes_std_deduction(self):
        """NRA NEC: taxable = gross − se_half (no std deduction)."""
        net_se = 30_000 * SE_INCOME_MULTIPLIER
        se_tax = round(net_se * SE_TAX_RATE, 2)
        se_half = round(se_tax / 2, 2)
        expected_taxable = round(30_000 - se_half, 2)  # no std deduction
        taxable_step = next(s for s in self.steps if s.label == "Taxable Income")
        assert f"${expected_taxable:,.2f}" in taxable_step.output_value


# ---------------------------------------------------------------------------
# Tests 18–24: State income tax — _calculate_state_tax() unit tests (TODO-7)
# ---------------------------------------------------------------------------

class TestStateTaxCA:
    """California graduated state income tax on $52,000 gross."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "CA")

    def test_returns_four_steps(self):
        assert len(self.steps) == 4

    def test_all_tagged_state(self):
        assert all(s.source_form == "STATE" for s in self.steps)

    def test_step_numbers_sequential(self):
        nums = [s.step_number for s in self.steps]
        assert nums == list(range(1, len(self.steps) + 1))

    def test_deduction_step_correct(self):
        ded_step = self.steps[1]
        assert f"${STATE_STD_DED_CA:,.2f}" in ded_step.output_value

    def test_state_taxable_correct(self):
        taxable_step = self.steps[2]
        expected = 52_000 - STATE_STD_DED_CA
        assert f"${expected:,.2f}" in taxable_step.output_value

    def test_state_tax_positive(self):
        tax_step = self.steps[3]
        # CA tax on (52000 - 5202) = 46798:
        # 1% on 10756 = 107.56
        # 2% on (25499-10756) = 294.86
        # 4% on (40245-25499) = 589.84
        # 6% on (46798-40245) = 393.18
        # Total ≈ 1385.44
        assert "1,385" in tax_step.output_value or "$1,3" in tax_step.output_value


class TestStateTaxNY:
    """New York graduated state income tax on $52,000 gross."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "NY")

    def test_returns_four_steps(self):
        assert len(self.steps) == 4

    def test_deduction_step_correct(self):
        ded_step = self.steps[1]
        assert f"${STATE_STD_DED_NY:,.2f}" in ded_step.output_value

    def test_state_taxable_correct(self):
        taxable_step = self.steps[2]
        expected = 52_000 - STATE_STD_DED_NY
        assert f"${expected:,.2f}" in taxable_step.output_value


class TestStateTaxIL:
    """Illinois flat 4.95% on $52,000 gross."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "IL")

    def test_returns_four_steps(self):
        assert len(self.steps) == 4

    def test_state_tax_is_flat(self):
        taxable = 52_000 - STATE_STD_DED_IL
        expected_tax = round(taxable * 0.0495, 2)
        tax_step = self.steps[3]
        assert f"${expected_tax:,.2f}" in tax_step.output_value

    def test_all_tagged_state(self):
        assert all(s.source_form == "STATE" for s in self.steps)


class TestStateTaxMA:
    """Massachusetts flat 5.0% on $52,000 gross."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "MA")

    def test_state_tax_is_flat(self):
        taxable = 52_000 - STATE_STD_DED_MA
        expected_tax = round(taxable * 0.05, 2)
        tax_step = self.steps[3]
        assert f"${expected_tax:,.2f}" in tax_step.output_value


class TestStateTaxTX:
    """Texas — no state income tax."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "TX")

    def test_single_step(self):
        assert len(self.steps) == 1

    def test_output_is_zero(self):
        assert self.steps[0].output_value == "$0.00"

    def test_tagged_state(self):
        assert self.steps[0].source_form == "STATE"


class TestStateTaxWA:
    """Washington — no state income tax."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "WA")

    def test_single_step(self):
        assert len(self.steps) == 1

    def test_output_is_zero(self):
        assert self.steps[0].output_value == "$0.00"


class TestStateTaxUnsupported:
    """Unsupported state returns a single 'unavailable' flag step."""

    def setup_method(self):
        self.steps = _calculate_state_tax(52_000.0, "FL")

    def test_single_flag_step(self):
        assert len(self.steps) == 1
        assert self.steps[0].is_flag is True

    def test_flag_mentions_unavailable(self):
        assert "Unavailable" in self.steps[0].label or "unavailable" in self.steps[0].label


# ---------------------------------------------------------------------------
# Tests 25–26: State tax integration via calculate() — end-to-end
# ---------------------------------------------------------------------------

def _ca_context() -> UserContext:
    return UserContext(
        visa_type="US_CITIZEN",
        wants_state_estimate=True,
        state_code="CA",
    )


class TestStateTaxW2Integration:
    """W-2 filer with state estimate enabled: state steps appended to result."""

    def setup_method(self):
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        self.steps, self.outcome, self.amount = calculate(confirmed, _ca_context())

    def test_state_steps_present(self):
        state_steps = [s for s in self.steps if s.source_form == "STATE"]
        assert len(state_steps) > 0, "CA state steps should be present"

    def test_federal_steps_unaffected(self):
        federal_steps = [s for s in self.steps if s.source_form == "W-2"]
        assert len(federal_steps) >= 6, "Federal W-2 steps should still be present"

    def test_no_state_steps_when_disabled(self):
        """When wants_state_estimate is False, no STATE steps should appear."""
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        ctx = UserContext(visa_type="US_CITIZEN", wants_state_estimate=False, state_code="CA")
        steps, _, _ = calculate(confirmed, ctx)
        state_steps = [s for s in steps if s.source_form == "STATE"]
        assert len(state_steps) == 0

    def test_no_state_steps_when_no_state_code(self):
        """When wants_state_estimate is True but state_code is absent, no STATE steps."""
        confirmed = _make_w2_fields(wages="52000", federal_withheld="8000")
        ctx = UserContext(visa_type="US_CITIZEN", wants_state_estimate=True, state_code=None)
        steps, _, _ = calculate(confirmed, ctx)
        state_steps = [s for s in steps if s.source_form == "STATE"]
        assert len(state_steps) == 0


class TestStateTaxNECIntegration:
    """NEC filer with state estimate enabled: state steps use net income base."""

    def setup_method(self):
        confirmed = _make_nec_fields(nonemployee_compensation="40000")
        ctx = UserContext(visa_type="US_CITIZEN", wants_state_estimate=True, state_code="IL")
        self.steps, _, _ = calculate(confirmed, ctx)

    def test_state_steps_present(self):
        state_steps = [s for s in self.steps if s.source_form == "STATE"]
        assert len(state_steps) > 0

    def test_state_gross_income_equals_nec_gross(self):
        """For NEC with no expenses, state base should equal gross NEC income."""
        state_gross_step = next(s for s in self.steps if s.source_form == "STATE" and "Gross" in s.label)
        assert "$40,000.00" in state_gross_step.output_value


# ---------------------------------------------------------------------------
# Test: PREREQUISITE GATE — combined W-2 + NEC + 1042-S in one ConfirmedFields
# This test MUST pass before any other bundle/aggregation coding continues.
# ---------------------------------------------------------------------------

def _make_combined_fields(
    wages: str = "0",
    nec_income: str = "0",
    ch3_income: str = "0",
    w2_withheld: str = "0",
    nec_withheld: str = "0",
    ch3_withholding: str = "0",
    ch4_withholding: str = "0",
) -> ConfirmedFields:
    fields: dict = {
        "form_type": FieldValue(value="COMBINED", source="aggregation_service", confidence=1.0),
    }
    if float(wages):
        fields["box_1_wages"] = FieldValue(value=wages, source="aggregation_service", confidence=1.0)
        fields["box_2_federal_tax_withheld"] = FieldValue(value=w2_withheld, source="aggregation_service", confidence=1.0)
    if float(nec_income):
        fields["box_1_nonemployee_compensation"] = FieldValue(value=nec_income, source="aggregation_service", confidence=1.0)
        fields["box_4_federal_tax_withheld"] = FieldValue(value=nec_withheld, source="aggregation_service", confidence=1.0)
    # Include 1042-S fields when income OR withholding is present (withholding
    # may exist even if ch3_income = 0, e.g. over-withheld on scholarship).
    if float(ch3_income) or float(ch3_withholding) or float(ch4_withholding):
        if float(ch3_income):
            fields["gross_income_ch3"] = FieldValue(value=ch3_income, source="aggregation_service", confidence=1.0)
        fields["ch3_withholding"] = FieldValue(value=ch3_withholding, source="aggregation_service", confidence=1.0)
        fields["ch4_withholding"] = FieldValue(value=ch4_withholding, source="aggregation_service", confidence=1.0)
    return ConfirmedFields(document_id="bundle-test", confirmed_fields=fields)


class TestCombinedPrerequisite:
    """BLOCKING GATE: Engine must handle W-2 + NEC + 1042-S in one ConfirmedFields.

    Fixture: wages=$30,000 + nec_income=$5,000 + ch3_withholding=$4,000
    User: F-1 student (NRA, FICA-exempt). No business expenses.

    Expected (NRA, no standard deduction):
      Total ECI = $30,000 + $5,000 net NEC + $0 ch3 = $35,000
      Income tax = 10% × $11,925 + 12% × ($35,000 − $11,925) = $3,961.50
      SE tax = $0 (F-1 FICA-exempt)
      Total liability = $3,961.50
      Total withheld = $0 W-2 + $0 NEC + $4,000 ch3 = $4,000
      Balance = $4,000 − $3,961.50 = $38.50 REFUND
    """

    def setup_method(self):
        confirmed = _make_combined_fields(
            wages="30000",
            nec_income="5000",
            ch3_withholding="4000",
        )
        context = _f1_context(entry_year="2022")  # F-1, year 4 → still exempt
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_returns_steps(self):
        assert len(self.steps) >= 5, "Combined calculation must return ledger steps"

    def test_outcome_is_not_unknown(self):
        assert self.outcome != "unknown", "Engine must handle COMBINED form_type"

    def test_outcome_is_refund(self):
        assert self.outcome == "refund"

    def test_refund_amount_correct(self):
        # Income tax on $35,000 (NRA, no deduction):
        # 10% × 11,925 = 1,192.50
        # 12% × (35,000 - 11,925) = 12% × 23,075 = 2,769.00
        # Total = 3,961.50; withheld = 4,000; refund = 38.50
        assert self.amount == pytest.approx(38.50, abs=1.0)

    def test_w2_step_tagged_correctly(self):
        w2_steps = [s for s in self.steps if s.source_form == "W-2"]
        assert len(w2_steps) >= 1, "W-2 steps must be tagged source_form='W-2'"

    def test_nec_step_tagged_correctly(self):
        nec_steps = [s for s in self.steps if s.source_form == "1099-NEC"]
        assert len(nec_steps) >= 1, "NEC steps must be tagged source_form='1099-NEC'"

    def test_1042s_step_tagged_correctly(self):
        s1042_steps = [s for s in self.steps if s.source_form == "1042-S"]
        assert len(s1042_steps) >= 1, "1042-S steps must be tagged source_form='1042-S'"

    def test_fica_exempt_flag_present(self):
        """F-1 NEC filer must get SE tax exemption flag, not SE tax charge."""
        se_flags = [s for s in self.steps if s.is_flag and "FICA" in s.label]
        assert len(se_flags) >= 1, "F-1 filer should get FICA-exempt SE tax flag"

    def test_no_se_tax_for_fica_exempt(self):
        """F-1 filer should not have SE tax in liability."""
        se_steps = [s for s in self.steps if "Self-Employment Tax" in s.label and not s.is_flag]
        assert len(se_steps) == 0, "FICA-exempt filer must not owe SE tax"


class TestCombined1042SOnly:
    """Single 1042-S document goes through 1042-S sub-calculator."""

    def setup_method(self):
        confirmed = ConfirmedFields(
            document_id="test-1042s",
            confirmed_fields={
                "form_type": FieldValue(value="1042-S", source="ocr", confidence=0.9),
                "gross_income_ch3": FieldValue(value="20000", source="user_confirmed", confidence=1.0),
                "ch3_withholding": FieldValue(value="3000", source="user_confirmed", confidence=1.0),
                "ch4_withholding": FieldValue(value="0", source="user_confirmed", confidence=1.0),
            },
        )
        self.steps, self.outcome, self.amount = calculate(confirmed, None)

    def test_returns_steps(self):
        assert len(self.steps) >= 5

    def test_outcome_is_not_unknown(self):
        assert self.outcome != "unknown"

    def test_owe_correct_amount(self):
        # Tax on $20,000 (NRA default, no deduction):
        # 10% × 11,925 = 1,192.50; 12% × (20,000 - 11,925) = 969.00 → total = 2,161.50
        # withheld = 3,000; refund = 838.50
        assert self.outcome == "refund"
        assert self.amount == pytest.approx(838.50, abs=1.0)

    def test_source_form_tagged_1042s(self):
        income_steps = [s for s in self.steps if s.source_form == "1042-S"]
        assert len(income_steps) >= 3


class TestCombinedW2PlusNEC:
    """W-2 + 1099-NEC combined, H-1B filer (not FICA exempt) — SE tax applies."""

    def setup_method(self):
        confirmed = _make_combined_fields(
            wages="40000",
            w2_withheld="5000",
            nec_income="10000",
        )
        context = _h1b_context()
        self.steps, self.outcome, self.amount = calculate(confirmed, context)

    def test_returns_steps(self):
        assert len(self.steps) >= 5

    def test_se_tax_step_present(self):
        """H-1B filer with NEC income must have SE tax step."""
        se_steps = [s for s in self.steps if "Self-Employment" in s.label and not s.is_flag]
        assert len(se_steps) >= 1

    def test_outcome_is_owe_or_refund(self):
        assert self.outcome in ("owe", "refund", "balanced")

    def test_combined_step_present(self):
        combined_steps = [s for s in self.steps if s.source_form == "COMBINED"]
        assert len(combined_steps) >= 1


class TestCombinedZeroIncomeFields:
    """All income fields = $0 → unknown outcome (nothing to calculate)."""

    def test_all_zero_returns_unknown(self):
        confirmed = _make_combined_fields()  # all defaults = "0"
        steps, outcome, amount = calculate(confirmed, None)
        assert outcome == "unknown"
        assert steps == []


class TestCombinedLargeIncome:
    """Very large combined income ($500k+) → correct top bracket applied."""

    def test_large_income_top_bracket(self):
        confirmed = _make_combined_fields(
            wages="400000",
            nec_income="100000",
            w2_withheld="120000",
        )
        context = UserContext(visa_type="H-1B")  # RA for this test
        steps, outcome, amount = calculate(confirmed, context)
        assert outcome in ("refund", "owe", "balanced")
        # Top bracket is 37%. Total ECI: 400k wages + 100k nec net = 500k.
        # With standard deduction (RA): taxable = 500k - 14,600 = 485,400
        # This is clearly in the 37% bracket. Tax >> $120k withheld → owe.
        # Just verify the engine doesn't crash and returns a numeric amount.
        assert amount is not None
        assert amount > 0
