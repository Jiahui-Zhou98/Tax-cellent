"""Forms API — generate and bundle IRS Form 8843 and 1040NR PDFs.

Endpoints
---------
POST /api/forms/8843/generate
    Body: Form8843GenerateRequest
    Returns: application/pdf

POST /api/forms/bundle
    Body: Form8843BundleRequest  (multiple years / catch-up filing)
    Returns: application/pdf (multi-page bundle with cover sheet)

POST /api/forms/package
    Body: { document_id: str }
    Returns: application/pdf (cover sheet + 1040NR + optional Form 8843)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.schemas.form_8843 import Form8843Data
from app.services.form_generator import (
    bundle_pdfs,
    generate_8843,
    generate_cover_sheet,
    generate_1040nr,
    generate_cover_sheet_package,
)
from app.storage.session_store import load_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class Form8843GenerateRequest(BaseModel):
    data: Form8843Data
    year: Optional[int] = None  # override data.tax_year if provided


class TaxPackageRequest(BaseModel):
    document_id: str


class Form8843BundleRequest(BaseModel):
    """Bundle one Form 8843 per year (catch-up filing).

    `years` is ignored when `data_per_year` is provided; otherwise a copy of
    `base_data` is generated for each year in `years` with tax_year overridden.
    """
    base_data: Form8843Data
    years: list[int] = []                    # used when data_per_year is empty
    data_per_year: list[Form8843Data] = []   # one entry per year, full override
    include_cover_sheet: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/forms/8843/generate")
async def generate_form_8843(req: Form8843GenerateRequest) -> Response:
    """Generate a single filled IRS Form 8843 PDF."""
    try:
        pdf_bytes = generate_8843(req.data, year=req.year)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Form 8843 template not available. {e}",
        )
    except Exception as e:
        logger.exception("generate_form_8843 failed")
        raise HTTPException(status_code=500, detail=str(e))

    year = req.year or req.data.tax_year
    filename = f"f8843_{year}_{req.data.last_name.lower() or 'form'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/forms/bundle")
async def bundle_forms(req: Form8843BundleRequest) -> Response:
    """Generate a multi-PDF bundle (one form per year) with optional cover sheet."""
    # Resolve per-year data list
    if req.data_per_year:
        data_list = req.data_per_year
    elif req.years:
        data_list = []
        for yr in sorted(req.years):
            overridden = req.base_data.model_copy(update={"tax_year": yr, "catch_up_years": []})
            data_list.append(overridden)
    else:
        # Fall back to a single form for the base year
        data_list = [req.base_data]

    if not data_list:
        raise HTTPException(status_code=422, detail="No years provided for bundle.")

    # Generate each form
    pdf_parts: list[bytes] = []
    errors: list[str] = []
    for entry in data_list:
        try:
            pdf_parts.append(generate_8843(entry, year=entry.tax_year))
        except FileNotFoundError as e:
            errors.append(str(e))
        except Exception as e:
            logger.exception("bundle: failed to generate form for year %d", entry.tax_year)
            errors.append(f"Year {entry.tax_year}: {e}")

    if not pdf_parts:
        raise HTTPException(
            status_code=503,
            detail="No PDFs generated. " + "; ".join(errors),
        )

    # Prepend cover sheet if requested
    if req.include_cover_sheet:
        try:
            cover = generate_cover_sheet(data_list[: len(pdf_parts)])
            pdf_parts = [cover] + pdf_parts
        except Exception:
            logger.warning("bundle: cover sheet generation failed, skipping", exc_info=True)

    bundled = bundle_pdfs(pdf_parts)

    name_slug = (data_list[0].last_name or "forms").lower()
    years_str = "_".join(str(d.tax_year) for d in data_list[:4])
    if len(data_list) > 4:
        years_str += "_etc"
    filename = f"f8843_bundle_{years_str}_{name_slug}.pdf"

    return Response(
        content=bundled,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/forms/package")
async def generate_tax_package(req: TaxPackageRequest) -> Response:
    """Generate a complete tax filing package for NRA students.

    Bundle contents (in order):
      1. Cover sheet with filing instructions
      2. IRS Form 1040NR (filled)
      3. IRS Form 8843 (filled, only when form_8843_data is present)

    Requires a completed tax analysis (session.tax_report must be set).
    """
    try:
        session = load_session(req.document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.tax_report is None:
        raise HTTPException(
            status_code=422,
            detail="Tax analysis not yet complete. Run /api/analyze first.",
        )

    report = session.tax_report

    # Collect PDF parts: cover sheet first, then forms
    pdf_parts: list[bytes] = []

    # 1. Cover sheet
    try:
        pdf_parts.append(generate_cover_sheet_package(report))
    except Exception:
        logger.warning("package: cover sheet generation failed, skipping", exc_info=True)

    # 2. Form 1040NR
    try:
        pdf_parts.append(generate_1040nr(report))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Form 1040NR template not available. {e}")
    except Exception as e:
        logger.exception("package: 1040NR generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Form 8843 (only for NRA filers who have 8843 data)
    if report.form_8843_data is not None:
        try:
            pdf_parts.append(generate_8843(report.form_8843_data))
        except FileNotFoundError as e:
            logger.warning("package: Form 8843 template not available — skipping: %s", e)
        except Exception:
            logger.warning("package: Form 8843 generation failed, skipping", exc_info=True)

    if not pdf_parts:
        raise HTTPException(status_code=500, detail="PDF generation failed for all package components.")

    bundled = bundle_pdfs(pdf_parts)

    tax_year = (report.form_8843_data.tax_year if report.form_8843_data else 2024)
    filename = f"tax-package-{tax_year}.pdf"

    return Response(
        content=bundled,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
