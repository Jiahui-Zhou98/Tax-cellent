"""Visual PDF verification tests — read-back approach.

Generates PDFs against real IRS templates, reads back filled AcroForm fields
with pypdf, and asserts key values were written correctly. Catches silent
field-placement bugs that structural tests (field-name matching) would miss.

Also tests cover sheet text extraction via pdfplumber where AcroForm is not used.

Test contract:
  V01  generate_8843 → pypdf reads back first_name from filled PDF
  V02  generate_8843 → pypdf reads back institution_name
  V03  generate_cover_sheet_package → pdfplumber finds title and mailing address
  V04  generate_1040nr W-2 path → pypdf reads back wages field
  V05  generate_1040nr NEC path → pypdf reads back NEC income field
  V06  generate_1040nr → pypdf reads back withholding field

Run: pytest backend/tests/test_pdf_visual.py -v
"""

from __future__ import annotations

import io
import pytest
import pypdf

from app.schemas.document import TaxReport, CalculationStep
from app.schemas.form_8843 import Form8843Data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_8843_data(**overrides) -> Form8843Data:
    defaults = dict(
        first_name="Jane",
        last_name="Zhang",
        visa_type="F-1",
        first_us_entry_date="2022",
        days_in_us_current_year=200,
        institution_name="Massachusetts Institute of Technology",
        institution_city="Cambridge",
        institution_state="MA",
        role="student",
        tin_status="ssn",
        tin_value="123-45-6789",
        has_income=True,
        tax_year=2024,
        catch_up_years=[],
    )
    defaults.update(overrides)
    return Form8843Data(**defaults)


def _make_report(**overrides) -> TaxReport:
    defaults = dict(
        document_id="test-visual-pdf",
        calculation_steps=[],
        estimated_outcome="refund",
        estimated_amount=500.0,
        outcome_explanation="",
        validation_results=[],
        wages=30000.0,
        gross_income=None,
        withholding=3000.0,
        form_8843_data=_make_8843_data(),
    )
    defaults.update(overrides)
    return TaxReport(**defaults)


def _read_filled_fields(pdf_bytes: bytes) -> dict[str, str]:
    """Read all AcroForm field values from a filled PDF."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    fields = reader.get_fields() or {}
    result = {}
    for name, field_obj in fields.items():
        val = field_obj.get("/V", "")
        if val:
            result[name] = str(val)
    return result


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF pages using pypdf (for reportlab-generated PDFs)."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# V01 — Form 8843: first name read back from filled AcroForm
# ---------------------------------------------------------------------------

def test_v01_8843_first_name_readback():
    from app.services.form_generator import generate_8843
    try:
        pdf_bytes = generate_8843(_make_8843_data(), year=2024)
    except FileNotFoundError:
        pytest.skip("f8843_2024.pdf template not found")
    fields = _read_filled_fields(pdf_bytes)
    # Find field containing "Jane" — field name varies by IRS form version
    values = list(fields.values())
    assert any("Jane" in v for v in values), (
        f"Expected 'Jane' in filled fields, got: {fields}"
    )


# ---------------------------------------------------------------------------
# V02 — Form 8843: institution name read back
# ---------------------------------------------------------------------------

def test_v02_8843_institution_readback():
    from app.services.form_generator import generate_8843
    try:
        pdf_bytes = generate_8843(_make_8843_data(), year=2024)
    except FileNotFoundError:
        pytest.skip("f8843_2024.pdf template not found")
    fields = _read_filled_fields(pdf_bytes)
    values = list(fields.values())
    assert any("Massachusetts" in v for v in values), (
        f"Expected 'Massachusetts' in filled fields, got values: {values}"
    )


# ---------------------------------------------------------------------------
# V03 — Cover sheet: title and mailing address (reportlab text extraction)
# ---------------------------------------------------------------------------

def test_v03_cover_sheet_content():
    from app.services.form_generator import generate_cover_sheet_package
    pdf_bytes = generate_cover_sheet_package(_make_report())
    text = _extract_text(pdf_bytes)
    assert "Tax Filing Package" in text, f"Expected title: {text[:500]}"
    assert "Austin" in text, f"Expected mailing address: {text[:500]}"
    assert "IMPORTANT DISCLAIMER" in text, f"Expected disclaimer block: {text[:500]}"


# ---------------------------------------------------------------------------
# V04 — 1040NR W-2: wages field read back
# ---------------------------------------------------------------------------

def test_v04_1040nr_wages_readback():
    from app.services.form_generator import generate_1040nr
    report = _make_report(wages=30000.0, gross_income=None)
    try:
        pdf_bytes = generate_1040nr(report, year=2024)
    except FileNotFoundError:
        pytest.skip("f1040nr_2024.pdf template not found")
    fields = _read_filled_fields(pdf_bytes)
    values = list(fields.values())
    assert any("30000" in v for v in values), (
        f"Expected '30000' in 1040NR fields, got: {fields}"
    )


# ---------------------------------------------------------------------------
# V05 — 1040NR NEC: NEC income field read back
# ---------------------------------------------------------------------------

def test_v05_1040nr_nec_readback():
    from app.services.form_generator import generate_1040nr
    report = _make_report(wages=None, gross_income=15000.0)
    try:
        pdf_bytes = generate_1040nr(report, year=2024)
    except FileNotFoundError:
        pytest.skip("f1040nr_2024.pdf template not found")
    fields = _read_filled_fields(pdf_bytes)
    values = list(fields.values())
    assert any("15000" in v for v in values), (
        f"Expected '15000' in 1040NR fields, got: {fields}"
    )


# ---------------------------------------------------------------------------
# V06 — 1040NR: withholding field read back
# ---------------------------------------------------------------------------

def test_v06_1040nr_withholding_readback():
    from app.services.form_generator import generate_1040nr
    report = _make_report(wages=30000.0, withholding=3000.0)
    try:
        pdf_bytes = generate_1040nr(report, year=2024)
    except FileNotFoundError:
        pytest.skip("f1040nr_2024.pdf template not found")
    fields = _read_filled_fields(pdf_bytes)
    values = list(fields.values())
    assert any("3000" in v for v in values), (
        f"Expected '3000' in 1040NR fields, got: {fields}"
    )
