"""Tests for Bundle API endpoints (TODO-18).

Test contract (12 paths):
  T01  POST /api/bundle → 201 with bundle_id
  T02  POST /api/bundle → bundle_id is a valid UUID
  T03  GET  /api/bundle/{id} for new bundle → status "uploading"
  T04  POST /api/bundle/{id}/add with non-existent bundle → 404
  T05  POST /api/bundle/{id}/confirm with non-existent bundle → 404
  T06  POST /api/bundle/{id}/aggregate with uploading bundle → 409
  T07  GET  /api/bundle/{id} with non-existent bundle → 404
  T08  POST /api/bundle/{id}/add respects MAX_DOCUMENTS_PER_BUNDLE (10)
  T09  POST /api/bundle/{id}/add with non-existent document session → 404
  T10  POST /api/bundle/{id}/confirm with no documents → 422
  T11  POST /api/bundle/{id}/add duplicate document_id → 409
  T12  Full happy-path status transitions: uploading → all_confirmed → aggregated

Run: pytest backend/tests/test_bundle_api.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.document import (
    AggregatedFields,
    ConfirmedFields,
    DocumentBundle,
    FieldValue,
    MAX_DOCUMENTS_PER_BUNDLE,
    SessionState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(document_id: str, confirmed: bool = False) -> SessionState:
    """Create a minimal SessionState, optionally with confirmed_fields."""
    sess = SessionState(
        document_id=document_id,
        filename=f"{document_id}.pdf",
        file_path=f"/tmp/{document_id}.pdf",
        status="confirmed" if confirmed else "uploaded",
    )
    if confirmed:
        sess.confirmed_fields = ConfirmedFields(
            document_id=document_id,
            confirmed_fields={
                "box_1_wages": FieldValue(value="50000", confidence=0.99, source="user_confirmed"),
            },
        )
    return sess


def _make_bundle(bundle_id: str, document_ids: list[str] | None = None,
                 status: str = "uploading") -> DocumentBundle:
    """Create a DocumentBundle with optional pre-filled document_ids."""
    return DocumentBundle(
        bundle_id=bundle_id,
        document_ids=document_ids or [],
        status=status,
    )


client = TestClient(app)


# ---------------------------------------------------------------------------
# T01 — POST /api/bundle returns 201 with bundle_id
# ---------------------------------------------------------------------------

def test_t01_create_bundle_returns_201():
    with patch("app.api.bundle.save_bundle"):
        response = client.post("/api/bundle")
    assert response.status_code == 201
    data = response.json()
    assert "bundle_id" in data


# ---------------------------------------------------------------------------
# T02 — POST /api/bundle returns a valid UUID
# ---------------------------------------------------------------------------

def test_t02_create_bundle_returns_valid_uuid():
    with patch("app.api.bundle.save_bundle"):
        response = client.post("/api/bundle")
    bundle_id = response.json()["bundle_id"]
    # Should not raise
    parsed = uuid.UUID(bundle_id)
    assert str(parsed) == bundle_id


# ---------------------------------------------------------------------------
# T03 — GET /api/bundle/{id} for new bundle returns status "uploading"
# ---------------------------------------------------------------------------

def test_t03_get_new_bundle_status_uploading():
    bid = str(uuid.uuid4())
    bundle = _make_bundle(bid)
    with patch("app.api.bundle.load_bundle", return_value=bundle):
        response = client.get(f"/api/bundle/{bid}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "uploading"
    assert data["document_count"] == 0
    assert data["documents"] == []


# ---------------------------------------------------------------------------
# T04 — POST /api/bundle/{id}/add with non-existent bundle returns 404
# ---------------------------------------------------------------------------

def test_t04_add_document_to_nonexistent_bundle_404():
    with patch("app.api.bundle.load_bundle", side_effect=FileNotFoundError("not found")):
        response = client.post(
            f"/api/bundle/{uuid.uuid4()}/add",
            json={"document_id": "some-doc"},
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T05 — POST /api/bundle/{id}/confirm with non-existent bundle returns 404
# ---------------------------------------------------------------------------

def test_t05_confirm_nonexistent_bundle_404():
    with patch("app.api.bundle.load_bundle", side_effect=FileNotFoundError("not found")):
        response = client.post(f"/api/bundle/{uuid.uuid4()}/confirm")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T06 — POST /api/bundle/{id}/aggregate with uploading bundle returns 409
# ---------------------------------------------------------------------------

def test_t06_aggregate_uploading_bundle_409():
    bid = str(uuid.uuid4())
    bundle = _make_bundle(bid, status="uploading")
    with patch("app.api.bundle.load_bundle", return_value=bundle):
        response = client.post(f"/api/bundle/{bid}/aggregate")
    assert response.status_code == 409
    assert "all_confirmed" in response.json()["detail"].lower() or "confirm" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T07 — GET /api/bundle/{id} with non-existent bundle returns 404
# ---------------------------------------------------------------------------

def test_t07_get_nonexistent_bundle_404():
    with patch("app.api.bundle.load_bundle", side_effect=FileNotFoundError("not found")):
        response = client.get(f"/api/bundle/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# T08 — POST /api/bundle/{id}/add respects MAX_DOCUMENTS_PER_BUNDLE limit
# ---------------------------------------------------------------------------

def test_t08_add_document_exceeds_max_limit():
    bid = str(uuid.uuid4())
    # Create a bundle already at the maximum capacity
    existing_ids = [f"doc-{i}" for i in range(MAX_DOCUMENTS_PER_BUNDLE)]
    bundle = _make_bundle(bid, document_ids=existing_ids)

    with patch("app.api.bundle.load_bundle", return_value=bundle):
        response = client.post(
            f"/api/bundle/{bid}/add",
            json={"document_id": "one-too-many"},
        )
    assert response.status_code == 422
    assert "full" in response.json()["detail"].lower() or str(MAX_DOCUMENTS_PER_BUNDLE) in response.json()["detail"]


# ---------------------------------------------------------------------------
# T09 — POST /api/bundle/{id}/add with non-existent document session → 404
# ---------------------------------------------------------------------------

def test_t09_add_document_session_not_found_404():
    bid = str(uuid.uuid4())
    bundle = _make_bundle(bid)

    with patch("app.api.bundle.load_bundle", return_value=bundle), \
         patch("app.api.bundle.load_session", side_effect=FileNotFoundError("not found")):
        response = client.post(
            f"/api/bundle/{bid}/add",
            json={"document_id": "ghost-doc"},
        )
    assert response.status_code == 404
    assert "ghost-doc" in response.json()["detail"]


# ---------------------------------------------------------------------------
# T10 — POST /api/bundle/{id}/confirm with no documents → 422
# ---------------------------------------------------------------------------

def test_t10_confirm_empty_bundle_422():
    bid = str(uuid.uuid4())
    bundle = _make_bundle(bid)

    with patch("app.api.bundle.load_bundle", return_value=bundle):
        response = client.post(f"/api/bundle/{bid}/confirm")
    assert response.status_code == 422
    assert "no documents" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T11 — POST /api/bundle/{id}/add duplicate document_id → 409
# ---------------------------------------------------------------------------

def test_t11_add_duplicate_document_409():
    bid = str(uuid.uuid4())
    doc_id = "already-in-bundle"
    bundle = _make_bundle(bid, document_ids=[doc_id])

    with patch("app.api.bundle.load_bundle", return_value=bundle):
        response = client.post(
            f"/api/bundle/{bid}/add",
            json={"document_id": doc_id},
        )
    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T12 — Full happy-path: uploading → all_confirmed → aggregated
# ---------------------------------------------------------------------------

def test_t12_status_transitions_happy_path():
    """Walk through the full lifecycle: create → add → confirm → aggregate."""
    bid = str(uuid.uuid4())
    doc_id = "doc-happy-path"
    session = _make_session(doc_id, confirmed=True)

    # --- Step 1: Create bundle ---
    with patch("app.api.bundle.save_bundle"):
        create_resp = client.post("/api/bundle")
    assert create_resp.status_code == 201
    # We'll use our own bid for subsequent steps since save_bundle is mocked

    # --- Step 2: Add document ---
    bundle_uploading = _make_bundle(bid, document_ids=[])

    # After add, the bundle should have the doc
    bundle_after_add = _make_bundle(bid, document_ids=[doc_id])

    def mock_save_bundle_add(b):
        """Capture save to verify mutation."""
        assert doc_id in b.document_ids

    with patch("app.api.bundle.load_bundle", return_value=bundle_uploading), \
         patch("app.api.bundle.load_session", return_value=session), \
         patch("app.api.bundle.check_duplicate", return_value=None), \
         patch("app.api.bundle.save_bundle", side_effect=mock_save_bundle_add):
        add_resp = client.post(
            f"/api/bundle/{bid}/add",
            json={"document_id": doc_id},
        )
    assert add_resp.status_code == 200
    assert add_resp.json()["document_count"] == 1

    # --- Step 3: Confirm bundle ---
    bundle_with_doc = _make_bundle(bid, document_ids=[doc_id])

    saved_bundles = []

    def mock_save_bundle_confirm(b):
        saved_bundles.append(b)

    with patch("app.api.bundle.load_bundle", return_value=bundle_with_doc), \
         patch("app.api.bundle.load_session", return_value=session), \
         patch("app.api.bundle.save_bundle", side_effect=mock_save_bundle_confirm):
        confirm_resp = client.post(f"/api/bundle/{bid}/confirm")
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "all_confirmed"
    assert saved_bundles[-1].status == "all_confirmed"

    # --- Step 4: Aggregate ---
    bundle_confirmed = _make_bundle(bid, document_ids=[doc_id], status="all_confirmed")
    fake_aggregated = AggregatedFields(
        bundle_id=bid,
        source_document_ids=[doc_id],
        confirmed_fields=session.confirmed_fields,
        aggregation_log=["Merged 1 W-2 document"],
    )

    saved_agg_bundles = []

    def mock_save_bundle_agg(b):
        saved_agg_bundles.append(b)

    with patch("app.api.bundle.load_bundle", return_value=bundle_confirmed), \
         patch("app.api.bundle.load_session", return_value=session), \
         patch("app.api.bundle.aggregate", return_value=fake_aggregated), \
         patch("app.api.bundle.save_bundle", side_effect=mock_save_bundle_agg), \
         patch("app.api.bundle.save_session"):
        agg_resp = client.post(f"/api/bundle/{bid}/aggregate")
    assert agg_resp.status_code == 200
    assert agg_resp.json()["status"] == "aggregated"
    assert saved_agg_bundles[-1].status == "aggregated"
    assert saved_agg_bundles[-1].aggregated_fields is not None
