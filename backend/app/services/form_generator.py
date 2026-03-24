"""Form 8843 PDF generator.

Strategy
--------
1. Primary: fill named AcroForm widgets with pypdf (zero visual change to the
   official IRS layout).
2. Fallback: if the downloaded PDF has no AcroForm layer (scanned / flat),
   overlay text at hardcoded coordinates via reportlab.
3. The EXPECTED_FIELDS set is checked at import time; a missing field logs a
   WARNING rather than crashing — the fallback silently takes over.

Public API
----------
    generate_8843(data, year)  → bytes  (single PDF)
    bundle_pdfs(pdfs)          → bytes  (concatenated multi-page PDF)
    generate_cover_sheet(data_list) → bytes  (plain summary page)

Dependencies (already in requirements.txt):
    pypdf >= 4.0, reportlab >= 4.0
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

from app.constants.form_8843_fields import (
    COORD_FALLBACK,
    EXPECTED_FIELDS_BY_YEAR,
    FIELD_MAPS,
    FIELD_MAP,        # default (2025) — kept for backward compat
    EXPECTED_FIELDS,  # default (2025) — kept for backward compat
)
from app.schemas.form_8843 import Form8843Data

logger = logging.getLogger(__name__)

FORMS_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "forms"

# Cache: year -> (pypdf.PdfReader, bool has_acroform)
_pdf_fields_cache: dict[int, tuple[object, bool]] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_template(year: int):
    """Return (PdfReader, has_acroform).  Cached after first load."""
    if year in _pdf_fields_cache:
        return _pdf_fields_cache[year]

    try:
        import pypdf  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("pypdf is required for PDF generation: pip install pypdf") from e

    path = FORMS_DIR / f"f8843_{year}.pdf"
    if not path.exists():
        raise FileNotFoundError(
            f"IRS Form 8843 template not found: {path}\n"
            "Run: scripts/fetch_irs_forms.sh"
        )

    reader = pypdf.PdfReader(str(path))
    fields = reader.get_fields() or {}
    has_acroform = bool(fields)

    if has_acroform:
        actual = set(fields.keys())
        expected_for_year = EXPECTED_FIELDS_BY_YEAR.get(year, EXPECTED_FIELDS)
        missing = expected_for_year - actual
        if missing:
            logger.warning(
                "Form 8843 (%d): %d expected AcroForm fields are missing from PDF. "
                "Falling back to coordinate overlay for those fields. "
                "Missing: %s",
                year, len(missing), sorted(missing)[:10],
            )
            has_acroform = False  # treat as flat — safer than partial fill

    _pdf_fields_cache[year] = (reader, has_acroform)
    return reader, has_acroform


def _build_field_values(data: Form8843Data) -> dict[str, str]:
    """Map Form8843Data fields to semantic keys used in FIELD_MAP_*."""
    full_name_sign = f"{data.first_name} {data.last_name}".strip()
    tin_display = ""
    if data.tin_value:
        tin_display = data.tin_value
    elif data.tin_status == "applied_for":
        tin_display = "Applied For"
    elif data.tin_status == "none":
        tin_display = "None"

    prior_years_str = ", ".join(str(y) for y in sorted(data.exempt_prior_years)) if data.exempt_prior_years else ""

    return {
        "last_name":              data.last_name,
        "first_name_mi":          data.first_name,
        "tin":                    tin_display,
        "visa_type":              data.visa_type,
        "date_arrived":           data.first_us_entry_date or "",
        "days_us_current":        str(data.days_in_us_current_year) if data.days_in_us_current_year is not None else "",
        "institution_name":       data.institution_name or "",
        "institution_city":       data.institution_city or "",   # separate city field
        "institution_state":      data.institution_state or "",  # separate state field
        "prior_exempt_years":     prior_years_str,
        "exchange_program":       data.exchange_program_name or "",
        "sponsor_name":           data.sponsor_name or "",
        "sponsor_address":        data.sponsor_address or "",
        "taxpayer_name_sign":     full_name_sign,
        "sign_date":              f"{data.tax_year}-04-15",
    }


# ---------------------------------------------------------------------------
# Primary path: pypdf AcroForm fill
# ---------------------------------------------------------------------------

def _fill_acroform(reader, field_values: dict[str, str], year: int) -> bytes:
    """Fill named AcroForm widgets and return flattened PDF bytes.

    Uses the year-specific FIELD_MAP so short field names like ``f1_01[0]``
    match annotation ``/T`` attributes correctly.
    """
    import pypdf  # noqa: PLC0415

    field_map = FIELD_MAPS.get(year, FIELD_MAP)

    writer = pypdf.PdfWriter()
    writer.clone_reader_document_root(reader)

    # Build annotation-local-name -> value dict using year-specific FIELD_MAP
    pdf_fields: dict[str, str] = {}
    for semantic_key, pdf_field_name in field_map.items():
        if semantic_key in field_values and field_values[semantic_key]:
            pdf_fields[pdf_field_name] = field_values[semantic_key]

    writer.update_page_form_field_values(
        writer.pages[0],
        pdf_fields,
        auto_regenerate=False,
    )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fallback path: reportlab coordinate overlay
# ---------------------------------------------------------------------------

def _fill_coordinates(source_pdf_bytes: bytes, field_values: dict[str, str]) -> bytes:
    """Overlay text at hardcoded coordinates on top of a flat PDF."""
    try:
        from reportlab.lib.pagesizes import letter  # noqa: PLC0415
        from reportlab.pdfgen import canvas  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("reportlab is required for coordinate overlay: pip install reportlab") from e

    import pypdf  # noqa: PLC0415

    # Build an overlay PDF with just the text
    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=letter)
    c.setFont("Helvetica", 10)
    for semantic_key, (x, y, _width, font_size) in COORD_FALLBACK.items():
        text = field_values.get(semantic_key, "")
        if text:
            c.setFont("Helvetica", font_size)
            c.drawString(x, y, text)
    c.save()
    overlay_buf.seek(0)

    # Merge overlay onto the source PDF
    overlay_reader = pypdf.PdfReader(overlay_buf)
    source_reader = pypdf.PdfReader(io.BytesIO(source_pdf_bytes))
    writer = pypdf.PdfWriter()
    source_page = source_reader.pages[0]
    source_page.merge_page(overlay_reader.pages[0])
    writer.add_page(source_page)
    # Copy remaining pages (if any) unmodified
    for i in range(1, len(source_reader.pages)):
        writer.add_page(source_reader.pages[i])

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_8843(data: Form8843Data, year: Optional[int] = None) -> bytes:
    """Generate a filled IRS Form 8843 PDF for the given year.

    Returns PDF bytes ready to send as an HTTP response or include in a bundle.
    Raises FileNotFoundError if the template PDF has not been downloaded yet.
    """
    target_year = year or data.tax_year

    reader, has_acroform = _get_template(target_year)
    field_values = _build_field_values(data)

    if has_acroform:
        logger.debug("generate_8843: using AcroForm fill for year %d", target_year)
        return _fill_acroform(reader, field_values, target_year)

    # Fallback: read raw bytes from the template file for coordinate overlay
    logger.debug("generate_8843: using coordinate overlay for year %d", target_year)
    template_path = FORMS_DIR / f"f8843_{target_year}.pdf"
    raw_bytes = template_path.read_bytes()
    return _fill_coordinates(raw_bytes, field_values)


def bundle_pdfs(pdfs: list[bytes]) -> bytes:
    """Concatenate multiple PDFs into a single multi-page PDF."""
    try:
        import pypdf  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("pypdf is required for bundling: pip install pypdf") from e

    writer = pypdf.PdfWriter()
    for pdf_bytes in pdfs:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def generate_cover_sheet(data_list: list[Form8843Data]) -> bytes:
    """Generate a plain-text summary cover page listing all bundled forms."""
    try:
        from reportlab.lib.pagesizes import letter  # noqa: PLC0415
        from reportlab.pdfgen import canvas  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("reportlab is required for cover sheet: pip install reportlab") from e

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, height - 72, "Form 8843 Bundle — Cover Sheet")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 92, "Generated by Tax-cellent")

    y = height - 130
    for i, data in enumerate(data_list, 1):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(72, y, f"Form {i}: Tax Year {data.tax_year}")
        y -= 16
        c.setFont("Helvetica", 10)
        name = f"{data.first_name} {data.last_name}".strip()
        c.drawString(90, y, f"Name: {name}")
        y -= 14
        c.drawString(90, y, f"Visa: {data.visa_type}   Institution: {data.institution_name or '—'}")
        y -= 14
        has_income_str = "Yes (attach to 1040-NR)" if data.has_income else "No (standalone, mail to Austin TX)"
        c.drawString(90, y, f"Has income: {has_income_str}")
        y -= 22
        if y < 80:
            c.showPage()
            y = height - 72

    c.save()
    buf.seek(0)
    return buf.getvalue()
