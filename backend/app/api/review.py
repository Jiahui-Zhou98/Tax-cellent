from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.document import (
    ConfirmedFields, ValidationOutput, FieldValue,
    UserContext, TaxReport,
)
from app.services.validation_service import validate
from app.services.tax_advisor import run_tax_analysis
from app.storage.session_store import load_session, save_session

router = APIRouter()


class ConfirmRequest(BaseModel):
    document_id: str
    confirmed_fields: dict[str, dict]
    unresolved_fields: list[str] = []


@router.post("/context/{document_id}")
async def save_context(document_id: str, context: UserContext):
    try:
        session = load_session(document_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    session.user_context = context
    save_session(session)
    return {"status": "ok"}


@router.post("/confirm", response_model=ValidationOutput)
async def confirm_fields(req: ConfirmRequest):
    try:
        session = load_session(req.document_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    parsed = {}
    for fname, fdata in req.confirmed_fields.items():
        parsed[fname] = FieldValue(
            value=fdata.get("value"),
            confidence=fdata.get("confidence", 1.0),
            source=fdata.get("source", "user_confirmed"),
        )

    confirmed = ConfirmedFields(
        document_id=req.document_id,
        confirmed_fields=parsed,
        unresolved_fields=req.unresolved_fields,
    )

    validation = validate(confirmed)

    session.confirmed_fields = confirmed
    session.validation_output = validation
    session.status = "validated"
    save_session(session)

    return validation


@router.post("/analyze/{document_id}", response_model=TaxReport)
async def analyze_document(document_id: str):
    try:
        session = load_session(document_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if not session.confirmed_fields:
        raise HTTPException(400, "Fields must be confirmed before analysis")

    confirmed = session.confirmed_fields
    validation = session.validation_output or ValidationOutput(status="ok")
    user_context = session.user_context

    session.status = "analyzing"
    save_session(session)

    try:
        report = await run_tax_analysis(confirmed, validation, user_context)
    except Exception as e:
        raise HTTPException(502, f"Analysis failed: {str(e)}")

    session.tax_report = report
    session.status = "complete"
    save_session(session)

    return report


@router.get("/session/{document_id}")
async def get_session(document_id: str):
    try:
        session = load_session(document_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    return session
