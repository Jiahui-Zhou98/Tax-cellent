"""Deterministic rule-based validation of confirmed tax fields."""
import re
from app.schemas.document import ConfirmedFields, ValidationOutput, ValidationIssue

CURRENT_YEAR = 2025

REQUIRED_FIELDS_BY_FORM = {
    "W-2": [
        "tax_year", "employee_name", "employer_name",
        "box_1_wages", "box_2_federal_tax_withheld",
    ],
    "1099-NEC": [
        "tax_year", "payer_name", "recipient_name",
        "box_1_nonemployee_compensation",
    ],
    "1099-INT": [
        "tax_year", "payer_name", "recipient_name",
        "box_1_interest_income",
    ],
}

# All money field names across all form types
_ALL_MONEY_FIELDS = {
    "box_1_wages", "box_2_federal_tax_withheld",
    "box_3_social_security_wages", "box_4_social_security_tax",
    "box_5_medicare_wages", "box_6_medicare_tax",
    "box_16_state_wages", "box_17_state_income_tax",
    "box_18_local_wages", "box_19_local_income_tax",
    "box_1_nonemployee_compensation", "box_4_federal_tax_withheld",
    "box_1_interest_income", "box_2_early_withdrawal_penalty",
}


def _parse_money(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def validate(confirmed: ConfirmedFields) -> ValidationOutput:
    issues: list[ValidationIssue] = []
    fields = confirmed.confirmed_fields

    form_fv = fields.get("form_type")
    form_val = form_fv.value if form_fv else None

    # 1. Required field presence
    required = REQUIRED_FIELDS_BY_FORM.get(form_val or "", [])
    critical = {"box_1_wages", "box_1_nonemployee_compensation", "box_1_interest_income"}
    for req in required:
        fv = fields.get(req)
        if not fv or not fv.value:
            issues.append(ValidationIssue(
                field=req,
                type="missing",
                message=f"Required field '{req}' is missing or empty",
                severity="error" if req in critical else "warning",
            ))

    # 2. Unresolved fields
    for f in confirmed.unresolved_fields:
        issues.append(ValidationIssue(
            field=f, type="unresolved",
            message=f"Field '{f}' was left unresolved during review",
            severity="warning",
        ))

    # 3. Tax year
    fv = fields.get("tax_year")
    if fv and fv.value:
        yr = str(fv.value).strip()
        if not re.fullmatch(r"\d{4}", yr):
            issues.append(ValidationIssue(
                field="tax_year", type="invalid_format",
                message=f"Tax year '{yr}' is not a valid 4-digit year",
                severity="error",
            ))
        else:
            year = int(yr)
            if year < 2010 or year > CURRENT_YEAR + 1:
                issues.append(ValidationIssue(
                    field="tax_year", type="suspicious",
                    message=f"Tax year {year} seems unusual — expected 2010–{CURRENT_YEAR}",
                    severity="warning",
                ))
            elif year < CURRENT_YEAR:
                issues.append(ValidationIssue(
                    field="tax_year", type="prior_year",
                    message=(
                        f"This document is from {year} — you may need to file a late return "
                        f"or amended return, not a {CURRENT_YEAR} return. "
                        f"See IRS instructions for late filing."
                    ),
                    severity="warning",
                ))

    # 4. EIN format
    for fname in ("employer_ein", "box_15_employer_state_id", "payer_tin"):
        fv = fields.get(fname)
        if fv and fv.value and not re.match(r"^\d{2}-\d{7}$", fv.value):
            issues.append(ValidationIssue(
                field=fname, type="invalid_format",
                message=f"'{fname}' value '{fv.value}' is not in XX-XXXXXXX format",
                severity="warning",
            ))

    # 5. Money field parsing
    parsed: dict[str, float] = {}
    for fname in _ALL_MONEY_FIELDS:
        fv = fields.get(fname)
        if fv and fv.value:
            val = _parse_money(fv.value)
            if val is None:
                issues.append(ValidationIssue(
                    field=fname, type="invalid_format",
                    message=f"'{fname}' value '{fv.value}' is not a valid number",
                    severity="error",
                ))
            else:
                parsed[fname] = val

    # 6. W-2 logical checks
    if form_val == "W-2":
        wages = parsed.get("box_1_wages", 0)
        fed   = parsed.get("box_2_federal_tax_withheld", 0)
        if wages > 0 and fed > wages:
            issues.append(ValidationIssue(
                field="box_2_federal_tax_withheld", type="conflict",
                message="Federal tax withheld exceeds total wages — likely data error",
                severity="error",
            ))

        ss_wages = parsed.get("box_3_social_security_wages", 0)
        ss_tax   = parsed.get("box_4_social_security_tax", 0)
        expected = round(ss_wages * 0.062, 2) if ss_wages else 0
        if ss_tax > 0 and expected > 0 and abs(ss_tax - expected) > 5:
            issues.append(ValidationIssue(
                field="box_4_social_security_tax", type="suspicious",
                message=f"SS tax {ss_tax} differs from expected {expected} (6.2% of SS wages)",
                severity="warning",
            ))

    status = (
        "error"   if any(i.severity == "error" for i in issues) else
        "warning" if issues else
        "ok"
    )
    return ValidationOutput(status=status, issues=issues)
