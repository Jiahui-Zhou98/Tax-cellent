"""Bundle API — multi-document aggregation for NRA tax filing.

Endpoints
---------
POST   /api/bundle                            Create a new empty bundle
POST   /api/bundle/{bundle_id}/add            Add a document to the bundle
GET    /api/bundle/{bundle_id}                Get bundle status + metadata
POST   /api/bundle/{bundle_id}/confirm        Verify all docs are confirmed → all_confirmed
POST   /api/bundle/{bundle_id}/aggregate      Merge confirmed docs → aggregated_fields
POST   /api/bundle/{bundle_id}/analyze        Run tax analysis on the aggregated bundle
GET    /api/bundle/{bundle_id}/result         Get the TaxReport for the completed bundle

Typical happy-path flow:
  1. POST /bundle                             → bundle_id
  2. POST /upload  (per document)             → document_id  [existing endpoint]
  3. POST /confirm (per document)             → ValidationOutput  [existing endpoint]
  4. POST /bundle/{id}/add  (per document)    → updated document list
  5. POST /bundle/{id}/confirm                → status: all_confirmed
  6. POST /bundle/{id}/aggregate              → merged field count + log
  7. POST /bundle/{id}/analyze                → TaxReport
  8. GET  /bundle/{id}/result                 → TaxReport (cached)
"""
from __future__ import annotations

import httpx
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.constants.models import PROVIDER_MODELS
from app.schemas.document import (
    AnalysisPreferences,
    DocumentBundle,
    LLMProvider,
    MAX_DOCUMENTS_PER_BUNDLE,
    TaxReport,
    UserContext,
    ValidationOutput,
)
from app.services.aggregation_service import aggregate, check_duplicate
from app.services.llm_client import ensure_provider_configured
from app.services.tax_advisor import run_tax_analysis
from app.storage.session_store import (
    load_bundle,
    load_session,
    save_bundle,
    save_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AddDocumentRequest(BaseModel):
    document_id: str


class BundleAnalyzeRequest(BaseModel):
    provider: LLMProvider = LLMProvider.OLLAMA
    model: Optional[str] = None
    api_key: Optional[str] = None  # Inline key — takes precedence over env var; never logged


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/bundle", status_code=201)
async def create_bundle() -> dict:
    """Create a new empty bundle. Returns {bundle_id}."""
    bundle_id = str(uuid.uuid4())
    bundle = DocumentBundle(bundle_id=bundle_id)
    save_bundle(bundle)
    logger.info("create_bundle: created bundle %s", bundle_id)
    return {"bundle_id": bundle_id}


@router.post("/bundle/{bundle_id}/add")
async def add_document(bundle_id: str, req: AddDocumentRequest) -> dict:
    """Add a document to the bundle by document_id.

    Rejects:
    - Bundle already aggregated or complete
    - Bundle at MAX_DOCUMENTS_PER_BUNDLE capacity
    - Document already in the bundle
    - Document is a duplicate of an existing bundle member (SHA-256 match)
    - Document session not found
    """
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    if bundle.status in ("aggregated", "complete"):
        raise HTTPException(409, f"Bundle is '{bundle.status}' — cannot add documents")

    if len(bundle.document_ids) >= MAX_DOCUMENTS_PER_BUNDLE:
        raise HTTPException(
            422,
            f"Bundle is full ({MAX_DOCUMENTS_PER_BUNDLE} documents maximum)",
        )

    if req.document_id in bundle.document_ids:
        raise HTTPException(409, "Document is already in this bundle")

    try:
        new_session = load_session(req.document_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Document '{req.document_id}' not found")

    # Duplicate detection against all current bundle members
    existing_sessions = []
    for doc_id in bundle.document_ids:
        try:
            existing_sessions.append(load_session(doc_id))
        except FileNotFoundError:
            pass  # Tolerate orphaned references

    dup_id = check_duplicate(new_session, existing_sessions)
    if dup_id:
        raise HTTPException(
            409,
            f"Document appears to be a duplicate of '{dup_id}' (identical file contents)",
        )

    bundle.document_ids.append(req.document_id)
    bundle.status = "uploading"
    save_bundle(bundle)

    logger.info(
        "add_document: bundle=%s added document=%s (total=%d)",
        bundle_id, req.document_id, len(bundle.document_ids),
    )
    return {
        "bundle_id": bundle_id,
        "document_count": len(bundle.document_ids),
        "document_ids": bundle.document_ids,
    }


@router.get("/bundle/{bundle_id}")
async def get_bundle(bundle_id: str) -> dict:
    """Return bundle status, document list, and aggregation log (if available)."""
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    doc_statuses = []
    for doc_id in bundle.document_ids:
        try:
            sess = load_session(doc_id)
            doc_statuses.append({
                "document_id": doc_id,
                "filename": sess.filename,
                "confirmed": sess.confirmed_fields is not None,
                "status": sess.status,
            })
        except FileNotFoundError:
            doc_statuses.append({"document_id": doc_id, "error": "session not found"})

    return {
        "bundle_id": bundle_id,
        "status": bundle.status,
        "document_count": len(bundle.document_ids),
        "documents": doc_statuses,
        "aggregation_log": (
            bundle.aggregated_fields.aggregation_log
            if bundle.aggregated_fields else []
        ),
    }


@router.post("/bundle/{bundle_id}/confirm")
async def confirm_bundle(bundle_id: str) -> dict:
    """Verify all documents have confirmed fields; transition to 'all_confirmed'.

    Each document must have been confirmed individually via POST /api/confirm
    before this endpoint is called.
    """
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    if not bundle.document_ids:
        raise HTTPException(422, "Bundle has no documents — add documents first")

    unconfirmed = []
    for doc_id in bundle.document_ids:
        try:
            sess = load_session(doc_id)
            if not sess.confirmed_fields:
                unconfirmed.append(doc_id)
        except FileNotFoundError:
            unconfirmed.append(f"{doc_id} (session not found)")

    if unconfirmed:
        raise HTTPException(
            422,
            f"The following documents are not yet confirmed: {unconfirmed}. "
            "Call POST /api/confirm for each document before confirming the bundle.",
        )

    bundle.status = "all_confirmed"
    save_bundle(bundle)

    logger.info("confirm_bundle: bundle=%s → all_confirmed (%d docs)", bundle_id, len(bundle.document_ids))
    return {
        "bundle_id": bundle_id,
        "status": bundle.status,
        "document_count": len(bundle.document_ids),
    }


@router.post("/bundle/{bundle_id}/aggregate")
async def aggregate_bundle(bundle_id: str) -> dict:
    """Merge all confirmed documents into a single AggregatedFields.

    Requires bundle status == 'all_confirmed'.
    Reads user_context from the primary document (document_ids[0]).
    Saves any has_1042s mutation back to the primary session so the
    analyze step sees the correct value.
    """
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    if bundle.status not in ("all_confirmed", "aggregated"):
        raise HTTPException(
            409,
            f"Bundle must be in 'all_confirmed' state to aggregate "
            f"(current: '{bundle.status}'). "
            f"Call POST /api/bundle/{bundle_id}/confirm first.",
        )

    sessions = []
    for doc_id in bundle.document_ids:
        try:
            sessions.append(load_session(doc_id))
        except FileNotFoundError:
            raise HTTPException(404, f"Document session '{doc_id}' not found")

    # User context from primary document; aggregate() may set has_1042s in-place
    user_context: Optional[UserContext] = sessions[0].user_context if sessions else None

    try:
        aggregated = aggregate(sessions, bundle_id=bundle_id, user_context=user_context)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # Persist the (possibly mutated) has_1042s back to the primary session
    if user_context is not None and sessions:
        sessions[0].user_context = user_context
        save_session(sessions[0])

    bundle.aggregated_fields = aggregated
    bundle.status = "aggregated"
    save_bundle(bundle)

    logger.info(
        "aggregate_bundle: bundle=%s merged %d docs into %d fields",
        bundle_id, len(sessions), len(aggregated.confirmed_fields.confirmed_fields),
    )
    return {
        "bundle_id": bundle_id,
        "status": bundle.status,
        "source_document_ids": aggregated.source_document_ids,
        "merged_field_count": len(aggregated.confirmed_fields.confirmed_fields),
        "aggregation_log": aggregated.aggregation_log,
    }


@router.post("/bundle/{bundle_id}/analyze", response_model=TaxReport)
async def analyze_bundle(bundle_id: str, req: BundleAnalyzeRequest) -> TaxReport:
    """Run tax analysis on the aggregated bundle.

    Requires bundle status == 'aggregated'. Transitions to 'complete'.
    Uses the merged ConfirmedFields from the aggregation step as input.
    """
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    if bundle.status not in ("aggregated", "complete"):
        raise HTTPException(
            409,
            f"Bundle must be aggregated before analysis "
            f"(current: '{bundle.status}'). "
            f"Call POST /api/bundle/{bundle_id}/aggregate first.",
        )

    if not bundle.aggregated_fields:
        raise HTTPException(422, "Bundle has no aggregated fields — run /aggregate first")

    # Validate model against allowlist (Ollama accepts any model name)
    provider_key = req.provider.value if hasattr(req.provider, "value") else str(req.provider)
    allowed_models = PROVIDER_MODELS.get(provider_key, [])
    if allowed_models and req.model and req.model not in allowed_models:
        raise HTTPException(
            422, f"Model '{req.model}' is not supported for provider '{provider_key}'."
        )

    # Skip env-key check when user provides an inline API key
    if req.provider != LLMProvider.OLLAMA and not req.api_key:
        try:
            ensure_provider_configured(req.provider)
        except ValueError as e:
            raise HTTPException(400, str(e))

    confirmed = bundle.aggregated_fields.confirmed_fields
    validation = ValidationOutput(status="ok")  # aggregated docs are pre-validated

    # User context from primary session (has_1042s already saved there by /aggregate)
    user_context: Optional[UserContext] = None
    if bundle.document_ids:
        try:
            primary_session = load_session(bundle.document_ids[0])
            user_context = primary_session.user_context
        except FileNotFoundError:
            pass

    preferences = AnalysisPreferences(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
    )

    logger.info(
        "analyze_bundle: bundle=%s provider=%s model=%s api_key=%s",
        bundle_id, provider_key, req.model or "default",
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

    bundle.tax_report = report
    bundle.status = "complete"
    save_bundle(bundle)

    logger.info("analyze_bundle: bundle=%s → complete", bundle_id)
    return report


@router.get("/bundle/{bundle_id}/result", response_model=TaxReport)
async def get_bundle_result(bundle_id: str) -> TaxReport:
    """Return the cached TaxReport for a completed bundle analysis."""
    try:
        bundle = load_bundle(bundle_id)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found")

    if bundle.status != "complete" or bundle.tax_report is None:
        raise HTTPException(
            404,
            f"Bundle analysis is not complete (status: '{bundle.status}'). "
            f"Call POST /api/bundle/{bundle_id}/analyze first.",
        )

    return bundle.tax_report
