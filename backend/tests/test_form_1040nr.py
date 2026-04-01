"""Tests for Form 1040NR field map and generation pipeline.

Test contract (10 paths):
  T01  EXPECTED_FIELDS_2024 encodes all FIELD_MAP_2024 short names (no drift)
  T02  FIELD_MAP canonical alias points to FIELD_MAP_2024
  T03  FIELD_MAPS dispatch table includes year 2024
  T04  READONLY_FIELDS_2024 contains the 4 auto-calculated fields
  T05  CHECKBOX_FIELDS_2024 contains the 4 filing-status checkboxes
  T06  generate_1040nr raises FileNotFoundError for unknown year
  T07  generate_1040nr raises ValueError when wages and gross_income are both None
  T08  _build_1040nr_field_values sets wages_line_1a for W-2 filers
  T09  _build_1040nr_field_values sets nec_income_line_2 for NEC filers
  T10  generate_cover_sheet_package returns valid PDF bytes

Run: pytest backend/tests/test_form_1040nr.py -v
"""

from __future__ import annotations

import pytest

from app.constants.form_1040nr_fields import (
    EXPECTED_FIELDS,
    EXPECTED_FIELDS_2024,
    FIELD_MAP,
    FIELD_MAP_2024,
    FIELD_MAPS,
    READONLY_FIELDS_2024,
    CHECKBOX_FIELDS_2024,
)
from app.schemas.document import TaxReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(**overrides) -> TaxReport:
    defaults = dict(
        document_id="test-doc-1040nr",
        calculation_steps=[],
        estimated_outcome="refund",
        estimated_amount=500.0,
        outcome_explanation="",
        validation_results=[],
        wages=30000.0,
        gross_income=None,
        withholding=3000.0,
    )
    defaults.update(overrides)
    return TaxReport(**defaults)


# ---------------------------------------------------------------------------
# T01 — EXPECTED_FIELDS_2024 encodes all FIELD_MAP_2024 short names (no drift)
# ---------------------------------------------------------------------------

def test_t01_expected_fields_matches_field_map():
    """Every local field name in FIELD_MAP_2024 must appear in EXPECTED_FIELDS_2024."""
    short_names = set(FIELD_MAP_2024.values())
    for short in short_names:
        matched = any(
            full.endswith("." + short) or full.endswith(short)
            for full in EXPECTED_FIELDS_2024
        )
        assert matched, (
            f"Short name {short!r} from FIELD_MAP_2024 has no matching entry in EXPECTED_FIELDS_2024"
        )


# ---------------------------------------------------------------------------
# T02 — FIELD_MAP canonical alias points to FIELD_MAP_2024
# ---------------------------------------------------------------------------

def test_t02_field_map_alias_is_2024():
    assert FIELD_MAP is FIELD_MAP_2024


# ---------------------------------------------------------------------------
# T03 — FIELD_MAPS dispatch table includes year 2024
# ---------------------------------------------------------------------------

def test_t03_field_maps_dispatch_includes_2024():
    assert 2024 in FIELD_MAPS
    assert FIELD_MAPS[2024] is FIELD_MAP_2024


# ---------------------------------------------------------------------------
# T04 — READONLY_FIELDS_2024 has the 4 auto-calculated fields
# ---------------------------------------------------------------------------

def test_t04_readonly_fields():
    expected_readonly = {"f1_51[0]", "f1_52[0]", "f1_65[0]", "f2_29[0]"}
    assert expected_readonly.issubset(READONLY_FIELDS_2024), (
        f"Missing readonly fields: {expected_readonly - READONLY_FIELDS_2024}"
    )


# ---------------------------------------------------------------------------
# T05 — CHECKBOX_FIELDS_2024 contains the 4 filing-status checkboxes
# ---------------------------------------------------------------------------

def test_t05_checkbox_fields():
    filing_status_checkboxes = {"c1_1[0]", "c1_2[0]", "c1_3[0]", "c1_4[0]"}
    assert filing_status_checkboxes.issubset(CHECKBOX_FIELDS_2024), (
        f"Missing checkbox fields: {filing_status_checkboxes - CHECKBOX_FIELDS_2024}"
    )


# ---------------------------------------------------------------------------
# T06 — generate_1040nr raises FileNotFoundError for unknown year
# ---------------------------------------------------------------------------

def test_t06_generate_1040nr_raises_for_missing_template():
    from app.services.form_generator import generate_1040nr, _1040nr_cache

    report = _make_report()
    _1040nr_cache.pop(2099, None)
    with pytest.raises(FileNotFoundError):
        generate_1040nr(report, year=2099)


# ---------------------------------------------------------------------------
# T07 — generate_1040nr raises ValueError when no income data
# ---------------------------------------------------------------------------

def test_t07_generate_1040nr_raises_missing_income():
    from app.services.form_generator import generate_1040nr

    report = _make_report(wages=None, gross_income=None)
    with pytest.raises(ValueError, match="MISSING_REPORT_DATA"):
        generate_1040nr(report, year=2024)


# ---------------------------------------------------------------------------
# T08 — _build_1040nr_field_values routes wages to wages_line_1a for W-2
# ---------------------------------------------------------------------------

def test_t08_field_values_w2_path():
    from app.services.form_generator import _build_1040nr_field_values

    report = _make_report(wages=45000.0, gross_income=None, withholding=4500.0)
    fv = _build_1040nr_field_values(report)

    # W-2 path: Line 1a filled, Line 2 (NEC) empty
    assert fv.get("wages_line_1a") == "45000.00"
    assert fv.get("nec_income_line_2", "") == ""


# ---------------------------------------------------------------------------
# T09 — _build_1040nr_field_values routes income to nec_income_line_2 for NEC
# ---------------------------------------------------------------------------

def test_t09_field_values_nec_path():
    from app.services.form_generator import _build_1040nr_field_values

    report = _make_report(wages=None, gross_income=12000.0, withholding=0.0)
    fv = _build_1040nr_field_values(report)

    # NEC path: Line 2 filled, Line 1a (wages) empty
    assert fv.get("nec_income_line_2") == "12000.00"
    assert fv.get("wages_line_1a", "") == ""


# ---------------------------------------------------------------------------
# T10 — generate_cover_sheet_package returns valid PDF bytes
# ---------------------------------------------------------------------------

def test_t10_cover_sheet_package_valid_pdf():
    try:
        import reportlab  # noqa: F401
    except ImportError:
        pytest.skip("reportlab not installed")

    from app.services.form_generator import generate_cover_sheet_package

    report = _make_report()
    pdf = generate_cover_sheet_package(report)
    assert pdf.startswith(b"%PDF"), "Cover sheet package must be a valid PDF"


# ---------------------------------------------------------------------------
# T11–T15 — _extract_step_amount() integration tests (TODO-23)
# ---------------------------------------------------------------------------

from app.schemas.document import CalculationStep
from app.services.form_generator import _extract_step_amount


def _make_step(label: str, output_value: str, step_number: int = 1) -> CalculationStep:
    return CalculationStep(
        step_number=step_number,
        label=label,
        rule_reference="test",
        input_value="test",
        output_value=output_value,
    )


def test_t11_extract_step_amount_dollar_with_commas():
    """Step with '$30,000.00' output → extracts 30000.0."""
    steps = [_make_step("Federal Income Tax", "$30,000.00")]
    result = _extract_step_amount(steps, "Federal Income Tax")
    assert result == 30000.0


def test_t12_extract_step_amount_zero_dollars():
    """Step with '$0.00' output → extracts 0.0 (NOT None)."""
    steps = [_make_step("Federal Income Tax", "$0.00")]
    result = _extract_step_amount(steps, "Federal Income Tax")
    assert result == 0.0
    assert result is not None


def test_t13_extract_step_amount_no_matching_step():
    """No matching step → returns None."""
    steps = [_make_step("Unrelated Label", "$500.00")]
    result = _extract_step_amount(steps, "Federal Income Tax")
    assert result is None


def test_t14_extract_step_amount_multiple_matches_returns_last():
    """Multiple matching steps → returns the LAST match."""
    steps = [
        _make_step("Federal Income Tax", "$1,000.00", step_number=1),
        _make_step("Federal Income Tax", "$2,500.00", step_number=2),
        _make_step("Federal Income Tax", "$7,777.00", step_number=3),
    ]
    result = _extract_step_amount(steps, "Federal Income Tax")
    assert result == 7777.0


def test_t15_extract_step_amount_no_dollar_in_output():
    """Step with no dollar amount in output → returns None."""
    steps = [_make_step("Federal Income Tax", "N/A — exempt")]
    result = _extract_step_amount(steps, "Federal Income Tax")
    assert result is None
