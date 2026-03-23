import httpx
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.document import (
    ConfirmedFields, ValidationOutput, FieldValue,
    UserContext, TaxReport, AnalysisPreferences, LLMProvider,
)
from app.services.llm_client import ensure_provider_configured
from app.services.validation_service import validate
from app.services.tax_advisor import run_tax_analysis
from app.storage.session_store import load_session, save_session

logger = logging.getLogger(__name__)

router = APIRouter()

# SYNC: model lists must match SettingsStep.tsx provider model arrays
PROVIDER_MODELS: dict[str, list[str]] = {
    "ollama": [],  # Ollama accepts any model name — skip validation
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-5.2"],
    "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
}


class ConfirmRequest(BaseModel):
    document_id: str
    confirmed_fields: dict[str, dict]
    unresolved_fields: list[str] = []


class AnalyzeRequest(BaseModel):
    provider: LLMProvider = LLMProvider.OLLAMA
    model: str | None = None
    api_key: str | None = None  # Inline key — takes precedence over env var; never logged


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
async def analyze_document(document_id: str, req: AnalyzeRequest):
    try:
        session = load_session(document_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if not session.confirmed_fields:
        raise HTTPException(400, "Fields must be confirmed before analysis")

    # Validate model against allowlist (Ollama accepts any model name)
    provider_key = req.provider.value if hasattr(req.provider, "value") else str(req.provider)
    allowed_models = PROVIDER_MODELS.get(provider_key, [])
    if allowed_models and req.model and req.model not in allowed_models:
        raise HTTPException(422, f"Model '{req.model}' is not supported for provider '{provider_key}'.")

    confirmed = session.confirmed_fields
    validation = session.validation_output or ValidationOutput(status="ok")
    user_context = session.user_context
    preferences = AnalysisPreferences(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,  # Never stored in session — per-request only
    )

    # Skip env-key check when user provides an inline API key
    if preferences.provider != "ollama" and not req.api_key:
        try:
            ensure_provider_configured(preferences.provider)
        except ValueError as e:
            raise HTTPException(400, str(e))

    # Save preferences without the api_key (never persist it)
    session.analysis_preferences = AnalysisPreferences(
        provider=req.provider, model=req.model
    )
    session.status = "analyzing"
    save_session(session)

    logger.info(
        "analyze_document: provider=%s model=%s api_key=%s",
        provider_key,
        req.model or "default",
        "<provided>" if req.api_key else "<env>",
    )

    try:
        report = await run_tax_analysis(confirmed, validation, user_context, preferences)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(400, "Authentication failed: check your API key.")
        raise HTTPException(502, f"Analysis failed: provider returned {e.response.status_code}")
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
