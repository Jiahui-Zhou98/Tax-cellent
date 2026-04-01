"""AI-powered PDF field extraction via Gemini Vision API.

Sends the PDF as inline data to Gemini's generateContent endpoint,
which reads the document visually and returns structured JSON.

This is separate from llm_client.py because Vision API payloads are
structurally different from chat completions (binary PDF data vs text prompt).
The Gemini API key is resolved via the shared get_gemini_key() helper.

Public API:
    extract_with_ai(file_path, api_key, model) -> dict[str, FieldValue]
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

from app.schemas.document import FieldValue
from app.services.llm_client import get_gemini_key

logger = logging.getLogger(__name__)

AI_EXTRACTION_TIMEOUT = 15.0  # seconds — fail fast, regex is the fallback

# ---------------------------------------------------------------------------
# Structured prompts per form type
# ---------------------------------------------------------------------------

_W2_PROMPT = """Extract all values from this W-2 tax form. Return a JSON object with these exact keys:
- form_type: "W-2"
- tax_year: the year shown on the form (number)
- employer_name: string
- employer_ein: string (Box b)
- employee_name: string
- employee_ssn: string (Box a, may be partially masked)
- box_1_wages: number (Box 1)
- box_2_federal_tax_withheld: number (Box 2)
- box_3_social_security_wages: number (Box 3)
- box_4_social_security_tax: number (Box 4)
- box_5_medicare_wages: number (Box 5)
- box_6_medicare_tax: number (Box 6)
- box_10_dependent_care: number (Box 10)
- box_12a_code: string, box_12a_amount: number (Box 12a)
- box_12b_code: string, box_12b_amount: number (Box 12b)
- box_14_other: string (all Box 14 items as free text)
- box_15_state: string (2-letter state code)
- box_15_employer_state_id: string
- box_16_state_wages: number
- box_17_state_income_tax: number
- box_18_local_wages: number
- box_19_local_income_tax: number
- box_20_locality_name: string
Return ONLY the JSON object. Use null for blank/empty fields. Use numbers (not strings) for dollar amounts."""

_NEC_PROMPT = """Extract all values from this 1099-NEC tax form. Return a JSON object with these exact keys:
- form_type: "1099-NEC"
- tax_year: number
- payer_name: string
- recipient_name: string
- box_1_nonemployee_compensation: number (Box 1)
- box_4_federal_tax_withheld: number (Box 4)
Return ONLY the JSON object. Use null for blank fields. Numbers as numbers."""

_1042S_PROMPT = """Extract all values from this 1042-S tax form. Return a JSON object with these exact keys:
- form_type: "1042-S"
- tax_year: number
- withholding_agent: string
- recipient_name: string
- recipient_tin: string
- gross_income_ch3: number (Box 2 - Gross income)
- ch3_withholding: number (Box 7 - Chapter 3 tax withheld)
- ch4_withholding: number (Box 8 - Chapter 4 tax withheld)
Return ONLY the JSON object. Use null for blank fields. Numbers as numbers."""

_MISC_PROMPT = """Extract all values from this 1099-MISC tax form. Return a JSON object with these exact keys:
- form_type: "1099-MISC"
- tax_year: number
- payer_name: string
- recipient_name: string
- box_1_rents: number (Box 1)
- box_1_royalties: number (Box 2 - Royalties)
- box_3_other_income: number (Box 3)
- box_2_federal_tax_withheld: number (Box 4 - Federal tax withheld)
Return ONLY the JSON object. Use null for blank fields. Numbers as numbers."""

_INT_PROMPT = """Extract all values from this 1099-INT tax form. Return a JSON object with these exact keys:
- form_type: "1099-INT"
- tax_year: number
- payer_name: string
- recipient_name: string
- box_1_interest_income: number (Box 1)
- box_4_federal_tax_withheld: number (Box 4)
Return ONLY the JSON object. Use null for blank fields. Numbers as numbers."""

_DETECT_PROMPT = (
    "What type of IRS tax form is this? Reply with ONLY one of: "
    "W-2, 1099-NEC, 1099-INT, 1042-S, 1099-MISC, UNKNOWN"
)

_PROMPTS = {
    "W-2": _W2_PROMPT,
    "1099-NEC": _NEC_PROMPT,
    "1042-S": _1042S_PROMPT,
    "1099-MISC": _MISC_PROMPT,
    "1099-INT": _INT_PROMPT,
}


# ---------------------------------------------------------------------------
# Gemini Vision API call
# ---------------------------------------------------------------------------

async def _call_gemini_vision(
    file_path: str,
    prompt: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    json_mode: bool = True,
) -> str:
    """Send PDF to Gemini Vision and return the text response."""
    pdf_bytes = Path(file_path).read_bytes()
    b64_data = base64.b64encode(pdf_bytes).decode("utf-8")

    generation_config: dict = {"temperature": 0.1}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "application/pdf", "data": b64_data}},
                {"text": prompt},
            ]
        }],
        "generationConfig": generation_config,
    }

    async with httpx.AsyncClient(timeout=AI_EXTRACTION_TIMEOUT) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                return part["text"]
    raise ValueError("Gemini Vision returned no text output")


# ---------------------------------------------------------------------------
# JSON → FieldValue conversion
# ---------------------------------------------------------------------------

def _json_to_field_values(raw: dict) -> dict[str, FieldValue]:
    """Convert Gemini's JSON response to FieldValue dict matching extraction_service keys."""
    result: dict[str, FieldValue] = {}
    for key, val in raw.items():
        if val is None:
            continue
        str_val = str(val) if not isinstance(val, str) else val
        if not str_val.strip():
            continue
        result[key] = FieldValue(
            value=str_val,
            confidence=0.95,
            source="ai",
        )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_with_ai(
    file_path: str,
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
) -> dict[str, FieldValue]:
    """Extract tax form fields using Gemini Vision API.

    Returns dict of field_name → FieldValue. On ANY error, returns empty dict
    (the caller falls back to regex-only extraction).
    """
    key = get_gemini_key(api_key)
    if not key:
        return {}

    try:
        # Step 1: Detect form type
        form_type_raw = await _call_gemini_vision(
            file_path, _DETECT_PROMPT, key, model, json_mode=False,
        )
        form_type = form_type_raw.strip().upper()

        # Normalize
        for known in _PROMPTS:
            if known.upper() in form_type:
                form_type = known
                break
        else:
            logger.warning("ai_extractor: unknown form type '%s', trying W-2 prompt", form_type_raw)
            form_type = "W-2"

        # Step 2: Extract fields with form-specific prompt
        prompt = _PROMPTS[form_type]
        response_text = await _call_gemini_vision(file_path, prompt, key, model)

        # Step 3: Parse JSON
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
            else:
                logger.warning("ai_extractor: could not parse JSON from response: %s", text[:200])
                return {}

        fields = _json_to_field_values(parsed)
        logger.info("ai_extractor: extracted %d fields via %s (%s)", len(fields), model, form_type)
        return fields

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (401, 403):
            logger.warning("ai_extractor: auth failed (HTTP %d) — invalid API key", status)
        else:
            logger.warning("ai_extractor: Gemini returned HTTP %d", status)
        return {}
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning("ai_extractor: network error — %s", e)
        return {}
    except Exception as e:
        logger.warning("ai_extractor: unexpected error — %s", e)
        return {}
