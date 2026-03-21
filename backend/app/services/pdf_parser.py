"""PDF/Image text extraction.

Strategy:
- PDF  → opendataloader_pdf (structure-aware, keeps table layout) → markdown text
         fallback: render page to image → DeepSeek OCR
- Image → DeepSeek OCR via Ollama
"""
import asyncio
import base64
import io
import json as _json
import logging
import tempfile
from pathlib import Path

import httpx
import pdfplumber
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────────

def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def _file_to_base64(file_path: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) for an image file."""
    path = Path(file_path)
    ext = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")
    data = base64.b64encode(path.read_bytes()).decode()
    return data, mime


# ── DeepSeek OCR via Ollama ────────────────────────────────────────────────────

OCR_PROMPT = (
    "You are an OCR assistant. Extract ALL text from this tax document image exactly as it "
    "appears, preserving labels, box numbers, field names, and values. "
    "Output only the extracted text — no commentary, no markdown, no extra formatting."
)


async def _ocr_image_base64(b64_data: str, mime: str = "image/png") -> str:
    """Send an image to DeepSeek vision model via Ollama and return extracted text."""
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": settings.OCR_MODEL,
        "messages": [
            {
                "role": "user",
                "content": OCR_PROMPT,
                "images": [b64_data],
            }
        ],
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0.0},
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _render_pdf_page_to_b64(file_path: str, page_index: int = 0, resolution: int = 200) -> str:
    """Render a PDF page to base64 PNG using pdfplumber (fallback only)."""
    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[page_index]
        img = page.to_image(resolution=resolution).original
    return _image_to_base64(img)


# ── opendataloader_pdf extraction ─────────────────────────────────────────────

def _json_to_readable_text(data: dict) -> str:
    """
    Convert opendataloader JSON to compact text for LLM field extraction.
    - Only uses page 1 (skip duplicate W-2 copies and instructions pages)
    - Deduplicates identical content
    - Sorts elements top-to-bottom, left-to-right (PDF reading order)
    Result: ~2-4KB clean text instead of 93KB raw JSON
    """
    elements = []

    def collect(node):
        if isinstance(node, dict):
            content = node.get("content", "").strip()
            bbox = node.get("bounding box")
            page = node.get("page number", 1)
            if content and bbox and len(content) > 2:
                elements.append({
                    "content": content,
                    "x1": bbox[0],
                    "y1": bbox[1],
                    "page": page,
                })
            for val in node.values():
                if isinstance(val, (dict, list)):
                    collect(val)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(data)

    # Page 1 only — W-2 has 3 identical copies across pages + instructions
    page1 = [e for e in elements if e["page"] == 1]

    # Sort: high y = top of page (PDF y-axis goes up), then left-to-right
    page1.sort(key=lambda e: (-e["y1"], e["x1"]))

    # Deduplicate while preserving order
    seen: set[str] = set()
    lines = []
    for e in page1:
        normalized = " ".join(e["content"].split())
        # Skip separator lines
        if set(normalized.replace(" ", "")) <= {"-", ".", "_"}:
            continue
        if normalized not in seen:
            seen.add(normalized)
            lines.append(e["content"])

    return "\n".join(lines)

def _run_opendataloader(file_path: str, tmp_dir: str) -> None:
    """Synchronous call — run in executor to avoid blocking the event loop."""
    import opendataloader_pdf  # imported lazily so missing install doesn't crash startup
    opendataloader_pdf.convert(
        input_path=[str(file_path)],
        output_dir=tmp_dir,
        format="markdown,json",
    )


async def _extract_with_opendataloader(file_path: str) -> tuple[str, dict | None, int]:
    """
    Extract structured text from a PDF using opendataloader_pdf.
    Returns (compact_text, parsed_json_or_None, page_count).
    parsed_json is the full raw dict — callers that need structured extraction keep it.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_opendataloader, file_path, tmp_dir)

        tmp_path = Path(tmp_dir)
        md_files = sorted(tmp_path.glob("**/*.md"))
        json_files = sorted(tmp_path.glob("**/*.json"))

        text = ""
        parsed_json: dict | None = None
        page_count = 1

        # Parse JSON → keep full dict + compact text fallback
        if json_files:
            try:
                parsed_json = _json.loads(json_files[0].read_text(encoding="utf-8"))
                pages = parsed_json.get("pages") or parsed_json.get("content") or []
                if isinstance(pages, list) and pages:
                    page_count = len(pages)
                text = _json_to_readable_text(parsed_json)
                logger.info("opendataloader: compact text %d chars from %s", len(text), file_path)
            except Exception as e:
                logger.warning("opendataloader: JSON parse failed (%s), will use markdown", e)

        # Fall back to markdown if JSON parse failed
        if not text.strip() and md_files:
            text = md_files[0].read_text(encoding="utf-8")
            logger.info("opendataloader: using markdown output (%d chars) from %s", len(text), file_path)

        # Save debug copies so you can inspect what was extracted
        _save_debug(file_path, md_files, json_files)

        return text, parsed_json, page_count


def _save_debug(original_path: str, md_files: list, json_files: list) -> None:
    """Copy opendataloader output to a persistent debug folder for inspection."""
    from app.core.config import settings
    import shutil
    debug_dir = Path(settings.UPLOAD_DIR) / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(original_path).stem
    for f in md_files:
        shutil.copy(f, debug_dir / f"{stem}_opendataloader.md")
    for f in json_files:
        shutil.copy(f, debug_dir / f"{stem}_opendataloader.json")
    if md_files or json_files:
        logger.info("debug files saved to %s", debug_dir)


# ── public API ─────────────────────────────────────────────────────────────────

async def extract_structured(file_path: str) -> tuple[str, dict | None, int]:
    """
    Primary extraction path.
    Returns (compact_text, parsed_json_or_None, page_count).

    parsed_json is the full opendataloader dict — use it for structured
    candidate extraction.  compact_text is a human-readable fallback.

    For images: parsed_json is None (no structured output available).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        errors = []

        # 1. Try opendataloader_pdf (structure-aware)
        try:
            text, parsed_json, page_count = await _extract_with_opendataloader(str(path))
            if text.strip():
                return text, parsed_json, page_count
            errors.append("opendataloader_pdf: returned empty text")
        except Exception as e:
            errors.append(f"opendataloader_pdf: {e}")

        # 2. Try DeepSeek OCR (vision fallback)
        try:
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
            b64 = _render_pdf_page_to_b64(str(path), page_index=0)
            ocr_text = await _ocr_image_base64(b64, "image/png")
            if ocr_text.strip():
                return ocr_text, None, page_count
            errors.append("deepseek-ocr: returned empty text")
        except Exception as e:
            errors.append(f"deepseek-ocr: {e}")

        raise RuntimeError(
            "Failed to extract text from PDF. Both extraction methods failed:\n"
            + "\n".join(f"  • {err}" for err in errors)
        )

    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        b64, mime = _file_to_base64(str(path))
        ocr_text = await _ocr_image_base64(b64, mime)
        return ocr_text, None, 1

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


async def extract_text(file_path: str) -> tuple[str, int]:
    """Legacy wrapper — returns only (text, page_count)."""
    text, _json, page_count = await extract_structured(file_path)
    return text, page_count
