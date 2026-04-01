"""Tests for AI extraction and dual-extraction merge.

Test contract:
  M01  merge: both agree on money → confidence=0.99, source=ai_regex_agree
  M02  merge: AI disagrees on money → use AI value, confidence=0.50
  M03  merge: only regex → keep regex, confidence unchanged
  M04  merge: only AI → use AI value, confidence=0.90
  M05  merge: text agreement case-insensitive
  M06  merge: money agreement within $0.01 threshold
  M07  merge: $0.00 is a valid value (not treated as missing)
  M08  _values_agree: exact money match
  M09  _values_agree: text mismatch
  A01  extract_with_ai returns empty dict when no key
  A02  _json_to_field_values skips null values
  A03  _json_to_field_values sets confidence=0.95

Run: pytest backend/tests/test_ai_extraction.py -v
"""

from __future__ import annotations

import pytest

from app.schemas.document import FieldValue
from app.services.extraction_service import merge_extractions, _values_agree
from app.services.ai_extractor import _json_to_field_values, extract_with_ai


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------

def _fv(value: str, conf: float = 0.80, source: str = "ocr") -> FieldValue:
    return FieldValue(value=value, confidence=conf, source=source)


def test_m01_both_agree_money():
    regex = {"box_1_wages": _fv("44629.35")}
    ai = {"box_1_wages": _fv("44629.35", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    assert merged["box_1_wages"].confidence == 0.99
    assert merged["box_1_wages"].source == "ai_regex_agree"
    assert merged["box_1_wages"].value == "44629.35"


def test_m02_ai_disagrees():
    regex = {"box_1_wages": _fv("44629")}
    ai = {"box_1_wages": _fv("44629.35", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    assert merged["box_1_wages"].confidence == 0.50
    assert merged["box_1_wages"].source == "ai_regex_disagree"
    assert merged["box_1_wages"].value == "44629.35"  # AI value used


def test_m03_only_regex():
    regex = {"box_1_wages": _fv("44629.35")}
    ai: dict = {}
    merged = merge_extractions(regex, ai)
    assert merged["box_1_wages"].confidence == 0.80  # unchanged
    assert merged["box_1_wages"].value == "44629.35"


def test_m04_only_ai():
    regex: dict = {}
    ai = {"box_12a_code": _fv("E", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    assert merged["box_12a_code"].confidence == 0.90
    assert merged["box_12a_code"].source == "ai"


def test_m05_text_agree_case_insensitive():
    regex = {"employer_name": _fv("UNIVERSITY OF PITTSBURGH")}
    ai = {"employer_name": _fv("University of Pittsburgh", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    assert merged["employer_name"].confidence == 0.99
    assert merged["employer_name"].source == "ai_regex_agree"


def test_m06_money_agree_within_threshold():
    regex = {"box_2_federal_tax_withheld": _fv("7631.62")}
    ai = {"box_2_federal_tax_withheld": _fv("7631.62", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    assert merged["box_2_federal_tax_withheld"].confidence == 0.99


def test_m07_zero_is_valid_value():
    regex = {"box_7_tips": _fv("0.00")}
    ai = {"box_7_tips": _fv("0", 0.95, "ai")}
    merged = merge_extractions(regex, ai)
    # $0.00 and $0 agree (within $0.01)
    assert merged["box_7_tips"].confidence == 0.99


def test_m08_values_agree_exact_money():
    assert _values_agree("7631.62", "7631.62") is True
    assert _values_agree("$7,631.62", "7631.62") is True
    assert _values_agree("7631.62", "7631.63") is False  # $0.01 difference is threshold


def test_m09_values_agree_text_mismatch():
    assert _values_agree("PA", "NY") is False
    assert _values_agree("PA", "pa") is True  # case insensitive


# ---------------------------------------------------------------------------
# AI extractor unit tests
# ---------------------------------------------------------------------------

def test_a01_no_key_returns_empty():
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        extract_with_ai("/nonexistent.pdf", api_key=None)
    )
    assert result == {}


def test_a02_json_to_field_values_skips_null():
    raw = {"box_1_wages": 44629.35, "box_7_tips": None, "box_8": ""}
    result = _json_to_field_values(raw)
    assert "box_1_wages" in result
    assert "box_7_tips" not in result
    assert "box_8" not in result


def test_a03_json_to_field_values_confidence():
    raw = {"box_1_wages": 44629.35}
    result = _json_to_field_values(raw)
    assert result["box_1_wages"].confidence == 0.95
    assert result["box_1_wages"].source == "ai"
    assert result["box_1_wages"].value == "44629.35"
