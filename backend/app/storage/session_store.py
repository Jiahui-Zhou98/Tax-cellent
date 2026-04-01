import json
import logging
import os
import re
from pathlib import Path
from app.schemas.document import DocumentBundle, SessionState
from app.core.config import settings

logger = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_id(id_value: str, label: str = "id") -> None:
    """Reject IDs that could cause path traversal (e.g. '../../etc/passwd')."""
    if not _SAFE_ID.match(id_value):
        raise ValueError(f"Invalid {label}: must be alphanumeric, hyphens, or underscores")


def _session_path(document_id: str) -> Path:
    _validate_id(document_id, "document_id")
    os.makedirs(settings.SESSION_DIR, exist_ok=True)
    return Path(settings.SESSION_DIR) / f"{document_id}.json"


def _bundle_path(bundle_id: str) -> Path:
    _validate_id(bundle_id, "bundle_id")
    os.makedirs(settings.SESSION_DIR, exist_ok=True)
    return Path(settings.SESSION_DIR) / f"bundle_{bundle_id}.json"


def save_session(session: SessionState) -> None:
    path = _session_path(session.document_id)
    path.write_text(session.model_dump_json(indent=2))


def load_session(document_id: str) -> SessionState:
    path = _session_path(document_id)
    if not path.exists():
        raise FileNotFoundError(f"Session {document_id} not found")
    data = json.loads(path.read_text())
    return SessionState(**data)


def delete_session(document_id: str) -> None:
    path = _session_path(document_id)
    if path.exists():
        path.unlink()


def save_bundle(bundle: DocumentBundle) -> None:
    path = _bundle_path(bundle.bundle_id)
    try:
        path.write_text(bundle.model_dump_json(indent=2))
    except OSError as exc:
        logger.error("save_bundle: failed to write bundle %s: %s", bundle.bundle_id, exc)
        raise


def load_bundle(bundle_id: str) -> DocumentBundle:
    path = _bundle_path(bundle_id)
    if not path.exists():
        raise FileNotFoundError(f"Bundle {bundle_id} not found")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.error("load_bundle: corrupted JSON for bundle %s: %s", bundle_id, exc)
        raise ValueError(f"Bundle {bundle_id} is corrupted and cannot be loaded") from exc
    return DocumentBundle(**data)


def delete_bundle(bundle_id: str) -> None:
    path = _bundle_path(bundle_id)
    if path.exists():
        path.unlink()
