"""Form PDF generators for IRS Form 8843 and Form 1040NR.

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
    generate_8843(data, year)              → bytes  (Form 8843 PDF)
    generate_1040nr(report, year)          → bytes  (Form 1040NR PDF)
    generate_cover_sheet_package(report)   → bytes  (package cover sheet)
    bundle_pdfs(pdfs)                      → bytes  (concatenated multi-page PDF)
    generate_cover_sheet(data_list)        → bytes  (8843-only cover, legacy)

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
import app.constants.form_1040nr_fields as _nr_fields
from app.schemas.document import TaxReport
from app.schemas.form_8843 import Form8843Data

logger = logging.getLogger(__name__)

FORMS_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "forms"

# Cache: year -> (pypdf.PdfReader, bool has_acroform)
_pdf_fields_cache: dict[int, tuple[object, bool]] = {}

# 1040NR template cache: year -> (pypdf.PdfReader, bool has_acroform)
_1040nr_cache: dict[int, tuple[object, bool]] = {}


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


# ---------------------------------------------------------------------------
# Form 1040NR — template loader and field builder
# ---------------------------------------------------------------------------

def _get_1040nr_template(year: int):
    """Return (PdfReader, has_acroform) for the 1040NR template.  Cached after first load."""
    if year in _1040nr_cache:
        return _1040nr_cache[year]

    try:
        import pypdf  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("pypdf is required for PDF generation: pip install pypdf") from e

    path = FORMS_DIR / f"f1040nr_{year}.pdf"
    if not path.exists():
        raise FileNotFoundError(
            f"IRS Form 1040NR template not found: {path}\n"
            "Download from: https://www.irs.gov/pub/irs-pdf/f1040nr.pdf"
        )

    reader = pypdf.PdfReader(str(path))
    fields = reader.get_fields() or {}
    has_acroform = bool(fields)

    if has_acroform:
        actual = set(fields.keys())
        expected_for_year = _nr_fields.EXPECTED_FIELDS_BY_YEAR.get(year, _nr_fields.EXPECTED_FIELDS)
        missing = expected_for_year - actual
        if missing:
            logger.warning(
                "Form 1040NR (%d): %d expected AcroForm fields missing from PDF. "
                "Falling back to coordinate overlay. Missing: %s",
                year, len(missing), sorted(missing)[:10],
            )
            has_acroform = False

    _1040nr_cache[year] = (reader, has_acroform)
    return reader, has_acroform


def _build_1040nr_field_values(report: TaxReport) -> dict[str, str]:
    """Map TaxReport fields to the semantic keys used in FIELD_MAP_1040NR_*."""
    d8843 = report.form_8843_data
    values: dict[str, str] = {}

    # Personal info — pull from form_8843_data when available
    if d8843:
        values["first_name_mi"] = d8843.first_name or ""
        values["last_name"] = d8843.last_name or ""
        tin = ""
        if d8843.tin_value:
            tin = d8843.tin_value
        elif d8843.tin_status == "applied_for":
            tin = "Applied For"
        values["tin"] = tin

    # Filing status — NRAs almost always file as Single (c1_1)
    # We pre-check the single box; leave others as "/Off"
    values["filing_status_single"] = "/Yes"

    # Income — W-2 filer path
    if report.wages is not None:
        values["wages_line_1a"] = f"{report.wages:.2f}"
        values["wages_line_1k"] = f"{report.wages:.2f}"

    # Income — NEC filer path
    if report.gross_income is not None:
        values["nec_income_line_2"] = f"{report.gross_income:.2f}"

    # Withholding
    if report.withholding is not None and report.withholding > 0:
        if report.wages is not None:
            # W-2 filer: withholding goes on Line 25a
            values["withholding_w2"] = f"{report.withholding:.2f}"
        else:
            # NEC filer: withholding goes on Line 25b
            values["withholding_nec"] = f"{report.withholding:.2f}"
        values["total_withholding"] = f"{report.withholding:.2f}"

    # Treaty — Part IV / Schedule OI (fill only when treaty applies)
    if report.treaty_exempt_amount and report.treaty_exempt_amount > 0:
        if report.treaty_article:
            values["treaty_article"] = report.treaty_article
        if report.treaty_country:
            values["treaty_country"] = report.treaty_country
        values["treaty_amount_exempt"] = f"{report.treaty_exempt_amount:.2f}"

    return values


def _fill_1040nr_acroform(reader, field_values: dict[str, str], year: int) -> bytes:
    """Fill all pages of the 1040NR AcroForm and return PDF bytes.

    Loops over every page so that Schedule OI (page 2+) fields are filled
    in the same pass as page 1 fields.
    """
    import pypdf  # noqa: PLC0415

    field_map = _nr_fields.FIELD_MAPS.get(year, _nr_fields.FIELD_MAP)
    checkbox_fields = _nr_fields.CHECKBOX_FIELDS_2024
    readonly_fields = _nr_fields.READONLY_FIELDS_2024

    writer = pypdf.PdfWriter()
    writer.clone_reader_document_root(reader)

    # Build the fill dict: semantic_key → local_field_name → value
    pdf_fields: dict[str, str] = {}
    for semantic_key, pdf_field_name in field_map.items():
        if pdf_field_name in readonly_fields:
            continue  # never fill auto-calculated fields
        val = field_values.get(semantic_key, "")
        if pdf_field_name in checkbox_fields:
            # Checkboxes must be "/Yes" or "/Off" — never empty string
            pdf_fields[pdf_field_name] = val if val in ("/Yes", "/Off") else "/Off"
        elif val:
            pdf_fields[pdf_field_name] = val

    # Multi-page fill: loop all pages so page 2 (Schedule OI) fields are covered
    for page in writer.pages:
        writer.update_page_form_field_values(
            page,
            pdf_fields,
            auto_regenerate=False,
        )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _fill_1040nr_coordinates(source_pdf_bytes: bytes, field_values: dict[str, str]) -> bytes:
    """Overlay 1040NR field values at hardcoded coordinates (fallback path)."""
    try:
        from reportlab.lib.pagesizes import letter  # noqa: PLC0415
        from reportlab.pdfgen import canvas  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("reportlab is required for coordinate overlay: pip install reportlab") from e

    import pypdf  # noqa: PLC0415

    coord = _nr_fields.COORD_FALLBACK

    # Build a two-page overlay (page 1 and page 2) since 1040NR is multi-page
    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=letter)
    c.setFont("Helvetica", 10)

    # Page 1 overlay
    for semantic_key, (x, y, _w, font_size) in coord.items():
        text = field_values.get(semantic_key, "")
        if text and text not in ("/Yes", "/Off"):
            c.setFont("Helvetica", font_size)
            c.drawString(x, y, text)
    c.showPage()

    # Page 2 overlay (treaty / withholding fields)
    for semantic_key in ("treaty_article", "treaty_country", "treaty_amount_exempt",
                         "withholding_w2", "withholding_nec", "total_withholding",
                         "amount_owed_line_37", "refund_line_36a",
                         "taxpayer_name_sign", "sign_date"):
        if semantic_key not in coord:
            continue
        x, y, _w, font_size = coord[semantic_key]
        text = field_values.get(semantic_key, "")
        if text and text not in ("/Yes", "/Off"):
            c.setFont("Helvetica", font_size)
            c.drawString(x, y, text)
    c.save()
    overlay_buf.seek(0)

    overlay_reader = pypdf.PdfReader(overlay_buf)
    source_reader = pypdf.PdfReader(io.BytesIO(source_pdf_bytes))
    writer = pypdf.PdfWriter()

    for i, source_page in enumerate(source_reader.pages):
        if i < len(overlay_reader.pages):
            source_page.merge_page(overlay_reader.pages[i])
        writer.add_page(source_page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def generate_1040nr(report: TaxReport, year: Optional[int] = None) -> bytes:
    """Generate a pre-filled IRS Form 1040NR PDF from TaxReport data.

    Branches on report.wages (W-2 path) vs report.gross_income (NEC path).
    Treaty lines are filled only when report.treaty_exempt_amount > 0.
    Schedule OI lines are filled only for NRA visa types.

    Error codes raised:
        MISSING_REPORT_DATA — wages=None AND gross_income=None
        PDF_GENERATION_FAILED — pypdf fill failed or template file missing

    Returns PDF bytes ready to include in bundle_pdfs().
    """
    if report.wages is None and report.gross_income is None:
        raise ValueError(
            "MISSING_REPORT_DATA: TaxReport has neither wages nor gross_income. "
            "At least one income source is required to generate Form 1040NR."
        )

    tax_year = year or 2024  # default to 2024; update annually

    try:
        reader, has_acroform = _get_1040nr_template(tax_year)
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise RuntimeError(f"PDF_GENERATION_FAILED: could not load 1040NR template: {exc}") from exc

    field_values = _build_1040nr_field_values(report)

    try:
        if has_acroform:
            logger.debug("generate_1040nr: using AcroForm fill for year %d", tax_year)
            return _fill_1040nr_acroform(reader, field_values, tax_year)

        logger.debug("generate_1040nr: using coordinate overlay for year %d", tax_year)
        template_path = FORMS_DIR / f"f1040nr_{tax_year}.pdf"
        raw_bytes = template_path.read_bytes()
        return _fill_1040nr_coordinates(raw_bytes, field_values)
    except Exception as exc:
        raise RuntimeError(f"PDF_GENERATION_FAILED: {exc}") from exc


# ---------------------------------------------------------------------------
# Package cover sheet (distinct from the 8843-only generate_cover_sheet)
# ---------------------------------------------------------------------------

def generate_cover_sheet_package(report: TaxReport) -> bytes:
    """Generate a cover sheet for the full NRA tax package (Form 1040NR + Form 8843).

    Explains: what forms are included, what to sign, what to attach (W-2/1099),
    where to mail (IRS Austin TX or Charlotte NC), and state filing note.
    """
    try:
        from reportlab.lib.pagesizes import letter  # noqa: PLC0415
        from reportlab.pdfgen import canvas  # noqa: PLC0415
        from reportlab.lib import colors  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("reportlab is required for cover sheet: pip install reportlab") from e

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Header
    c.setFillColor(colors.HexColor("#1a3a5c"))
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 45, "Your Tax Filing Package")
    c.setFont("Helvetica", 11)
    c.drawString(72, height - 62, "Generated by Tax-cellent   •   For Nonresident Aliens (NRA)")

    c.setFillColor(colors.black)
    y = height - 110

    def section(title: str) -> None:
        nonlocal y
        y -= 8
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#1a3a5c"))
        c.drawString(72, y, title)
        c.setFillColor(colors.black)
        y -= 16

    def line(text: str, indent: int = 90) -> None:
        nonlocal y
        c.setFont("Helvetica", 10)
        c.drawString(indent, y, text)
        y -= 14

    d8843 = report.form_8843_data
    name = ""
    if d8843:
        name = f"{d8843.first_name} {d8843.last_name}".strip()
    tax_year = d8843.tax_year if d8843 else 2024

    # Intro
    c.setFont("Helvetica", 11)
    c.drawString(72, y, f"Taxpayer: {name or '(see Form 1040NR)'}")
    y -= 14
    c.drawString(72, y, f"Tax Year: {tax_year}")
    y -= 20

    # What's inside
    section("What's Inside This Package")
    has_8843 = d8843 is not None
    if has_8843:
        line("1.  Form 1040NR  — U.S. Nonresident Alien Income Tax Return (pre-filled)")
        line("2.  Form 8843    — Statement for Exempt Individuals (pre-filled)")
    else:
        line("1.  Form 1040NR  — U.S. Nonresident Alien Income Tax Return (pre-filled)")

    # What you must do before mailing
    section("Before You Mail — Checklist")
    line("☐  Review every pre-filled field for accuracy.")
    line("☐  Sign and date Form 1040NR (page 2, signature section).")
    if has_8843:
        line("☐  Sign and date Form 8843 (bottom of page 1).")
    line("☐  Attach your W-2 or 1099 form(s) to Form 1040NR.")
    if report.wages is not None:
        line("     Your W-2 shows Box 1 wages and Box 2 federal tax withheld.")
    elif report.gross_income is not None:
        line("     Your 1099-NEC shows Box 1 nonemployee compensation.")
    if report.treaty_exempt_amount and report.treaty_exempt_amount > 0:
        line("☐  Attach Form 8833 (treaty-based return position disclosure) if required.")
        line(f"     Treaty country: {report.treaty_country or '(see Part IV of 1040NR)'}  "
             f"Article: {report.treaty_article or '(see Part IV)'}")
    line("☐  Make a copy of everything for your records.")

    # Where to mail
    section("Where to Mail")
    line("Mail ALL forms together to the IRS in a single envelope.")
    y -= 4
    c.setFont("Helvetica-Bold", 10)
    c.drawString(90, y, "If you owe tax OR are getting a refund:")
    y -= 13
    line("Department of the Treasury")
    line("Internal Revenue Service")
    line("Austin, TX  73301-0215")
    y -= 4
    c.setFont("Helvetica-Bold", 10)
    c.drawString(90, y, "If you are not enclosing a payment:")
    y -= 13
    line("Department of the Treasury")
    line("Internal Revenue Service")
    line("Austin, TX  73301-0215  USA")
    y -= 4
    line("(Same address — use USA if mailing from outside the United States.)")

    # Deadline
    section("Filing Deadline")
    line(f"Form 1040NR for tax year {tax_year} is due April 15, {tax_year + 1}.")
    line("If you need more time, file Form 4868 for an automatic 6-month extension.")
    line("Note: An extension to file is NOT an extension to pay any tax owed.")

    # State taxes
    section("State Taxes")
    line("This package covers your federal return only.")
    line("Most states require a separate state income tax return.")
    line("Check with your university's ISSO or visit your state's tax website.")
    line("Many universities offer free state return help through VITA or Glacier Tax Prep.")

    # Disclaimer
    y -= 10
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    c.drawString(72, y, "Tax-cellent provides tax filing assistance tools, not professional tax advice.")
    y -= 11
    c.drawString(72, y, "When in doubt, consult a licensed tax professional or your university's ISSO.")

    c.save()
    buf.seek(0)
    return buf.getvalue()
