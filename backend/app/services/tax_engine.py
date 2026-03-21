"""TaxCalculationEngine — deterministic 2025 IRS tax math.

This module does ALL arithmetic. No LLM calls here.
TaxExplanationService (tax_advisor.py) adds plain-English explanations afterward.

Data flow:
    ConfirmedFields + UserContext
          ↓
    TaxCalculationEngine.calculate()    ← this file, pure Python
          ↓
    list[CalculationStep]               ← deterministic, citable numbers
          ↓
    TaxExplanationService.explain()     ← one LLM call in tax_advisor.py
          ↓
    CalculationStep.explanation         ← AI plain-English, no new numbers
"""

from typing import Optional
from app.schemas.document import CalculationStep, ConfirmedFields, UserContext

# ---------------------------------------------------------------------------
# 2025 IRS constants
# Source: IRS Rev. Proc. 2024-40
# Last verified: 2026-03-21
# ---------------------------------------------------------------------------

# Federal income tax brackets — single filer (2025)
# Each tuple: (upper_bound, rate)
# Source: IRS Rev. Proc. 2024-40, Table 1
BRACKETS_SINGLE_2025: list[tuple[float, float]] = [
    (11_925,        0.10),
    (48_475,        0.12),
    (103_350,       0.22),
    (197_300,       0.24),
    (250_525,       0.32),
    (626_350,       0.35),
    (float("inf"),  0.37),
]

STANDARD_DEDUCTION_SINGLE_2025: float = 14_600.0   # Rev. Proc. 2024-40
STANDARD_DEDUCTION_MFJ_2025:    float = 29_200.0
STANDARD_DEDUCTION_HOH_2025:    float = 21_900.0

FICA_SS_RATE:      float = 0.062    # IRC §3101(a)
FICA_SS_WAGE_CAP:  float = 168_600  # SSA 2025 announcement
FICA_MEDICARE:     float = 0.0145   # IRC §3101(b)

# F-1/J-1 students are exempt from FICA for their first 5 calendar years in
# the US on a student/exchange visa.  IRC §3121(b)(19).
FICA_EXEMPT_VISA_TYPES = {"F-1", "J-1", "F1", "J1", "OPT", "CPT"}
FICA_EXEMPT_MAX_YEARS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse a field value string like '$52,000.00' or '52000' to float."""
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _apply_brackets(taxable_income: float) -> float:
    """Compute federal income tax using 2025 single-filer brackets."""
    tax = 0.0
    prev = 0.0
    for upper, rate in BRACKETS_SINGLE_2025:
        if taxable_income <= prev:
            break
        taxable_in_bracket = min(taxable_income, upper) - prev
        tax += taxable_in_bracket * rate
        prev = upper
    return round(tax, 2)


def _is_fica_exempt(visa_type: str, first_entry_year: Optional[str]) -> bool:
    """Return True if the user is exempt from FICA under IRC §3121(b)(19).

    F-1/J-1 students are exempt for their first 5 calendar years in the US.
    We use first_us_entry_date (year) to determine years elapsed.
    If the entry year is unknown, we conservatively return False.
    """
    if visa_type not in FICA_EXEMPT_VISA_TYPES:
        return False
    if not first_entry_year:
        return False
    try:
        entry_year = int(str(first_entry_year)[:4])
        # Tax year 2025 filing
        years_elapsed = 2025 - entry_year
        return years_elapsed < FICA_EXEMPT_MAX_YEARS
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Main calculation function
# ---------------------------------------------------------------------------

def calculate(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax outcome for a W-2 filer (2025, single).

    Returns:
        steps:    list[CalculationStep] — the ledger rows (numbers only, no explanations)
        outcome:  str — "refund" | "owe" | "balanced" | "unknown"
        amount:   Optional[float] — the refund or owed amount

    Explanations are added separately by TaxExplanationService.
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    # Detect form type
    form_type = field_val("form_type") or "W-2"

    if "W-2" not in form_type and "W2" not in form_type:
        # Only W-2 path is implemented deterministically for now.
        # 1099 forms handled by TODO-4.
        return [], "unknown", None

    # --- Step 1: Gross wages ---
    wages_raw = field_val("box_1_wages")
    wages = _parse_float(wages_raw)
    if wages is None:
        return [], "unknown", None

    steps.append(CalculationStep(
        step_number=1,
        label="Gross Wages (W-2 Box 1)",
        rule_reference="Form W-2, Box 1",
        input_value="W-2 Box 1",
        output_value=f"${wages:,.2f}",
    ))

    # --- Step 2: Standard deduction ---
    std_ded = STANDARD_DEDUCTION_SINGLE_2025
    steps.append(CalculationStep(
        step_number=2,
        label="Standard Deduction",
        rule_reference="IRS Rev. Proc. 2024-40 (2025 single filer)",
        input_value="Single filer, no itemization",
        output_value=f"− ${std_ded:,.2f}",
    ))

    # --- Step 3: Taxable income ---
    taxable = max(0.0, wages - std_ded)
    steps.append(CalculationStep(
        step_number=3,
        label="Taxable Income",
        rule_reference="Form 1040, Line 15",
        input_value=f"${wages:,.2f} − ${std_ded:,.2f}",
        output_value=f"${taxable:,.2f}",
    ))

    # --- Step 4: Federal income tax ---
    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=4,
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))

    # --- Step 5: Federal tax withheld ---
    withheld_raw = field_val("box_2_federal_tax_withheld")
    withheld = _parse_float(withheld_raw) or 0.0
    steps.append(CalculationStep(
        step_number=5,
        label="Federal Tax Withheld (W-2 Box 2)",
        rule_reference="Form W-2, Box 2",
        input_value="W-2 Box 2",
        output_value=f"${withheld:,.2f}",
    ))

    # --- Step 6: Estimated federal balance ---
    balance = round(withheld - federal_tax, 2)
    if balance > 0:
        outcome = "refund"
        outcome_label = f"Estimated Refund: ${balance:,.2f}"
    elif balance < 0:
        outcome = "owe"
        outcome_label = f"Estimated Tax Owed: ${abs(balance):,.2f}"
    else:
        outcome = "balanced"
        outcome_label = "Balanced — no refund or amount owed"

    steps.append(CalculationStep(
        step_number=6,
        label="Estimated Federal Balance",
        rule_reference="Form 1040, Line 35a / Line 37",
        input_value=f"${withheld:,.2f} withheld − ${federal_tax:,.2f} liability",
        output_value=outcome_label,
    ))

    # --- FICA exemption check (flag row) ---
    if user_context:
        visa = user_context.visa_type
        entry_year = user_context.first_us_entry_date
        fica_exempt = _is_fica_exempt(visa, entry_year)

        ss_withheld_raw = field_val("box_4_social_security_tax")
        ss_withheld = _parse_float(ss_withheld_raw)

        if fica_exempt and ss_withheld and ss_withheld > 0:
            steps.append(CalculationStep(
                step_number=len(steps) + 1,
                label="⚠ FICA Exemption: Social Security Tax",
                rule_reference="IRC §3121(b)(19) — F-1/J-1 student FICA exemption",
                input_value=f"Box 4 SS withheld: ${ss_withheld:,.2f}",
                output_value=f"${ss_withheld:,.2f} may be recoverable via Form 843",
                is_flag=True,
            ))

        mc_withheld_raw = field_val("box_6_medicare_tax")
        mc_withheld = _parse_float(mc_withheld_raw)

        if fica_exempt and mc_withheld and mc_withheld > 0:
            steps.append(CalculationStep(
                step_number=len(steps) + 1,
                label="⚠ FICA Exemption: Medicare Tax",
                rule_reference="IRC §3101(b)(2) — F-1/J-1 student Medicare exemption",
                input_value=f"Box 6 Medicare withheld: ${mc_withheld:,.2f}",
                output_value=f"${mc_withheld:,.2f} may be recoverable via Form 843",
                is_flag=True,
            ))

    return steps, outcome, abs(balance)
