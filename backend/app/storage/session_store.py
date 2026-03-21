import json
import os
from pathlib import Path
from app.schemas.document import SessionState
from app.core.config import settings


def _session_path(document_id: str) -> Path:
    os.makedirs(settings.SESSION_DIR, exist_ok=True)
    return Path(settings.SESSION_DIR) / f"{document_id}.json"


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
