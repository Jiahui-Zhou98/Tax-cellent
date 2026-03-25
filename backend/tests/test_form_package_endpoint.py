"""Tests for POST /api/forms/package endpoint.

Test contract (6 paths):
  T01  404 when document_id not found in session store
  T02  422 when session has no tax_report
  T03  Happy path (NRA W-2 filer) → PDF response with correct headers
  T04  Happy path (NRA NEC filer) → PDF response (nec_income_line_2 path)
  T05  422 when report has no income data (wages=None, gross_income=None)
  T06  Non-NRA filer (no form_8843_data) still gets 1040NR package

Run: pytest backend/tests/test_form_package_endpoint.py -v
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest


pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.document import SessionState, TaxReport
from app.schemas.form_8843 import Form8843Data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tax_report(**overrides) -> TaxReport:
    defaults = dict(
        document_id="test-pkg-doc",
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


def _make_session(tax_report=None) -> SessionState:
    return SessionState(
        document_id="test-pkg-doc",
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        tax_report=tax_report,
        status="complete",
    )


def _fake_pdf(page_count: int = 1) -> bytes:
    """Return minimal valid PDF bytes (N blank pages) using pypdf."""
    try:
        import pypdf
    except ImportError:
        return b"%PDF-1.4\n%%EOF\n"
    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# T01 — 404 when document not found
# ---------------------------------------------------------------------------

def test_t01_package_404_session_not_found():
    client = TestClient(app)
    with patch("app.api.forms.load_session", side_effect=FileNotFoundError("not found")):
        response = client.post("/api/forms/package", json={"document_id": "nonexistent"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T02 — 422 when tax_report is None
# ---------------------------------------------------------------------------

def test_t02_package_422_no_tax_report():
    client = TestClient(app)
    session = _make_session(tax_report=None)
    with patch("app.api.forms.load_session", return_value=session):
        response = client.post("/api/forms/package", json={"document_id": "test-pkg-doc"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# T03 — Happy path: NRA W-2 filer gets PDF with correct headers
# ---------------------------------------------------------------------------

def test_t03_package_happy_path_nra_w2():
    client = TestClient(app)
    form_8843 = Form8843Data(
        first_name="Jane", last_name="Doe", visa_type="F-1", tax_year=2024
    )
    report = _make_tax_report(
        form_8843_data=form_8843,
        wages=30000.0,
        gross_income=None,
        withholding=3000.0,
    )
    session = _make_session(tax_report=report)

    fake_pdf_bytes = _fake_pdf(2)

    with patch("app.api.forms.load_session", return_value=session), \
         patch("app.api.forms.generate_cover_sheet_package", return_value=_fake_pdf(1)), \
         patch("app.api.forms.generate_1040nr", return_value=_fake_pdf(2)), \
         patch("app.api.forms.generate_8843", return_value=_fake_pdf(1)), \
         patch("app.api.forms.bundle_pdfs", return_value=fake_pdf_bytes):

        response = client.post("/api/forms/package", json={"document_id": "test-pkg-doc"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert "tax-package" in response.headers["content-disposition"]


# ---------------------------------------------------------------------------
# T04 — Happy path: NRA NEC filer (gross_income path)
# ---------------------------------------------------------------------------

def test_t04_package_happy_path_nra_nec():
    client = TestClient(app)
    form_8843 = Form8843Data(
        first_name="John", last_name="Smith", visa_type="J-1", tax_year=2024
    )
    report = _make_tax_report(
        form_8843_data=form_8843,
        wages=None,
        gross_income=12000.0,
        withholding=0.0,
    )
    session = _make_session(tax_report=report)

    fake_pdf_bytes = _fake_pdf(2)

    with patch("app.api.forms.load_session", return_value=session), \
         patch("app.api.forms.generate_cover_sheet_package", return_value=_fake_pdf(1)), \
         patch("app.api.forms.generate_1040nr", return_value=_fake_pdf(2)), \
         patch("app.api.forms.generate_8843", return_value=_fake_pdf(1)), \
         patch("app.api.forms.bundle_pdfs", return_value=fake_pdf_bytes):

        response = client.post("/api/forms/package", json={"document_id": "test-pkg-doc"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------------------
# T05 — 422 when report has no income data at all
# ---------------------------------------------------------------------------

def test_t05_package_422_no_income_data():
    client = TestClient(app)
    report = _make_tax_report(wages=None, gross_income=None, withholding=None)
    session = _make_session(tax_report=report)

    with patch("app.api.forms.load_session", return_value=session), \
         patch("app.api.forms.generate_cover_sheet_package", return_value=_fake_pdf(1)), \
         patch("app.api.forms.generate_1040nr",
               side_effect=ValueError("MISSING_REPORT_DATA: no income")):

        response = client.post("/api/forms/package", json={"document_id": "test-pkg-doc"})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# T06 — Non-NRA filer (no form_8843_data) still gets 1040NR-only package
# ---------------------------------------------------------------------------

def test_t06_package_non_nra_no_8843():
    client = TestClient(app)
    report = _make_tax_report(
        form_8843_data=None,
        wages=50000.0,
        gross_income=None,
        withholding=8000.0,
    )
    session = _make_session(tax_report=report)

    fake_pdf_bytes = _fake_pdf(2)

    with patch("app.api.forms.load_session", return_value=session), \
         patch("app.api.forms.generate_cover_sheet_package", return_value=_fake_pdf(1)), \
         patch("app.api.forms.generate_1040nr", return_value=_fake_pdf(2)), \
         patch("app.api.forms.bundle_pdfs", return_value=fake_pdf_bytes) as mock_bundle:

        response = client.post("/api/forms/package", json={"document_id": "test-pkg-doc"})

    assert response.status_code == 200
    # generate_8843 must NOT have been called (no form_8843_data)
    call_args_list = mock_bundle.call_args_list
    assert call_args_list, "bundle_pdfs should have been called"
    # The bundle call should have at most 2 parts (cover + 1040NR), not 3
    bundled_parts = mock_bundle.call_args[0][0]
    assert len(bundled_parts) == 2, (
        f"Expected 2 PDF parts (cover + 1040NR), got {len(bundled_parts)}"
    )
