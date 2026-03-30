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

from typing import Literal, Optional, TypedDict
from app.schemas.document import CalculationStep, ConfirmedFields, UserContext
from app.schemas.form_8843 import Form8843Data
from app.constants.tax_constants import CURRENT_TAX_YEAR, NRA_VISA_TYPES

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

# Visa types that confer Resident Alien (RA) status unconditionally.
# All others require the Substantial Presence Test (SPT).
RA_VISA_TYPES = {"US_CITIZEN", "GREEN_CARD", "RESIDENT_ALIEN"}

# Self-employment tax constants (IRC §1401 / IRC §1402)
SE_TAX_RATE: float = 0.153          # 12.4% SS + 2.9% Medicare
SE_INCOME_MULTIPLIER: float = 0.9235 # net SE income = gross × 0.9235 (IRC §1402(a))

# Estimated tax underpayment threshold (IRC §6654)
ESTIMATED_TAX_THRESHOLD: float = 1_000.0

# Flag step rule_reference constants (used for deduplication in calculate_combined)
_RULE_NRA_SE_TAX     = "nra_se_tax_advisory"
_RULE_NEGATIVE_NET   = "nec_negative_net_income_advisory"
_RULE_EST_PAYMENTS   = "IRC §6654 — estimated tax underpayment"


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


def _apply_brackets(
    taxable_income: float,
    brackets: list[tuple[float, float]] = BRACKETS_SINGLE_2025,
) -> float:
    """Compute income tax using progressive brackets.

    Defaults to 2025 federal single-filer brackets.  Pass a state-specific
    bracket table to compute state income tax.
    """
    tax = 0.0
    prev = 0.0
    for upper, rate in brackets:
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
        years_elapsed = CURRENT_TAX_YEAR - entry_year
        return years_elapsed < FICA_EXEMPT_MAX_YEARS
    except (ValueError, TypeError):
        return False


def _determine_residency(user_context: Optional[UserContext]) -> str:
    """Determine filer residency status for federal tax purposes.

    Returns 'RA' (Resident Alien / citizen) or 'NRA' (Nonresident Alien).
    Defaults to 'RA' when data is insufficient — a conservative choice that
    slightly over-estimates refunds rather than under-estimating.

    Rules applied in priority order:
    1. US_CITIZEN / GREEN_CARD / RESIDENT_ALIEN → always RA.
    2. F-1/J-1/OPT/CPT "exempt individual" rule (IRS Pub. 519 §1):
       - If first_us_entry_date present and years_elapsed < 5 → NRA.
       - If first_us_entry_date absent → conservatively NRA (entry year unknown).
       - If years_elapsed >= 5 → fall through to SPT below.
    3. Substantial Presence Test (26 USC §7701(b)(3)):
       - weighted = d0 + d1/3 + d2/6
       - RA if d0 >= 31 AND weighted >= 183.
       - NRA if d0 > 0 but test not met.
       - Default RA if no day counts provided.

    Source: IRS Publication 519 (2024 edition), Chapter 1.
    """
    if not user_context:
        return "RA"

    visa = (user_context.visa_type or "").strip()

    # Rule 1: permanent residency / citizenship
    if visa in RA_VISA_TYPES:
        return "RA"

    # Rule 2: F-1/J-1/OPT/CPT exempt individual (first 5 calendar years)
    if visa in FICA_EXEMPT_VISA_TYPES:
        entry_str = user_context.first_us_entry_date
        if not entry_str:
            return "NRA"  # no entry date → conservative NRA
        try:
            entry_year = int(str(entry_str)[:4])
            years_elapsed = CURRENT_TAX_YEAR - entry_year
            if years_elapsed < FICA_EXEMPT_MAX_YEARS:
                return "NRA"
            # 5+ years: no longer an exempt individual; fall through to SPT
        except (ValueError, TypeError):
            return "NRA"  # unparseable → conservative NRA

    # Rule 3: Substantial Presence Test (H-1B, B-1/B-2, etc., and F-1 >= 5 yrs)
    d0 = user_context.current_year_days_in_us or 0
    d1 = user_context.prior_year_days_in_us or 0
    d2 = user_context.second_prior_year_days_in_us or 0

    if d0 >= 31:
        weighted = d0 + d1 / 3.0 + d2 / 6.0
        return "RA" if weighted >= 183 else "NRA"
    elif d0 > 0:
        # d0 in [1, 30]: cannot meet the 31-day minimum → NRA
        return "NRA"
    # d0 == 0: no day data at all → default RA (conservative)
    return "RA"


# ---------------------------------------------------------------------------
# Form 8843 helpers
# ---------------------------------------------------------------------------

def _check_8843_eligibility(
    user_context: Optional[UserContext],
) -> tuple[Literal["exempt", "resident_alien_warning"], int]:
    """Check Form 8843 filing eligibility and count exempt years.

    Calls _determine_residency() (the existing SPT implementation) to classify
    the filer, then computes how many calendar years the individual has been
    present as an exempt individual.  That count feeds Form 8843 Line 7.

    Returns:
        status:
          "exempt"                 — still an NRA exempt individual; file 8843 normally
          "resident_alien_warning" — SPT met or 5+ exempt years; may have become RA
                                     (still file Form 8843 for the year, but verify status)
        exempt_years_count:
          Number of calendar years in the US as an exempt individual.
          Capped at FICA_EXEMPT_MAX_YEARS (5) when status is "resident_alien_warning"
          because the filer crossed the threshold during or before the tax year.
    """
    if not user_context:
        return "exempt", 0

    residency = _determine_residency(user_context)

    entry_str = user_context.first_us_entry_date
    if not entry_str:
        if residency == "RA":
            return "resident_alien_warning", 0
        return "exempt", 0

    try:
        entry_year = int(str(entry_str)[:4])
        years_elapsed = CURRENT_TAX_YEAR - entry_year  # calendar years since first entry
    except (ValueError, TypeError):
        if residency == "RA":
            return "resident_alien_warning", 0
        return "exempt", 0

    if residency == "RA":
        # SPT met, or 5+ years as exempt individual → cap at FICA_EXEMPT_MAX_YEARS
        return "resident_alien_warning", min(years_elapsed, FICA_EXEMPT_MAX_YEARS)

    return "exempt", years_elapsed


def _assemble_form_8843_data(
    user_context: UserContext,
    has_income: bool = True,
) -> Form8843Data:
    """Assemble a Form8843Data from UserContext fields.

    This is the FormDataAssembler: extracts all Form 8843-relevant fields from
    the existing UserContext.  Called from compute_report_extras() for NRA visa
    holders on the income path.

    For the zero-income path, Form8843Data is constructed directly from the
    POST /api/forms/8843/generate request body — this function is not used there.

    tin_status defaults to "none" — callers on the income path may override
    with the actual TIN type if it is present in ConfirmedFields.

    exempt_prior_years is computed from first_us_entry_date: the list of
    calendar years from entry_year up to (but not including) tax_year 2025.
    This feeds Form 8843 Line 7 (count of previously claimed exempt years).
    """
    _, exempt_years_count = _check_8843_eligibility(user_context)

    # Build list of prior years the individual was present as exempt individual.
    # Example: entry 2022, tax year 2025 → [2022, 2023, 2024] (3 prior years).
    exempt_prior_years: list[int] = []
    if user_context.first_us_entry_date:
        try:
            entry_year = int(str(user_context.first_us_entry_date)[:4])
            # Years from entry up to (not including) current tax year
            prior_years = list(range(entry_year, CURRENT_TAX_YEAR))
            # Cap at how many were actually exempt (don't go past exempt_years_count)
            exempt_prior_years = prior_years[:exempt_years_count]
        except (ValueError, TypeError):
            pass

    return Form8843Data(
        visa_type=user_context.visa_type or "",
        first_us_entry_date=user_context.first_us_entry_date,
        days_in_us_current_year=user_context.current_year_days_in_us,
        institution_name=user_context.institution_name,
        institution_city=user_context.institution_city,
        institution_state=user_context.institution_state,
        exempt_prior_years=exempt_prior_years,
        has_income=has_income,
        tax_year=CURRENT_TAX_YEAR,
        tin_status="none",  # income-path callers may override from ConfirmedFields
    )


# ---------------------------------------------------------------------------
# 1099-NEC calculation
# ---------------------------------------------------------------------------

def _calculate_nec(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax + SE tax for a 1099-NEC (self-employment) filer (2025).

    Ledger:
      1. Gross NEC income (Box 1)
      2. Business expenses deducted
      3. Net self-employment income
      4. SE tax (15.3% × net × 0.9235)
      5. Deductible half of SE tax
      6. Standard deduction
      7. Taxable income
      8. Federal income tax
      9. Federal withheld (Box 4)
      10. Total liability (income tax + SE tax)
      11. Estimated balance
      [flag] NRA SE tax advisory (if F-1/J-1)
      [flag] Negative net income (if expenses > gross)
      [flag] Estimated tax payments (if owe > $1,000)
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    gross_raw = field_val("box_1_nonemployee_compensation")
    gross = _parse_float(gross_raw)
    if gross is None:
        return [], "unknown", None

    n = 1  # step counter

    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Gross Self-Employment Income (1099-NEC Box 1)",
        rule_reference="Form 1099-NEC, Box 1",
        input_value="1099-NEC Box 1",
        output_value=f"${gross:,.2f}",
    ))
    n += 1

    # Business expenses (from UserContext; 0 if not provided)
    expenses = max(0.0, user_context.nec_business_expenses or 0.0) if user_context else 0.0
    net_gross = gross - expenses

    # Negative net income: clamp to 0, add advisory flag later
    negative_net = net_gross < 0
    net_gross_display = max(0.0, net_gross)

    if expenses > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="Estimated Business Expenses",
            rule_reference="Schedule C (Form 1040), Line 28",
            input_value="Entered by user",
            output_value=f"− ${expenses:,.2f}",
        ))
        n += 1

    # Net SE income (IRC §1402(a): net × 0.9235)
    net_se = net_gross_display * SE_INCOME_MULTIPLIER
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Net Self-Employment Income",
        rule_reference="IRC §1402(a); Schedule SE Line 4a",
        input_value=f"${net_gross_display:,.2f} × 0.9235",
        output_value=f"${net_se:,.2f}",
    ))
    n += 1

    # SE tax
    se_tax = round(net_se * SE_TAX_RATE, 2)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Self-Employment Tax (SS + Medicare)",
        rule_reference="IRC §1401; Schedule SE Line 12",
        input_value=f"${net_se:,.2f} × 15.3%",
        output_value=f"${se_tax:,.2f}",
    ))
    n += 1

    # Deductible half of SE tax
    se_half = round(se_tax / 2, 2)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Deductible Half of SE Tax",
        rule_reference="IRC §164(f); Schedule 1 Line 15",
        input_value=f"${se_tax:,.2f} ÷ 2",
        output_value=f"− ${se_half:,.2f}",
    ))
    n += 1

    # Residency determination: NRA filers cannot claim the standard deduction
    # on Form 1040-NR. Source: IRS Pub. 519, Chapter 4.
    is_nra = _determine_residency(user_context) == "NRA"
    std_ded = 0.0 if is_nra else STANDARD_DEDUCTION_SINGLE_2025
    std_ded_label = (
        "No Standard Deduction (Nonresident Alien — Form 1040-NR)"
        if is_nra
        else "Standard Deduction"
    )
    std_ded_ref = (
        "IRS Pub. 519 Chapter 4; Form 1040-NR instructions"
        if is_nra
        else "IRS Rev. Proc. 2024-40 (2025 single filer)"
    )
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label=std_ded_label,
        rule_reference=std_ded_ref,
        input_value="Single filer, no itemization" if not is_nra else "NRA — no standard deduction",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    # Taxable income
    taxable = max(0.0, gross - (expenses if expenses > 0 else 0) - se_half - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Taxable Income",
        rule_reference="Form 1040, Line 15",
        input_value=f"${gross:,.2f} − expenses − SE deduction − standard deduction",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    # Federal income tax
    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))
    n += 1

    # Total liability
    total_liability = round(federal_tax + se_tax, 2)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Total Tax Liability (Income Tax + SE Tax)",
        rule_reference="Form 1040, Lines 16 + Schedule 2",
        input_value=f"${federal_tax:,.2f} income tax + ${se_tax:,.2f} SE tax",
        output_value=f"${total_liability:,.2f}",
    ))
    n += 1

    # Federal withheld (Box 4; often $0 for contractors)
    withheld_raw = field_val("box_4_federal_tax_withheld")
    withheld = _parse_float(withheld_raw) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="1099-NEC",
        label="Federal Tax Withheld (1099-NEC Box 4)",
        rule_reference="Form 1099-NEC, Box 4",
        input_value="1099-NEC Box 4",
        output_value=f"${withheld:,.2f}",
    ))
    n += 1

    # Balance
    balance = round(withheld - total_liability, 2)
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
        step_number=n, source_form="1099-NEC",
        label="Estimated Federal Balance",
        rule_reference="Form 1040, Line 35a / Line 37",
        input_value=f"${withheld:,.2f} withheld − ${total_liability:,.2f} total liability",
        output_value=outcome_label,
    ))
    n += 1

    # Advisory flags
    if negative_net:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="⚠ Business Expenses Exceed Gross Income",
            rule_reference=_RULE_NEGATIVE_NET,
            input_value=f"Gross: ${gross:,.2f}, Expenses: ${expenses:,.2f}",
            output_value="Net SE income clamped to $0 — you may have a net operating loss",
            is_flag=True,
        ))
        n += 1

    if balance < -ESTIMATED_TAX_THRESHOLD:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="⚠ Estimated Quarterly Tax Payments May Be Required",
            rule_reference=_RULE_EST_PAYMENTS,
            input_value=f"Tax owed: ${abs(balance):,.2f} (exceeds $1,000 threshold)",
            output_value="Due dates: April 15, June 16, September 15, January 15",
            is_flag=True,
        ))
        n += 1

    if is_nra:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="ℹ Filing as Nonresident Alien (Form 1040-NR)",
            rule_reference="IRS Pub. 519; 26 USC §7701(b)",
            input_value=f"Visa: {user_context.visa_type if user_context else 'N/A'}",
            output_value="No standard deduction. Same graduated brackets as Form 1040 for ECI. Consider a US tax treaty.",
            is_flag=True,
        ))
        n += 1

    if user_context and user_context.visa_type in FICA_EXEMPT_VISA_TYPES:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="⚠ NRA Self-Employment Tax Advisory",
            rule_reference=_RULE_NRA_SE_TAX,
            input_value=f"Visa: {user_context.visa_type}",
            output_value="SE tax treatment for F-1/J-1 NRAs may be modified by a US tax treaty",
            is_flag=True,
        ))

    # --- State income tax estimate (optional, gated on user_context) ---
    # State base = net income after expenses (Schedule C net, before SE deduction)
    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_base = max(0.0, gross - (expenses if expenses > 0 else 0))
        state_steps = _calculate_state_tax(state_base, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


# ---------------------------------------------------------------------------
# 1099-INT calculation
# ---------------------------------------------------------------------------

def _calculate_int(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax on interest income (1099-INT Box 1, 2025 single filer).

    No SE tax. Interest income is taxed as ordinary income.
    """
    fields = confirmed.confirmed_fields

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    interest_raw = field_val("box_1_interest_income")
    interest = _parse_float(interest_raw)
    if interest is None:
        return [], "unknown", None

    steps: list[CalculationStep] = []
    n = 1

    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Taxable Interest Income (1099-INT Box 1)",
        rule_reference="Form 1099-INT, Box 1",
        input_value="1099-INT Box 1",
        output_value=f"${interest:,.2f}",
    ))
    n += 1

    std_ded = STANDARD_DEDUCTION_SINGLE_2025
    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Standard Deduction",
        rule_reference="IRS Rev. Proc. 2024-40 (2025 single filer)",
        input_value="Single filer, no itemization",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    taxable = max(0.0, interest - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Taxable Income",
        rule_reference="Form 1040, Line 15",
        input_value=f"${interest:,.2f} − ${std_ded:,.2f}",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    income_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${income_tax:,.2f}",
    ))
    n += 1

    withheld_raw = field_val("box_4_federal_tax_withheld")
    withheld = _parse_float(withheld_raw) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Federal Tax Withheld (1099-INT Box 4)",
        rule_reference="Form 1099-INT, Box 4",
        input_value="1099-INT Box 4",
        output_value=f"${withheld:,.2f}",
    ))
    n += 1

    balance = round(withheld - income_tax, 2)
    if balance > 0:
        outcome, outcome_label = "refund", f"Estimated Refund: ${balance:,.2f}"
    elif balance < 0:
        outcome, outcome_label = "owe", f"Estimated Tax Owed: ${abs(balance):,.2f}"
    else:
        outcome, outcome_label = "balanced", "Balanced — no refund or amount owed"

    steps.append(CalculationStep(
        step_number=n, source_form="1099-INT",
        label="Estimated Federal Balance",
        rule_reference="Form 1040, Line 35a / Line 37",
        input_value=f"${withheld:,.2f} withheld − ${income_tax:,.2f} liability",
        output_value=outcome_label,
    ))

    # --- State income tax estimate (optional, gated on user_context) ---
    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_steps = _calculate_state_tax(interest, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


# ---------------------------------------------------------------------------
# State income tax constants (2025 estimates)
# Sources: CA FTB, NY Dept of Taxation, IL IDOR, MA DOR
# Note: 2025 brackets estimated from 2024 rates; verify annually.
# ---------------------------------------------------------------------------

# California — graduated, single filer (FTB 2025 estimate)
STATE_BRACKETS_CA: list[tuple[float, float]] = [
    (10_756,        0.010),
    (25_499,        0.020),
    (40_245,        0.040),
    (55_866,        0.060),
    (70_606,        0.080),
    (360_659,       0.093),
    (432_787,       0.103),
    (721_314,       0.113),
    (float("inf"),  0.123),   # 13.3% kicks in above $1M
]
STATE_STD_DED_CA: float = 5_202.0   # CA single standard deduction (2025 est.)

# New York — graduated, single filer (NY Dept of Taxation 2025 estimate)
STATE_BRACKETS_NY: list[tuple[float, float]] = [
    (17_150,         0.0400),
    (23_600,         0.0450),
    (27_900,         0.0525),
    (161_550,        0.0585),
    (323_200,        0.0625),
    (2_155_350,      0.0685),
    (5_000_000,      0.0965),
    (25_000_000,     0.1030),
    (float("inf"),   0.1090),
]
STATE_STD_DED_NY: float = 8_000.0   # NY single standard deduction (2025 est.)

# Illinois — flat 4.95%, personal exemption (IDOR 2025)
STATE_BRACKETS_IL: list[tuple[float, float]] = [(float("inf"), 0.0495)]
STATE_STD_DED_IL: float = 2_775.0   # IL personal exemption (single, 2025)

# Massachusetts — flat 5.0%, personal exemption (MA DOR 2025)
STATE_BRACKETS_MA: list[tuple[float, float]] = [(float("inf"), 0.0500)]
STATE_STD_DED_MA: float = 4_400.0   # MA personal exemption (single, 2025)

# TX and WA have NO state income tax.
_NO_STATE_INCOME_TAX: frozenset[str] = frozenset({"TX", "WA"})

# Lookup maps keyed by 2-letter state code (upper-case)
_STATE_BRACKETS: dict[str, list[tuple[float, float]]] = {
    "CA": STATE_BRACKETS_CA,
    "NY": STATE_BRACKETS_NY,
    "IL": STATE_BRACKETS_IL,
    "MA": STATE_BRACKETS_MA,
}
_STATE_STD_DED: dict[str, float] = {
    "CA": STATE_STD_DED_CA,
    "NY": STATE_STD_DED_NY,
    "IL": STATE_STD_DED_IL,
    "MA": STATE_STD_DED_MA,
}
_STATE_NAMES: dict[str, str] = {
    "CA": "California",
    "NY": "New York",
    "IL": "Illinois",
    "MA": "Massachusetts",
    "TX": "Texas",
    "WA": "Washington",
}


def _calculate_state_tax(
    gross_income: float,
    state_code: str,
) -> list[CalculationStep]:
    """Return state income tax calculation steps for the supported states.

    Steps are tagged with source_form="STATE" so the frontend can route them
    to the State Tax Estimate card.  Step numbers start at 1 relative to the
    state card (independent of the federal step sequence).

    Supported states: CA, NY, IL, MA, TX (no tax), WA (no tax).
    Returns a single informational flag step for unsupported states.

    Note: State deductions are applied for all filers (RA and NRA alike).
    Most states do not follow the federal 1040-NR no-standard-deduction rule.
    Source: IRS Pub. 519 does not govern state returns; state-specific guidance applies.
    """
    state = state_code.upper().strip()
    steps: list[CalculationStep] = []
    n = 1

    state_name = _STATE_NAMES.get(state, state)

    # TX and WA: no state income tax
    if state in _NO_STATE_INCOME_TAX:
        steps.append(CalculationStep(
            step_number=n, source_form="STATE",
            label=f"State Income Tax ({state_name})",
            rule_reference=f"{state_name} has no personal state income tax",
            input_value=f"State: {state}",
            output_value="$0.00",
        ))
        return steps

    brackets = _STATE_BRACKETS.get(state)
    if not brackets:
        # State not in the supported set
        steps.append(CalculationStep(
            step_number=n, source_form="STATE",
            label=f"State Tax ({state}): Estimate Unavailable",
            rule_reference="State not yet supported — only CA, NY, IL, MA, TX, WA",
            input_value=f"State: {state}",
            output_value="—",
            is_flag=True,
        ))
        return steps

    std_ded = _STATE_STD_DED.get(state, 0.0)
    ded_label_map = {
        "CA": "CA Standard Deduction (single)",
        "NY": "NY Standard Deduction (single)",
        "IL": "IL Personal Exemption (single)",
        "MA": "MA Personal Exemption (single)",
    }
    ref_map = {
        "CA": "CA Rev. & Tax. Code §17072 (2025 estimate)",
        "NY": "NY Tax Law §611 (2025 estimate)",
        "IL": "35 ILCS 5/204 (2025 estimate)",
        "MA": "M.G.L. c.62 §3 (2025 estimate)",
    }

    # Step 1: State gross income (same as federal gross for these form types)
    steps.append(CalculationStep(
        step_number=n, source_form="STATE",
        label=f"{state_name} Gross Income",
        rule_reference=ref_map.get(state, f"{state} state return (2025 estimate)"),
        input_value="From federal gross income",
        output_value=f"${gross_income:,.2f}",
    ))
    n += 1

    # Step 2: State deduction / exemption
    steps.append(CalculationStep(
        step_number=n, source_form="STATE",
        label=ded_label_map.get(state, f"{state} Deduction/Exemption"),
        rule_reference=ref_map.get(state, "State revenue code (2025 estimate)"),
        input_value="Single filer",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    # Step 3: State taxable income
    state_taxable = max(0.0, gross_income - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="STATE",
        label=f"{state_name} Taxable Income",
        rule_reference=f"{state} state return (2025 estimate)",
        input_value=f"${gross_income:,.2f} − ${std_ded:,.2f}",
        output_value=f"${state_taxable:,.2f}",
    ))
    n += 1

    # Step 4: State income tax
    state_tax = _apply_brackets(state_taxable, brackets)
    flat_states = {"IL", "MA"}
    rate_note = "flat rate" if state in flat_states else "graduated brackets"
    steps.append(CalculationStep(
        step_number=n, source_form="STATE",
        label=f"{state_name} State Income Tax",
        rule_reference=f"{ref_map.get(state, state + ' revenue code')} — {rate_note}",
        input_value=f"${state_taxable:,.2f} state taxable income",
        output_value=f"${state_tax:,.2f}",
    ))

    return steps


# ---------------------------------------------------------------------------
# Main calculation function (dispatches by form type)
# ---------------------------------------------------------------------------

def _calculate_w2(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax outcome for a W-2 filer (2025, single).

    Ledger:
      1. Gross wages (W-2 Box 1)
      2. Standard deduction ($14,600 for RA; $0 for NRA)
      3. Taxable income
      4. Federal income tax
      5. Federal tax withheld (W-2 Box 2)
      6. Estimated federal balance
      [flag] NRA disclosure (if NRA)
      [flag] FICA SS exemption (if F-1/J-1 and SS withheld)
      [flag] FICA Medicare exemption (if F-1/J-1 and Medicare withheld)
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []
    n = 1  # step counter

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    # --- Step 1: Gross wages ---
    wages_raw = field_val("box_1_wages")
    wages = _parse_float(wages_raw)
    if wages is None:
        return [], "unknown", None

    steps.append(CalculationStep(
        step_number=n, source_form="W-2",
        label="Gross Wages (W-2 Box 1)",
        rule_reference="Form W-2, Box 1",
        input_value="W-2 Box 1",
        output_value=f"${wages:,.2f}",
    ))
    n += 1

    # --- Step 2: Standard deduction (NRA filers get $0) ---
    is_nra = _determine_residency(user_context) == "NRA"
    std_ded = 0.0 if is_nra else STANDARD_DEDUCTION_SINGLE_2025
    std_ded_label = (
        "No Standard Deduction (Nonresident Alien — Form 1040-NR)"
        if is_nra
        else "Standard Deduction"
    )
    std_ded_ref = (
        "IRS Pub. 519 Chapter 4; Form 1040-NR instructions"
        if is_nra
        else "IRS Rev. Proc. 2024-40 (2025 single filer)"
    )
    steps.append(CalculationStep(
        step_number=n, source_form="W-2",
        label=std_ded_label,
        rule_reference=std_ded_ref,
        input_value="Single filer, no itemization" if not is_nra else "NRA — no standard deduction",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    # --- Step 3: Taxable income ---
    taxable = max(0.0, wages - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="W-2",
        label="Taxable Income",
        rule_reference="Form 1040, Line 15",
        input_value=f"${wages:,.2f} − ${std_ded:,.2f}",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    # --- Step 4: Federal income tax ---
    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="W-2",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))
    n += 1

    # --- Step 5: Federal tax withheld ---
    withheld_raw = field_val("box_2_federal_tax_withheld")
    withheld = _parse_float(withheld_raw) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="W-2",
        label="Federal Tax Withheld (W-2 Box 2)",
        rule_reference="Form W-2, Box 2",
        input_value="W-2 Box 2",
        output_value=f"${withheld:,.2f}",
    ))
    n += 1

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
        step_number=n, source_form="W-2",
        label="Estimated Federal Balance",
        rule_reference="Form 1040, Line 35a / Line 37",
        input_value=f"${withheld:,.2f} withheld − ${federal_tax:,.2f} liability",
        output_value=outcome_label,
    ))
    n += 1

    # --- Advisory flags ---
    if is_nra:
        steps.append(CalculationStep(
            step_number=n, source_form="W-2",
            label="ℹ Filing as Nonresident Alien (Form 1040-NR)",
            rule_reference="IRS Pub. 519; 26 USC §7701(b)",
            input_value=f"Visa: {user_context.visa_type if user_context else 'N/A'}",
            output_value="No standard deduction. Same graduated brackets as Form 1040 for ECI. Consider a US tax treaty.",
            is_flag=True,
        ))
        n += 1

    if user_context:
        visa = user_context.visa_type
        entry_year = user_context.first_us_entry_date
        fica_exempt = _is_fica_exempt(visa, entry_year)

        ss_withheld_raw = field_val("box_4_social_security_tax")
        ss_withheld = _parse_float(ss_withheld_raw)

        if fica_exempt and ss_withheld and ss_withheld > 0:
            steps.append(CalculationStep(
                step_number=n, source_form="W-2",
                label="⚠ FICA Exemption: Social Security Tax",
                rule_reference="IRC §3121(b)(19) — F-1/J-1 student FICA exemption",
                input_value=f"Box 4 SS withheld: ${ss_withheld:,.2f}",
                output_value=f"${ss_withheld:,.2f} may be recoverable via Form 843",
                is_flag=True,
            ))
            n += 1

        mc_withheld_raw = field_val("box_6_medicare_tax")
        mc_withheld = _parse_float(mc_withheld_raw)

        if fica_exempt and mc_withheld and mc_withheld > 0:
            steps.append(CalculationStep(
                step_number=n, source_form="W-2",
                label="⚠ FICA Exemption: Medicare Tax",
                rule_reference="IRC §3101(b)(2) — F-1/J-1 student Medicare exemption",
                input_value=f"Box 6 Medicare withheld: ${mc_withheld:,.2f}",
                output_value=f"${mc_withheld:,.2f} may be recoverable via Form 843",
                is_flag=True,
            ))

    # --- State income tax estimate (optional, gated on user_context) ---
    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_steps = _calculate_state_tax(wages, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


def _calculate_1042s(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax outcome for a Form 1042-S filer (2025, single NRA).

    1042-S reports income subject to Chapter 3 withholding (e.g. scholarship
    stipends, fellowship payments).  Chapter 3 income is ECI-equivalent for
    NRA students and is taxed at the graduated rates on Form 1040-NR.

    Ledger:
      1. Chapter 3 gross income (1042-S Box 2)
      2. No standard deduction (NRA filer)
      3. Taxable income
      4. Federal income tax
      5. Chapter 3 withholding (1042-S Box 7)
      6. Chapter 4 withholding (1042-S Box 8, often $0)
      7. Estimated federal balance
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []
    n = 1

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    # Step 1: Chapter 3 gross income
    ch3_income_raw = field_val("gross_income_ch3")
    ch3_income = _parse_float(ch3_income_raw)
    if ch3_income is None:
        return [], "unknown", None

    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="Chapter 3 Gross Income (1042-S Box 2)",
        rule_reference="Form 1042-S, Box 2 — Gross Income",
        input_value="1042-S Box 2",
        output_value=f"${ch3_income:,.2f}",
    ))
    n += 1

    # Step 2: No standard deduction for NRA
    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="No Standard Deduction (Nonresident Alien — Form 1040-NR)",
        rule_reference="IRS Pub. 519 Chapter 4; Form 1040-NR instructions",
        input_value="NRA — no standard deduction",
        output_value="− $0.00",
    ))
    n += 1

    # Step 3: Taxable income
    taxable = max(0.0, ch3_income)
    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="Taxable Income",
        rule_reference="Form 1040-NR, Line 15",
        input_value=f"${ch3_income:,.2f} − $0.00",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    # Step 4: Federal income tax
    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))
    n += 1

    # Step 5: Chapter 3 withholding
    ch3_withheld = _parse_float(field_val("ch3_withholding")) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="Chapter 3 Federal Tax Withheld (1042-S Box 7)",
        rule_reference="Form 1042-S, Box 7 — U.S. Federal Tax Withheld",
        input_value="1042-S Box 7",
        output_value=f"${ch3_withheld:,.2f}",
    ))
    n += 1

    # Step 6: Chapter 4 withholding (typically $0 for students)
    ch4_withheld = _parse_float(field_val("ch4_withholding")) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="1042-S",
        label="Chapter 4 Federal Tax Withheld (1042-S Box 8)",
        rule_reference="Form 1042-S, Box 8 — U.S. Federal Tax Withheld (Ch.4)",
        input_value="1042-S Box 8",
        output_value=f"${ch4_withheld:,.2f}",
    ))
    n += 1

    # Step 7: Estimated balance
    total_withheld = round(ch3_withheld + ch4_withheld, 2)
    balance = round(total_withheld - federal_tax, 2)
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
        step_number=n, source_form="1042-S",
        label="Estimated Federal Balance",
        rule_reference="Form 1040-NR, Line 35a / Line 37",
        input_value=f"${total_withheld:,.2f} withheld − ${federal_tax:,.2f} liability",
        output_value=outcome_label,
    ))

    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_steps = _calculate_state_tax(ch3_income, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


def _calculate_misc(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax for a standalone 1099-MISC filer.

    Treats Box 3 (other income) as ordinary income on 1040-NR Line 8.
    Box 1 (rents) and Box 2 (royalties) are not yet supported.
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []
    n = 1

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    other_income = _parse_float(field_val("box_3_other_income")) or 0.0
    royalties = _parse_float(field_val("box_1_royalties")) or 0.0
    misc_income = other_income + royalties

    if misc_income == 0.0:
        return [], "unknown", None

    is_nra = _determine_residency(user_context) == "NRA"

    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="1099-MISC Income (Box 2 Royalties + Box 3 Other)",
        rule_reference="Form 1099-MISC, Boxes 2 & 3",
        input_value="1099-MISC income",
        output_value=f"${misc_income:,.2f}",
    ))
    n += 1

    std_ded = 0.0 if is_nra else STANDARD_DEDUCTION_SINGLE_2025
    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="Standard Deduction" if not is_nra else "No Standard Deduction (NRA)",
        rule_reference="IRS Rev. Proc. 2024-40" if not is_nra else "IRS Pub. 519 Chapter 4",
        input_value="NRA — no deduction" if is_nra else f"Single filer",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    taxable = max(0.0, misc_income - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="Taxable Income",
        rule_reference="Form 1040-NR, Line 15",
        input_value=f"${misc_income:,.2f} − ${std_ded:,.2f}",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))
    n += 1

    withheld = _parse_float(field_val("box_2_federal_tax_withheld")) or 0.0
    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="Federal Tax Withheld (1099-MISC Box 4)",
        rule_reference="Form 1099-MISC, Box 4",
        input_value="1099-MISC withholding",
        output_value=f"${withheld:,.2f}",
    ))
    n += 1

    balance = withheld - federal_tax
    outcome = "refund" if balance > 0 else ("owe" if balance < 0 else "balanced")
    steps.append(CalculationStep(
        step_number=n, source_form="1099-MISC",
        label="Estimated Federal Balance",
        rule_reference="Withholding − Tax",
        input_value=f"${withheld:,.2f} − ${federal_tax:,.2f}",
        output_value=f"{'Refund' if balance > 0 else 'Owe'}: ${abs(balance):,.2f}",
    ))

    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_steps = _calculate_state_tax(misc_income, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


def _calculate_combined(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Calculate federal tax for a filer with income from multiple form types.

    Aggregation service merges numeric fields before calling this function.
    All source-form fields are additive; step source_form tags show origin.

    Combined income:
      - box_1_wages               → W-2 wages (ECI)
      - box_1_nonemployee_compensation → 1099-NEC gross (ECI, subject to SE tax)
      - box_1_interest_income     → 1099-INT interest (ordinary income)
      - gross_income_ch3          → 1042-S Chapter 3 income (ECI)
      - box_1_royalties + box_3_other_income → 1099-MISC (other income)

    Combined withholding:
      - box_2_federal_tax_withheld → W-2 Box 2 (also 1099-MISC Box 4, shared key)
      - box_4_federal_tax_withheld → 1099-NEC Box 4 / 1099-INT Box 4
      - ch3_withholding            → 1042-S Box 7
      - ch4_withholding            → 1042-S Box 8

    NEC income is subject to Self-Employment tax (SE) in addition to income tax.
    NRA filers receive no standard deduction regardless of form mix.
    """
    fields = confirmed.confirmed_fields
    steps: list[CalculationStep] = []
    n = 1

    def field_val(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    is_nra = _determine_residency(user_context) == "NRA"

    # --- Income sources ---
    wages = _parse_float(field_val("box_1_wages")) or 0.0
    nec_gross = _parse_float(field_val("box_1_nonemployee_compensation")) or 0.0
    ch3_income = _parse_float(field_val("gross_income_ch3")) or 0.0
    interest_income = _parse_float(field_val("box_1_interest_income")) or 0.0
    misc_royalties = _parse_float(field_val("box_1_royalties")) or 0.0
    misc_other = _parse_float(field_val("box_3_other_income")) or 0.0
    misc_income = misc_royalties + misc_other

    # At least one income source must be present
    if wages == 0.0 and nec_gross == 0.0 and ch3_income == 0.0 and interest_income == 0.0 and misc_income == 0.0:
        return [], "unknown", None

    # NEC: apply business expenses (from user_context or confirmed field)
    nec_expenses_raw = field_val("nec_expenses")
    nec_expenses = _parse_float(nec_expenses_raw) or 0.0
    if user_context and user_context.nec_business_expenses:
        nec_expenses = max(nec_expenses, user_context.nec_business_expenses)
    nec_net = max(0.0, nec_gross - nec_expenses)

    # --- Step 1: W-2 wages (if present) ---
    if wages > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="W-2",
            label="W-2 Wages (Combined)",
            rule_reference="Form W-2, Box 1",
            input_value="Sum of all W-2 Box 1 wages",
            output_value=f"${wages:,.2f}",
        ))
        n += 1

    # --- Step 2: NEC income (if present) ---
    if nec_gross > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="1099-NEC Gross Income (Combined)",
            rule_reference="Form 1099-NEC, Box 1",
            input_value="Sum of all 1099-NEC Box 1",
            output_value=f"${nec_gross:,.2f}",
        ))
        n += 1
        if nec_expenses > 0:
            steps.append(CalculationStep(
                step_number=n, source_form="1099-NEC",
                label="NEC Business Expenses (Schedule C)",
                rule_reference="IRC §162 — ordinary and necessary business expenses",
                input_value="User-confirmed deductible expenses",
                output_value=f"− ${nec_expenses:,.2f}",
            ))
            n += 1
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="NEC Net Income",
            rule_reference="Schedule C, Line 31",
            input_value=f"${nec_gross:,.2f} − ${nec_expenses:,.2f}",
            output_value=f"${nec_net:,.2f}",
        ))
        n += 1

    # --- Step 3: 1042-S income (if present) ---
    if ch3_income > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1042-S",
            label="1042-S Chapter 3 Income (Combined)",
            rule_reference="Form 1042-S, Box 2 — Gross Income",
            input_value="Sum of all 1042-S Box 2",
            output_value=f"${ch3_income:,.2f}",
        ))
        n += 1

    # --- Step 3b: 1099-INT interest income (if present) ---
    if interest_income > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-INT",
            label="1099-INT Interest Income (Combined)",
            rule_reference="Form 1099-INT, Box 1",
            input_value="Sum of all 1099-INT Box 1",
            output_value=f"${interest_income:,.2f}",
        ))
        n += 1

    # --- Step 3c: 1099-MISC income (if present) ---
    if misc_income > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-MISC",
            label="1099-MISC Other Income (Combined)",
            rule_reference="Form 1099-MISC, Boxes 2 & 3",
            input_value="Sum of 1099-MISC royalties + other income",
            output_value=f"${misc_income:,.2f}",
        ))
        n += 1

    # --- Step 4: Total ECI (effectively connected income) ---
    total_eci = round(wages + nec_net + ch3_income + interest_income + misc_income, 2)
    steps.append(CalculationStep(
        step_number=n, source_form="COMBINED",
        label="Total Effectively Connected Income",
        rule_reference="Form 1040-NR, Line 8 — Total ECI",
        input_value=" + ".join(filter(None, [
            f"${wages:,.2f} W-2" if wages else None,
            f"${nec_net:,.2f} NEC net" if nec_gross else None,
            f"${ch3_income:,.2f} 1042-S" if ch3_income else None,
            f"${interest_income:,.2f} INT" if interest_income else None,
            f"${misc_income:,.2f} MISC" if misc_income else None,
        ])),
        output_value=f"${total_eci:,.2f}",
    ))
    n += 1

    # --- Step 5: Standard deduction (NRA = $0) ---
    std_ded = 0.0 if is_nra else STANDARD_DEDUCTION_SINGLE_2025
    steps.append(CalculationStep(
        step_number=n, source_form="COMBINED",
        label=(
            "No Standard Deduction (Nonresident Alien — Form 1040-NR)"
            if is_nra else "Standard Deduction"
        ),
        rule_reference=(
            "IRS Pub. 519 Chapter 4; Form 1040-NR instructions"
            if is_nra else "IRS Rev. Proc. 2024-40 (2025 single filer)"
        ),
        input_value="NRA — no standard deduction" if is_nra else "Single filer",
        output_value=f"− ${std_ded:,.2f}",
    ))
    n += 1

    # --- Step 6: Taxable income ---
    taxable = max(0.0, total_eci - std_ded)
    steps.append(CalculationStep(
        step_number=n, source_form="COMBINED",
        label="Taxable Income",
        rule_reference="Form 1040-NR, Line 15",
        input_value=f"${total_eci:,.2f} − ${std_ded:,.2f}",
        output_value=f"${taxable:,.2f}",
    ))
    n += 1

    # --- Step 7: Federal income tax ---
    federal_tax = _apply_brackets(taxable)
    steps.append(CalculationStep(
        step_number=n, source_form="COMBINED",
        label="Federal Income Tax",
        rule_reference="IRS 2025 Tax Table (Rev. Proc. 2024-40, Table 1)",
        input_value=f"${taxable:,.2f} taxable income",
        output_value=f"${federal_tax:,.2f}",
    ))
    n += 1

    # --- Step 8: SE tax on NEC net (if present and not FICA-exempt) ---
    se_tax = 0.0
    if nec_net > 0:
        visa = (user_context.visa_type or "") if user_context else ""
        entry_year = (user_context.first_us_entry_date or "") if user_context else ""
        fica_exempt = _is_fica_exempt(visa, entry_year)

        se_base = round(nec_net * SE_INCOME_MULTIPLIER, 2)
        se_tax = round(se_base * SE_TAX_RATE, 2)

        if fica_exempt:
            steps.append(CalculationStep(
                step_number=n, source_form="1099-NEC",
                label="⚠ SE Tax: FICA Exempt (F-1/J-1 — No SE Tax)",
                rule_reference="IRC §1402(b); IRS Pub. 519 — NRA SE tax exemption",
                input_value=f"Visa: {visa}",
                output_value="$0.00 SE tax (FICA-exempt status applies)",
                is_flag=True,
            ))
            n += 1
            se_tax = 0.0
        else:
            steps.append(CalculationStep(
                step_number=n, source_form="1099-NEC",
                label="Self-Employment Tax (SE)",
                rule_reference=f"IRC §1401; SE base = net income × {SE_INCOME_MULTIPLIER}",
                input_value=f"${nec_net:,.2f} net NEC income",
                output_value=f"${se_tax:,.2f}",
            ))
            n += 1

    # --- Step 9: Total tax liability ---
    total_liability = round(federal_tax + se_tax, 2)
    if se_tax > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="COMBINED",
            label="Total Tax Liability",
            rule_reference="Form 1040-NR — income tax + SE tax",
            input_value=f"${federal_tax:,.2f} income tax + ${se_tax:,.2f} SE tax",
            output_value=f"${total_liability:,.2f}",
        ))
        n += 1

    # --- Withholding sources ---
    w2_withheld = _parse_float(field_val("box_2_federal_tax_withheld")) or 0.0
    nec_withheld = _parse_float(field_val("box_4_federal_tax_withheld")) or 0.0
    ch3_withheld = _parse_float(field_val("ch3_withholding")) or 0.0
    ch4_withheld = _parse_float(field_val("ch4_withholding")) or 0.0

    if w2_withheld > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="W-2",
            label="W-2 Federal Tax Withheld",
            rule_reference="Form W-2, Box 2",
            input_value="Sum of all W-2 Box 2",
            output_value=f"${w2_withheld:,.2f}",
        ))
        n += 1

    if nec_withheld > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1099-NEC",
            label="1099-NEC Federal Tax Withheld",
            rule_reference="Form 1099-NEC, Box 4",
            input_value="Sum of all 1099-NEC Box 4",
            output_value=f"${nec_withheld:,.2f}",
        ))
        n += 1

    if ch3_withheld > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1042-S",
            label="1042-S Chapter 3 Withheld",
            rule_reference="Form 1042-S, Box 7",
            input_value="Sum of all 1042-S Box 7",
            output_value=f"${ch3_withheld:,.2f}",
        ))
        n += 1

    if ch4_withheld > 0:
        steps.append(CalculationStep(
            step_number=n, source_form="1042-S",
            label="1042-S Chapter 4 Withheld",
            rule_reference="Form 1042-S, Box 8",
            input_value="Sum of all 1042-S Box 8",
            output_value=f"${ch4_withheld:,.2f}",
        ))
        n += 1

    # --- Final balance ---
    total_withheld = round(w2_withheld + nec_withheld + ch3_withheld + ch4_withheld, 2)
    balance = round(total_withheld - total_liability, 2)

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
        step_number=n, source_form="COMBINED",
        label="Estimated Federal Balance",
        rule_reference="Form 1040-NR, Line 35a / Line 37",
        input_value=f"${total_withheld:,.2f} withheld − ${total_liability:,.2f} liability",
        output_value=outcome_label,
    ))

    if user_context and user_context.wants_state_estimate and user_context.state_code:
        state_steps = _calculate_state_tax(total_eci, user_context.state_code)
        steps.extend(state_steps)

    return steps, outcome, abs(balance)


def calculate(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext] = None,
) -> tuple[list[CalculationStep], str, Optional[float]]:
    """Dispatch to the correct calculation branch based on form type.

    Returns:
        steps:    list[CalculationStep] — ledger rows (numbers only, no explanations yet)
        outcome:  str — "refund" | "owe" | "balanced" | "unknown"
        amount:   Optional[float] — absolute refund or owed amount
    """
    fields = confirmed.confirmed_fields
    form_fv = fields.get("form_type")
    form_type = (form_fv.value or "") if form_fv else ""

    if "COMBINED" in form_type:
        return _calculate_combined(confirmed, user_context)
    if "1042-S" in form_type:
        return _calculate_1042s(confirmed, user_context)
    if "1099-NEC" in form_type or "NEC" in form_type:
        return _calculate_nec(confirmed, user_context)
    if "1099-INT" in form_type or "INT" in form_type:
        return _calculate_int(confirmed, user_context)
    if "1099-MISC" in form_type or "MISC" in form_type:
        # 1099-MISC: treat other income (Box 3) like NEC for tax purposes.
        # Rents (Box 1) and royalties (Box 2) are not yet supported.
        return _calculate_misc(confirmed, user_context)
    if "W-2" in form_type or "W2" in form_type or not form_type:
        # Default to W-2 if form_type is missing (legacy / OCR fallback)
        return _calculate_w2(confirmed, user_context)
    return [], "unknown", None


# ---------------------------------------------------------------------------
# IRS Tax Treaty Table — Student / Apprentice Income (Pub 901, Table 1)
# Source: IRS Publication 901 (2024 edition)
# Schema per entry:
#   country:    display name
#   article:    treaty article citation
#   annual_cap: maximum exempt income per year (USD)
#   max_years:  maximum years of eligibility (None = unlimited)
#
# NOTE: These cover wages / personal-services income earned while studying.
# Scholarship/fellowship income is often separately exempt (Article varies).
# Form 8833 (Treaty-Based Return Position Disclosure) is REQUIRED when
# claiming a treaty exemption that reduces US tax liability (IRC §6114).
# ---------------------------------------------------------------------------

TREATY_TABLE: dict[str, dict] = {
    "BD": {"country": "Bangladesh",           "article": "Art. 21",                 "annual_cap": 9_000.0,  "max_years": None},
    "BY": {"country": "Belarus",              "article": "Art. 18",                 "annual_cap": 9_000.0,  "max_years": 5},
    "BE": {"country": "Belgium",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "BG": {"country": "Bulgaria",             "article": "Art. 18",                 "annual_cap": 9_000.0,  "max_years": 5},
    "CA": {"country": "Canada",               "article": "Art. XXI",                "annual_cap": 9_000.0,  "max_years": 5},
    "CN": {"country": "China (PRC)",          "article": "Special Protocol Art. 6", "annual_cap": 5_000.0,  "max_years": 5},
    "CY": {"country": "Cyprus",               "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "CZ": {"country": "Czech Republic",       "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "DK": {"country": "Denmark",              "article": "Art. 16",                 "annual_cap": 9_000.0,  "max_years": 5},
    "EG": {"country": "Egypt",                "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "EE": {"country": "Estonia",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "FI": {"country": "Finland",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "FR": {"country": "France",               "article": "Art. 21",                 "annual_cap": 9_000.0,  "max_years": 5},
    "DE": {"country": "Germany",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 4},
    "GR": {"country": "Greece",               "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "HU": {"country": "Hungary",              "article": "Art. 23",                 "annual_cap": 9_000.0,  "max_years": 5},
    "IS": {"country": "Iceland",              "article": "Art. 19",                 "annual_cap": 9_000.0,  "max_years": 5},
    "IN": {"country": "India",                "article": "Art. 21",                 "annual_cap": 9_000.0,  "max_years": 2},
    "ID": {"country": "Indonesia",            "article": "Art. 19",                 "annual_cap": 9_000.0,  "max_years": 5},
    "IE": {"country": "Ireland",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "IL": {"country": "Israel",               "article": "Art. 24",                 "annual_cap": 9_000.0,  "max_years": 5},
    "IT": {"country": "Italy",                "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "JM": {"country": "Jamaica",              "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "JP": {"country": "Japan",                "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "KZ": {"country": "Kazakhstan",           "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "KG": {"country": "Kyrgyzstan",           "article": "Art. 18 (former USSR)",   "annual_cap": 9_000.0,  "max_years": 5},
    "KR": {"country": "Korea (South)",        "article": "Art. 21",                 "annual_cap": 2_000.0,  "max_years": 5},
    "LV": {"country": "Latvia",               "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "LT": {"country": "Lithuania",            "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "LU": {"country": "Luxembourg",           "article": "Art. 21",                 "annual_cap": 9_000.0,  "max_years": 5},
    "MT": {"country": "Malta",                "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "MX": {"country": "Mexico",               "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "MD": {"country": "Moldova",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "MA": {"country": "Morocco",              "article": "Art. 18",                 "annual_cap": 9_000.0,  "max_years": 5},
    "NL": {"country": "Netherlands",          "article": "Art. 22",                 "annual_cap": 2_000.0,  "max_years": 5},
    "NZ": {"country": "New Zealand",          "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "NO": {"country": "Norway",               "article": "Art. 16",                 "annual_cap": 9_000.0,  "max_years": 5},
    "PK": {"country": "Pakistan",             "article": "Art. 15",                 "annual_cap": 9_000.0,  "max_years": 5},
    "PH": {"country": "Philippines",          "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "PL": {"country": "Poland",               "article": "Art. 18",                 "annual_cap": 9_000.0,  "max_years": 5},
    "PT": {"country": "Portugal",             "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "RO": {"country": "Romania",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "RU": {"country": "Russia",               "article": "Art. 18",                 "annual_cap": 9_000.0,  "max_years": 5},
    "SK": {"country": "Slovak Republic",      "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "SI": {"country": "Slovenia",             "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "ZA": {"country": "South Africa",         "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "ES": {"country": "Spain",                "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "LK": {"country": "Sri Lanka",            "article": "Art. 17",                 "annual_cap": 9_000.0,  "max_years": 5},
    "SE": {"country": "Sweden",               "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "CH": {"country": "Switzerland",          "article": "Art. 19",                 "annual_cap": 9_000.0,  "max_years": 5},
    "TJ": {"country": "Tajikistan",           "article": "Art. 18 (former USSR)",   "annual_cap": 9_000.0,  "max_years": 5},
    "TH": {"country": "Thailand",             "article": "Art. 22",                 "annual_cap": 9_000.0,  "max_years": 5},
    "TT": {"country": "Trinidad and Tobago",  "article": "Art. 19",                 "annual_cap": 9_000.0,  "max_years": 5},
    "TN": {"country": "Tunisia",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "TR": {"country": "Turkey",               "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "TM": {"country": "Turkmenistan",         "article": "Art. 18 (former USSR)",   "annual_cap": 9_000.0,  "max_years": 5},
    "UA": {"country": "Ukraine",              "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "GB": {"country": "United Kingdom",       "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
    "UZ": {"country": "Uzbekistan",           "article": "Art. 18 (former USSR)",   "annual_cap": 9_000.0,  "max_years": 5},
    "VE": {"country": "Venezuela",            "article": "Art. 20",                 "annual_cap": 9_000.0,  "max_years": 5},
}

# Visa types that can claim student income treaty exemptions
_TREATY_ELIGIBLE_VISAS = {"F-1", "J-1", "F1", "J1", "OPT", "CPT"}

# Visa types for which ITIN guidance is relevant (no SSN issued)
_ITIN_GUIDANCE_VISAS = {"F-1", "J-1", "F1", "J1", "OPT", "CPT"}


class ReportExtras(TypedDict):
    """All supplementary values needed to build TaxReport and generate the 1040NR PDF.

    All fields reading from confirmed_fields are done here (DRY).
    generate_1040nr() in form_generator.py reads from TaxReport which is populated
    by unpacking this TypedDict.
    """
    treaty_exempt_amount: Optional[float]   # USD amount exempt under treaty
    treaty_country: Optional[str]           # Display name of treaty country
    treaty_article: Optional[str]           # Treaty article citation, e.g. "Art. XXI"
    needs_itin_guidance: bool               # True when student visa + no SSN
    form_8843_data: Optional[Form8843Data]  # Populated for NRA visa types
    wages: Optional[float]                  # W-2 Box 1 ONLY (None for NEC filers)
    gross_income: Optional[float]           # NEC Box 1 ONLY (None for W-2 filers)
    withholding: Optional[float]            # Federal income tax withheld


def compute_report_extras(
    confirmed: ConfirmedFields,
    user_context: Optional[UserContext],
) -> ReportExtras:
    """Compute all supplementary TaxReport values from confirmed fields + user context.

    Called by tax_advisor.run_tax_analysis() to populate TaxReport extras.
    All field-reading from confirmed_fields is centralized here (DRY).
    """
    fields = confirmed.confirmed_fields

    def _fv(name: str) -> Optional[str]:
        fv = fields.get(name)
        return fv.value if fv else None

    # --- Treaty exemption ---
    treaty_amount: Optional[float] = None
    treaty_country_name: Optional[str] = None
    treaty_article: Optional[str] = None

    if user_context and user_context.country_of_origin:
        code = user_context.country_of_origin.upper().strip()
        treaty = TREATY_TABLE.get(code)
        visa = (user_context.visa_type or "").strip()

        if treaty and visa in _TREATY_ELIGIBLE_VISAS:
            is_nra = _determine_residency(user_context) == "NRA"
            if is_nra:
                # Check max_years eligibility
                eligible = True
                if treaty["max_years"] is not None and user_context.first_us_entry_date:
                    try:
                        entry_year = int(str(user_context.first_us_entry_date)[:4])
                        years_elapsed = CURRENT_TAX_YEAR - entry_year
                        eligible = years_elapsed < treaty["max_years"]
                    except (ValueError, TypeError):
                        eligible = True  # unknown entry year → assume eligible

                if eligible:
                    # Sum all income sources for treaty calculation.
                    # Each source is independent; don't short-circuit with `or`.
                    income = sum(filter(None, [
                        _parse_float(_fv("box_1_wages")),
                        _parse_float(_fv("box_1_nonemployee_compensation")),
                        _parse_float(_fv("box_1_interest_income")),
                        _parse_float(_fv("gross_income_ch3")),
                    ]))
                    exempt = min(income, treaty["annual_cap"])
                    if exempt > 0:
                        treaty_amount = round(exempt, 2)
                        treaty_country_name = treaty["country"]
                        treaty_article = treaty["article"]

    # --- ITIN guidance ---
    needs_itin = False
    if user_context and (user_context.visa_type or "").strip() in _ITIN_GUIDANCE_VISAS:
        ssn_fv = fields.get("employee_ssn") or fields.get("recipient_tin")
        has_ssn = bool(ssn_fv and ssn_fv.value and ssn_fv.value.strip())
        needs_itin = not has_ssn

    # --- Form 8843 data assembly ---
    form_8843_data: Optional[Form8843Data] = None
    if user_context and (user_context.visa_type or "").strip() in NRA_VISA_TYPES:
        form_8843_data = _assemble_form_8843_data(user_context, has_income=True)

    # --- 1040NR income fields (W-2 vs NEC separation) ---
    wages: Optional[float] = _parse_float(_fv("box_1_wages"))
    gross_income: Optional[float] = _parse_float(_fv("box_1_nonemployee_compensation"))
    # Withholding: W-2 Box 2 takes precedence; fall back to NEC Box 4
    withholding: Optional[float] = _parse_float(
        _fv("box_2_federal_tax_withheld") or _fv("box_4_federal_tax_withheld")
    )

    return ReportExtras(
        treaty_exempt_amount=treaty_amount,
        treaty_country=treaty_country_name,
        treaty_article=treaty_article,
        needs_itin_guidance=needs_itin,
        form_8843_data=form_8843_data,
        wages=wages,
        gross_income=gross_income,
        withholding=withholding,
    )
