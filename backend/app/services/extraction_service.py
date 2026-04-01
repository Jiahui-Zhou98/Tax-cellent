"""
Field extraction pipeline.

Primary path (extract_fields_structured):
  opendataloader JSON → candidate_extractor (deterministic) →
  _resolve_candidates (deterministic) → shown directly to user for review

Legacy fallback (extract_fields / extract_fields_llm) used only when the
structured JSON is unavailable (scanned images, OCR-only PDFs).
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from app.schemas.document import FieldValue, FormType
from app.services.llm_client import chat_json
from app.core.config import settings

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ── Wage vs tax field classification ─────────────────────────────────────────
# Wage/income fields: pick the LARGER candidate value
_WAGE_FIELDS = {
    "box_1_wages",
    "box_3_social_security_wages",
    "box_5_medicare_wages",
    "box_16_state_wages",
    "box_18_local_wages",
    "box_1_nonemployee_compensation",
    "box_1_interest_income",
    "box_1_royalties",           # 1099-MISC Box 1
    "box_3_other_income",        # 1099-MISC Box 3
    "gross_income_ch3",          # 1042-S Box 2
}
# Tax/withheld fields: pick the SMALLER candidate value
_TAX_FIELDS = {
    "box_2_federal_tax_withheld",
    "box_4_social_security_tax",
    "box_6_medicare_tax",
    "box_17_state_income_tax",
    "box_19_local_income_tax",
    "box_4_federal_tax_withheld",
    "box_2_early_withdrawal_penalty",
    "ch3_withholding",           # 1042-S Box 7
    "ch4_withholding",           # 1042-S Box 8
}

_MIN_CONFIDENCE = 0.50   # candidates below this are discarded


# ══════════════════════════════════════════════════════════════════════════════
# PRIMARY PIPELINE — fully deterministic, no LLM
# ══════════════════════════════════════════════════════════════════════════════

async def extract_fields_structured(parsed_json: dict) -> dict[str, FieldValue]:
    """
    Primary extraction path — no LLM involved.
    1. candidate_extractor produces ranked candidates per field.
    2. _resolve_candidates picks the best one deterministically and normalises.
    Results are shown directly to the user in Step 02 for review.
    """
    from app.services.candidate_extractor import extract_candidates

    candidate_map = await asyncio.to_thread(extract_candidates, parsed_json)
    if not candidate_map:
        raise ValueError("candidate_extractor returned no candidates")

    result = _resolve_candidates(candidate_map)
    logger.info("extract_fields_structured: resolved %d fields: %s",
                len(result), list(result.keys()))
    return result


def _resolve_candidates(candidate_map: dict) -> dict[str, FieldValue]:
    """
    Deterministic replacement for the LLM field_resolver.

    Selection rules:
      • Discard candidates with confidence < _MIN_CONFIDENCE.
      • Wage fields  → pick the candidate whose value is the LARGEST number.
      • Tax fields   → pick the candidate whose value is the SMALLEST number.
      • Other fields → pick the highest-confidence candidate (already cs[0]).

    Normalisation is applied after selection (strip $/, commas, format EIN, etc.).
    """
    result: dict[str, FieldValue] = {}

    for field_name, candidates in candidate_map.items():
        viable = [c for c in candidates if c.confidence >= _MIN_CONFIDENCE]
        if not viable:
            logger.debug("resolve: no viable candidates for %s (best=%.2f)",
                         field_name, candidates[0].confidence if candidates else 0)
            continue

        chosen = _pick_candidate(field_name, viable)
        normalised = _normalise(field_name, chosen.value or "")

        if normalised is None:
            logger.debug("resolve: normalisation rejected %r for %s", chosen.value, field_name)
            continue

        result[field_name] = FieldValue(
            value=normalised,
            confidence=round(chosen.confidence, 2),
            source="ocr",
        )

    return result


def _pick_candidate(field_name: str, viable: list) -> object:
    """Select the best candidate from the viable list."""
    if field_name in _WAGE_FIELDS or field_name in _TAX_FIELDS:
        # Parse each candidate as a float; fall back to highest-confidence if none parse
        parsed = []
        for c in viable:
            try:
                v = float(str(c.value).replace(",", "").replace("$", "").strip())
                if v > 0:
                    parsed.append((c, v))
            except (ValueError, TypeError):
                pass
        if parsed:
            if field_name in _WAGE_FIELDS:
                return max(parsed, key=lambda t: t[1])[0]   # largest → wages
            else:
                return min(parsed, key=lambda t: t[1])[0]   # smallest → tax
    # Default: highest confidence (already sorted)
    return viable[0]


def _normalise(field_name: str, value: str) -> Optional[str]:
    """Return a normalised string value, or None to reject it."""
    value = value.strip()
    if not value:
        return None

    # Money fields: strip symbols, validate as positive number
    if field_name in _WAGE_FIELDS or field_name in _TAX_FIELDS:
        clean = value.replace("$", "").replace(",", "").strip()
        try:
            amount = float(clean)
            if amount <= 0 or amount > 9_999_999:
                return None
            return clean
        except ValueError:
            return None

    # EIN: normalise to XX-XXXXXXX
    if field_name in ("employer_ein", "payer_tin", "box_15_employer_state_id"):
        m = re.match(r"(\d{2})-?(\d{7})", value)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        return value   # return as-is; validation_service will flag the format

    # Tax year: extract 4-digit year
    if field_name == "tax_year":
        m = re.search(r"\b(20\d{2})\b", value)
        return m.group(1) if m else None

    # All other fields: return as-is
    return value


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY FALLBACK — raw text → LLM field guesser
# ══════════════════════════════════════════════════════════════════════════════

async def extract_fields_llm(raw_text: str) -> dict[str, FieldValue]:
    """Legacy: use LLM to extract fields from raw compact text (no structured JSON)."""
    system_prompt = (PROMPTS_DIR / "field_extraction.txt").read_text()
    truncated = raw_text[:8000]
    data = await chat_json(
        settings.MODEL_A,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": (
                "Extract ALL fields from this tax document "
                "(input may be structured JSON or markdown):\n\n" + truncated
            )},
        ],
        temperature=0.0,
    )
    logger.info("extract_fields_llm (legacy): extracted %d fields: %s",
                len(data), list(data.keys()))

    result: dict[str, FieldValue] = {}
    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        result[key] = FieldValue(
            value=str(val["value"]) if val.get("value") is not None else None,
            confidence=float(val.get("confidence", 0.5)),
            source="llm",
        )

    # Supplement with regex for anything the LLM missed
    regex_fields = extract_fields(raw_text)
    for key, fv in regex_fields.items():
        if key not in result or result[key].value is None:
            result[key] = fv

    return result


# ── helpers ──────────────────────────────────────────────────────────────────

def _money(text: str, *patterns: str) -> FieldValue:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(",", "").strip()
            return FieldValue(value=raw, confidence=0.8)
    return FieldValue(value=None, confidence=0.0)


def _text_field(text: str, *patterns: str) -> FieldValue:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return FieldValue(value=m.group(1).strip(), confidence=0.75)
    return FieldValue(value=None, confidence=0.0)


def detect_form_type(text: str) -> FieldValue:
    text_upper = text.upper()
    if "W-2" in text_upper or "WAGE AND TAX STATEMENT" in text_upper:
        return FieldValue(value=FormType.W2, confidence=0.95)
    if "1099-NEC" in text_upper or "NONEMPLOYEE COMPENSATION" in text_upper:
        return FieldValue(value=FormType.NEC_1099, confidence=0.95)
    if "1099-INT" in text_upper or "INTEREST INCOME" in text_upper:
        return FieldValue(value=FormType.INT_1099, confidence=0.95)
    if ("1042-S" in text_upper or "WITHHOLDING AGENT" in text_upper
            or "CHAPTER 3" in text_upper or "CHAPTER 4" in text_upper):
        return FieldValue(value=FormType.FORM_1042S, confidence=0.95)
    if "1099-MISC" in text_upper or "MISCELLANEOUS INFORMATION" in text_upper:
        return FieldValue(value=FormType.MISC_1099, confidence=0.95)
    return FieldValue(value=FormType.UNKNOWN, confidence=0.3)


def extract_fields(text: str) -> dict[str, FieldValue]:
    """Pure-regex fallback — last resort only."""
    form_type_field = detect_form_type(text)
    form_type = form_type_field.value

    if form_type == FormType.W2:
        return {
            "form_type":    FieldValue(value="W-2", confidence=0.95, source="ocr"),
            "tax_year":     _text_field(text, r"(?:tax year|year)\s*[:\-]?\s*(\d{4})", r"(\b20\d{2}\b)"),
            "employee_name": _text_field(text, r"employee.{0,20}name[:\s]+([A-Za-z ,\.]+)"),
            "employer_name": _text_field(text, r"employer.{0,20}name[:\s]+([A-Za-z ,\.&]+)"),
            "box_1_wages":  _money(text, r"box 1[^$\d]*\$?([\d,]+\.?\d*)", r"wages.{0,30}\$?([\d,]+\.?\d*)"),
            "box_2_federal_tax_withheld": _money(text,
                r"box 2[^$\d]*\$?([\d,]+\.?\d*)",
                r"federal.{0,30}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_3_social_security_wages": _money(text, r"box 3[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_4_social_security_tax":   _money(text, r"box 4[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_5_medicare_wages":        _money(text, r"box 5[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_6_medicare_tax":          _money(text, r"box 6[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_16_state_wages":          _money(text,
                r"box 16[^$\d]*\$?([\d,]+\.?\d*)", r"state wages[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_17_state_income_tax":     _money(text,
                r"box 17[^$\d]*\$?([\d,]+\.?\d*)",
                r"state.{0,15}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_18_local_wages":          _money(text,
                r"box 18[^$\d]*\$?([\d,]+\.?\d*)",
                r"local wages[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_19_local_income_tax":     _money(text,
                r"box 19[^$\d]*\$?([\d,]+\.?\d*)",
                r"local.{0,15}income tax[^$\d]*\$?([\d,]+\.?\d*)"),
        }
    elif form_type == FormType.NEC_1099:
        return {
            "form_type":   FieldValue(value="1099-NEC", confidence=0.95, source="ocr"),
            "tax_year":    _text_field(text, r"(\b20\d{2}\b)"),
            "payer_name":  _text_field(text, r"payer.{0,20}name[:\s]+([A-Za-z ,\.&]+)"),
            "recipient_name": _text_field(text, r"recipient.{0,20}name[:\s]+([A-Za-z ,\.]+)"),
            "box_1_nonemployee_compensation": _money(text,
                r"box 1[^$\d]*\$?([\d,]+\.?\d*)",
                r"nonemployee compensation[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_4_federal_tax_withheld": _money(text,
                r"box 4[^$\d]*\$?([\d,]+\.?\d*)",
                r"federal.{0,30}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
        }
    elif form_type == FormType.INT_1099:
        return {
            "form_type":       FieldValue(value="1099-INT", confidence=0.95, source="ocr"),
            "tax_year":        _text_field(text, r"(\b20\d{2}\b)"),
            "payer_name":      _text_field(text, r"payer.{0,20}name[:\s]+([A-Za-z ,\.&]+)"),
            "recipient_name":  _text_field(text, r"recipient.{0,20}name[:\s]+([A-Za-z ,\.]+)"),
            "box_1_interest_income": _money(text,
                r"box 1[^$\d]*\$?([\d,]+\.?\d*)",
                r"interest income[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_2_early_withdrawal_penalty": _money(text, r"box 2[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_4_federal_tax_withheld":     _money(text, r"box 4[^$\d]*\$?([\d,]+\.?\d*)"),
        }
    elif form_type == FormType.FORM_1042S:
        return {
            "form_type":         FieldValue(value="1042-S", confidence=0.95, source="ocr"),
            "tax_year":          _text_field(text, r"(\b20\d{2}\b)"),
            "withholding_agent": _text_field(text,
                r"withholding agent.{0,20}name[:\s]+([A-Za-z ,\.&]+)"),
            "recipient_name":    _text_field(text,
                r"recipient.{0,20}name[:\s]+([A-Za-z ,\.]+)"),
            "recipient_tin":     _text_field(text,
                r"recipient.{0,20}(?:tin|ssn|ein)[:\s]+([\d\-]+)"),
            # Box 2: Gross income subject to withholding
            "gross_income_ch3":  _money(text,
                r"box 2[^$\d]*\$?([\d,]+\.?\d*)",
                r"gross income[^$\d]*\$?([\d,]+\.?\d*)"),
            # Box 7: U.S. federal tax withheld (Chapter 3)
            "ch3_withholding":   _money(text,
                r"box 7[^$\d]*\$?([\d,]+\.?\d*)",
                r"(?:chapter 3|ch\.?\s*3).{0,30}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
            # Box 8: U.S. federal tax withheld (Chapter 4 / FATCA)
            "ch4_withholding":   _money(text,
                r"box 8[^$\d]*\$?([\d,]+\.?\d*)",
                r"(?:chapter 4|ch\.?\s*4).{0,30}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
        }
    elif form_type == FormType.MISC_1099:
        return {
            "form_type":      FieldValue(value="1099-MISC", confidence=0.95, source="ocr"),
            "tax_year":       _text_field(text, r"(\b20\d{2}\b)"),
            "payer_name":     _text_field(text, r"payer.{0,20}name[:\s]+([A-Za-z ,\.&]+)"),
            "recipient_name": _text_field(text, r"recipient.{0,20}name[:\s]+([A-Za-z ,\.]+)"),
            # Box 1: Rents; Box 2: Royalties; Box 3: Other income
            "box_1_rents":         _money(text, r"box 1[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_1_royalties":     _money(text,
                r"box 2[^$\d]*\$?([\d,]+\.?\d*)",
                r"royalties[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_3_other_income":  _money(text,
                r"box 3[^$\d]*\$?([\d,]+\.?\d*)",
                r"other income[^$\d]*\$?([\d,]+\.?\d*)"),
            "box_2_federal_tax_withheld": _money(text,
                r"box 4[^$\d]*\$?([\d,]+\.?\d*)",
                r"federal.{0,30}withheld[^$\d]*\$?([\d,]+\.?\d*)"),
        }
    else:
        return {
            "form_type": form_type_field,
            "tax_year":  _text_field(text, r"(\b20\d{2}\b)"),
            "raw_note":  FieldValue(
                value="Unsupported form type — manual review required",
                confidence=1.0, source="ocr",
            ),
        }


# ---------------------------------------------------------------------------
# Dual extraction merge
# ---------------------------------------------------------------------------

def _parse_money(val: str) -> Optional[float]:
    """Parse a dollar amount from a string, tolerant of formatting."""
    if not val:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", val)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _values_agree(regex_val: str, ai_val: str) -> bool:
    """Check if two field values agree (money within $0.01, text case-insensitive)."""
    # Try money comparison first
    r_money = _parse_money(regex_val)
    a_money = _parse_money(ai_val)
    if r_money is not None and a_money is not None:
        return abs(r_money - a_money) <= 0.01

    # Text comparison: case-insensitive, whitespace-normalized
    r_norm = " ".join(regex_val.strip().upper().split())
    a_norm = " ".join(ai_val.strip().upper().split())
    return r_norm == a_norm


def merge_extractions(
    regex_fields: dict[str, FieldValue],
    ai_fields: dict[str, FieldValue],
) -> dict[str, FieldValue]:
    """Merge regex and AI extraction results with confidence comparison.

    Merge rules:
      BOTH_AGREE:     values match → use regex value, confidence=0.99
      ONLY_REGEX:     AI has no value → keep regex value, confidence unchanged
      AI_DISAGREES:   both have values but different → use AI, confidence=0.50
      ONLY_AI:        regex missed it → use AI value, confidence=0.90
    """
    all_keys = set(regex_fields.keys()) | set(ai_fields.keys())
    merged: dict[str, FieldValue] = {}

    for key in all_keys:
        r_fv = regex_fields.get(key)
        a_fv = ai_fields.get(key)

        if r_fv and a_fv:
            # Both have values — compare
            if _values_agree(r_fv.value, a_fv.value):
                merged[key] = FieldValue(
                    value=r_fv.value,
                    confidence=0.99,
                    source="ai_regex_agree",
                )
            else:
                # AI disagrees — use AI value (more accurate), flag for review
                merged[key] = FieldValue(
                    value=a_fv.value,
                    confidence=0.50,
                    source="ai_regex_disagree",
                )
        elif r_fv:
            # Only regex has value
            merged[key] = r_fv
        elif a_fv:
            # Only AI has value
            merged[key] = FieldValue(
                value=a_fv.value,
                confidence=0.90,
                source="ai",
            )

    return merged
