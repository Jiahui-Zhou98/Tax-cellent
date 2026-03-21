import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.config import settings
from app.schemas.document import OCROutput, SessionState
from app.services.pdf_parser import extract_structured
from app.services.extraction_service import (
    extract_fields_structured,
    extract_fields_llm,
    extract_fields,
)
from app.storage.session_store import save_session

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


@router.post("/upload", response_model=OCROutput)
async def upload_document(file: UploadFile = File(...)):
    # Validate
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")

    # Save to disk
    document_id = str(uuid.uuid4())
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text + structured JSON
    try:
        raw_text, parsed_json, page_count = await extract_structured(file_path)
    except Exception as e:
        raise HTTPException(422, f"Failed to extract text: {e}")

    if not raw_text.strip():
        raise HTTPException(422, "Could not extract any text from the document")

    # Field extraction — prefer structured pipeline, fall back to legacy LLM, then regex
    field_candidates = None

    if parsed_json is not None:
        try:
            field_candidates = await extract_fields_structured(parsed_json)
            logger.info("upload: structured extraction succeeded (%d fields)", len(field_candidates))
        except Exception as e:
            logger.warning("upload: structured extraction failed (%s), trying legacy LLM", e)

    if field_candidates is None:
        try:
            field_candidates = await extract_fields_llm(raw_text)
            logger.info("upload: legacy LLM extraction succeeded (%d fields)", len(field_candidates))
        except Exception as e:
            logger.warning("upload: legacy LLM failed (%s), falling back to regex", e)
            field_candidates = extract_fields(raw_text)
            logger.info("upload: regex fallback used (%d fields)", len(field_candidates))

    ocr_output = OCROutput(
        document_id=document_id,
        raw_text=raw_text,
        field_candidates=field_candidates,
        page_count=page_count,
    )

    session = SessionState(
        document_id=document_id,
        filename=file.filename or "document",
        file_path=file_path,
        ocr_output=ocr_output,
        status="ocr_done",
    )
    save_session(session)

    return ocr_output
