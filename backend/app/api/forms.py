"""Forms API — generate and bundle IRS Form 8843 PDFs.

Endpoints
---------
POST /api/forms/8843/generate
    Body: Form8843GenerateRequest
    Returns: application/pdf

POST /api/forms/bundle
    Body: Form8843BundleRequest  (multiple years / catch-up filing)
    Returns: application/pdf (multi-page bundle with cover sheet)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.schemas.form_8843 import Form8843Data
from app.services.form_generator import bundle_pdfs, generate_8843, generate_cover_sheet

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class Form8843GenerateRequest(BaseModel):
    data: Form8843Data
    year: Optional[int] = None  # override data.tax_year if provided


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
