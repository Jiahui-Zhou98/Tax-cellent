"""Form 8843 IRS Instructions Cross-Check (TODO-17).

Verifies that Form8843Data fields map to the correct IRS form lines with
correct semantics. Cross-referenced against IRS Form 8843 instructions
and IRS Publication 519 Chapter 1.

IRS Form 8843 Structure (2024/2025):
  Header:     Last name, First name/MI, TIN
  Part I:     General Information (all filers)
              Line 1a — Visa type + date entered US
              Line 3  — Days present in US (current year)
  Part II:    Teachers and Trainees (J-1 researchers, etc.)
              Line 4a — Academic institution name
              Line 4b — City
              Line 4c — State
              Line 5  — Director of academic program
  Part III:   Students (F-1, J-1 students, M-1)
              Line 6a — Academic institution name
              Line 6b — City/State
              Line 7  — Prior years claimed as exempt individual
              Line 8  — Change of status applied?
  Part V:     Exchange visitors (J-1 / Q visa)
              Line 9  — Exchange program name
              Line 10 — Sponsor name
              Line 11 — Sponsor address

Cross-check test contract:
  S01  _build_field_values produces correct name fields
  S02  days_in_us → string integer (not float), matches Line 3
  S03  visa_type field matches Line 1a semantics
  S04  institution fields match Part II/III semantics
  S05  prior_exempt_years → comma-separated year list for Line 7
  S06  sign_date defaults to April 15 of tax year
  S07  tin_status "applied_for" → "Applied For" text
  S08  tin_status "none" → "None" text
  S09  Exchange program fields populated for J-1
  S10  has_income flag does NOT affect field values (only cover sheet/deadline)

Run: pytest backend/tests/test_form_8843_semantics.py -v
"""

from __future__ import annotations

from app.schemas.form_8843 import Form8843Data
from app.services.form_generator import _build_field_values


def _make_data(**overrides) -> Form8843Data:
    defaults = dict(
        first_name="Wei",
        last_name="Chen",
        visa_type="F-1",
        first_us_entry_date="2022-08-15",
        days_in_us_current_year=200,
        institution_name="Stanford University",
        institution_city="Stanford",
        institution_state="CA",
        role="student",
        tin_status="ssn",
        tin_value="123-45-6789",
        has_income=False,
        tax_year=2024,
        catch_up_years=[],
        exempt_prior_years=[2022, 2023],
    )
    defaults.update(overrides)
    return Form8843Data(**defaults)


# S01 — Name fields (Header: Last name, First name/MI)
def test_s01_name_fields():
    fv = _build_field_values(_make_data())
    assert fv["last_name"] == "Chen"
    assert fv["first_name_mi"] == "Wei"
    assert "Wei Chen" in fv["taxpayer_name_sign"]


# S02 — Days in US → string integer (Line 3)
def test_s02_days_in_us_is_integer_string():
    fv = _build_field_values(_make_data(days_in_us_current_year=200))
    assert fv["days_us_current"] == "200"
    # Must be a count, not a float
    assert "." not in fv["days_us_current"]


# S03 — Visa type (Line 1a — combined with entry date)
def test_s03_visa_type_matches_line_1a():
    fv = _build_field_values(_make_data(visa_type="F-1"))
    assert "F-1" in fv["visa_type"]
    fv_j1 = _build_field_values(_make_data(visa_type="J-1"))
    assert "J-1" in fv_j1["visa_type"]


# S04 — Institution field (Part III Line 9 — combined name, city, state)
def test_s04_institution_fields():
    fv = _build_field_values(_make_data())
    assert "Stanford University" in fv["institution_name"]
    assert "Stanford" in fv["institution_name"]
    assert "CA" in fv["institution_name"]


# S05 — Prior exempt years → comma-separated list (Line 7)
def test_s05_prior_exempt_years_format():
    fv = _build_field_values(_make_data(exempt_prior_years=[2022, 2023]))
    assert fv["prior_exempt_years"] == "2022, 2023"


def test_s05b_no_prior_years():
    fv = _build_field_values(_make_data(exempt_prior_years=[]))
    assert fv["prior_exempt_years"] == ""


# S06 — Sign date included in signature line
def test_s06_sign_date():
    fv = _build_field_values(_make_data(tax_year=2024))
    assert "2024-04-15" in fv["taxpayer_name_sign"]


# S07 — TIN "applied_for" → "Applied For"
def test_s07_tin_applied_for():
    fv = _build_field_values(_make_data(tin_status="applied_for", tin_value=None))
    assert fv["tin"] == "Applied For"


# S08 — TIN "none" → "None"
def test_s08_tin_none():
    fv = _build_field_values(_make_data(tin_status="none", tin_value=None))
    assert fv["tin"] == "None"


# S09 — Exchange program fields for J-1
def test_s09_exchange_program_fields():
    fv = _build_field_values(_make_data(
        visa_type="J-1",
        exchange_program_name="Fulbright Program",
        sponsor_name="Institute of International Education",
        sponsor_address="809 UN Plaza, New York, NY 10017",
    ))
    assert fv["exchange_program"] == "Fulbright Program"
    assert fv["sponsor_name"] == "Institute of International Education"
    # sponsor_address no longer a separate field in 2025 layout


# S10 — has_income flag does NOT change field values
def test_s10_has_income_does_not_affect_fields():
    fv_income = _build_field_values(_make_data(has_income=True))
    fv_no_income = _build_field_values(_make_data(has_income=False))
    # Core field values should be identical (has_income only affects cover sheet/deadline)
    for key in ["last_name", "first_name_mi", "tin", "institution_name"]:
        assert fv_income[key] == fv_no_income[key]
