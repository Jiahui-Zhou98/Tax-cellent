"""Unit tests for aggregation_service.py

Covers:
 1. Two W-2s → wages are summed
 2. W-2 + 1099-NEC → form_type becomes COMBINED
 3. W-2 + 1042-S → wages and gross_income_ch3 remain separate (not added)
 4. Single document → numeric fields pass through unchanged
 5. Zero-income document → no crash, form_type always present
 6. source_document_ids records every contributing doc
 7. Empty sessions list → raises ValueError
 8. Session without confirmed_fields → raises ValueError
 9. SSN mismatch across docs → WARNING appears in aggregation_log
10. Consistent SSN → merged value equals primary doc's normalized SSN
11. has_1042s wired on UserContext when a 1042-S doc is present
12. Identical file hash → duplicate detected by check_duplicate()
13. Different file bytes → check_duplicate() returns None
"""
import pytest

from app.schemas.document import (
    ConfirmedFields,
    FieldValue,
    FormType,
    SessionState,
    UserContext,
)
from app.services.aggregation_service import aggregate, check_duplicate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    document_id: str,
    form_type: str,
    fields: dict[str, str],
    file_path: str = "/dev/null",
    confirmed: bool = True,
) -> SessionState:
    """Build a minimal SessionState with ConfirmedFields."""
    confirmed_field_map: dict[str, FieldValue] = {
        "form_type": FieldValue(value=form_type, confidence=1.0, source="ocr"),
    }
    for k, v in fields.items():
        confirmed_field_map[k] = FieldValue(value=v, confidence=0.95, source="ocr")

    cf = ConfirmedFields(
        document_id=document_id,
        confirmed_fields=confirmed_field_map,
    )

    return SessionState(
        document_id=document_id,
        filename=f"{document_id}.pdf",
        file_path=file_path,
        confirmed_fields=cf if confirmed else None,
    )


def _make_w2(
    doc_id: str,
    wages: str,
    withheld: str,
    ssn: str = "123-45-6789",
) -> SessionState:
    return _make_session(
        doc_id,
        FormType.W2.value,
        {
            "box_1_wages": wages,
            "box_2_federal_tax_withheld": withheld,
            "employee_ssn": ssn,
        },
    )


def _make_nec(doc_id: str, income: str, withheld: str = "0") -> SessionState:
    return _make_session(
        doc_id,
        FormType.NEC_1099.value,
        {
            "box_1_nonemployee_compensation": income,
            "box_4_federal_tax_withheld": withheld,
        },
    )


def _make_1042s(
    doc_id: str,
    gross: str,
    ch3_wh: str,
    ch4_wh: str = "0",
) -> SessionState:
    return _make_session(
        doc_id,
        FormType.FORM_1042S.value,
        {
            "gross_income_ch3": gross,
            "ch3_withholding": ch3_wh,
            "ch4_withholding": ch4_wh,
        },
    )


# ---------------------------------------------------------------------------
# Tests — numeric aggregation
# ---------------------------------------------------------------------------

class TestNumericAggregation:

    def test_two_w2s_wages_are_summed(self):
        """Two W-2s from the same person: wages and withholding are added."""
        s1 = _make_w2("doc1", wages="50000", withheld="8000", ssn="111223333")
        s2 = _make_w2("doc2", wages="30000", withheld="5000", ssn="111223333")
        result = aggregate([s1, s2], bundle_id="bundle-sum")

        merged = result.confirmed_fields.confirmed_fields
        assert float(merged["box_1_wages"].value) == pytest.approx(80000.0)
        assert float(merged["box_2_federal_tax_withheld"].value) == pytest.approx(13000.0)

    def test_w2_plus_nec_form_type_is_combined(self):
        """A W-2 and a 1099-NEC together produce form_type = 'COMBINED'."""
        s1 = _make_w2("doc1", wages="40000", withheld="6000")
        s2 = _make_nec("doc2", income="10000", withheld="500")
        result = aggregate([s1, s2], bundle_id="bundle-combo")

        merged = result.confirmed_fields.confirmed_fields
        assert merged["form_type"].value == FormType.COMBINED.value

    def test_w2_plus_1042s_numeric_fields_stay_separate(self):
        """Wages (W-2) and gross_income_ch3 (1042-S) must NOT be added together.
        Each lives in its own FormType bucket inside _NUMERIC_FIELDS."""
        s1 = _make_w2("doc1", wages="20000", withheld="3000")
        s2 = _make_1042s("doc2", gross="15000", ch3_wh="2000")
        result = aggregate([s1, s2], bundle_id="bundle-split")

        merged = result.confirmed_fields.confirmed_fields
        assert float(merged["box_1_wages"].value) == pytest.approx(20000.0)
        assert float(merged["gross_income_ch3"].value) == pytest.approx(15000.0)
        # Critically, they are still separate keys — not summed into one
        assert "box_1_wages" in merged
        assert "gross_income_ch3" in merged

    def test_single_document_passthrough(self):
        """A one-doc bundle returns the same amounts, unchanged."""
        s1 = _make_w2("doc1", wages="75000", withheld="12000")
        result = aggregate([s1], bundle_id="bundle-solo")

        merged = result.confirmed_fields.confirmed_fields
        assert float(merged["box_1_wages"].value) == pytest.approx(75000.0)
        assert float(merged["box_2_federal_tax_withheld"].value) == pytest.approx(12000.0)

    def test_zero_income_doc_does_not_crash(self):
        """All-zero amounts must not raise; form_type is always present."""
        s1 = _make_w2("doc1", wages="0", withheld="0")
        result = aggregate([s1], bundle_id="bundle-zero")

        # form_type must always be written even when no numeric fields qualify
        assert "form_type" in result.confirmed_fields.confirmed_fields

    def test_source_document_ids_recorded(self):
        """AggregatedFields.source_document_ids lists every contributing doc."""
        s1 = _make_w2("alpha", wages="10000", withheld="1000")
        s2 = _make_nec("beta", income="5000")
        result = aggregate([s1, s2], bundle_id="bundle-ids")

        assert set(result.source_document_ids) == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# Tests — guard clauses
# ---------------------------------------------------------------------------

class TestGuards:

    def test_empty_sessions_raises(self):
        """aggregate() with an empty list must raise ValueError."""
        with pytest.raises(ValueError, match="zero documents"):
            aggregate([], bundle_id="bundle-empty")

    def test_unconfirmed_session_raises(self):
        """A SessionState without confirmed_fields must raise ValueError."""
        s_bad = _make_session(
            "doc-bad", FormType.W2.value, {}, confirmed=False
        )
        with pytest.raises(ValueError, match="confirmed_fields"):
            aggregate([s_bad], bundle_id="bundle-bad")


# ---------------------------------------------------------------------------
# Tests — identity fields
# ---------------------------------------------------------------------------

class TestIdentityFields:

    def test_ssn_mismatch_logged_as_warning(self):
        """Different SSNs across docs → WARNING appears in aggregation_log."""
        s1 = _make_w2("doc1", wages="50000", withheld="8000", ssn="111223333")
        s2 = _make_w2("doc2", wages="30000", withheld="5000", ssn="999887777")

        result = aggregate([s1, s2], bundle_id="bundle-ssn-conflict")

        log_text = " ".join(result.aggregation_log)
        assert "WARNING" in log_text

    def test_consistent_ssn_taken_from_primary(self):
        """When all SSNs match, the merged SSN equals the primary doc's value."""
        ssn_raw = "111223333"  # already digits-only → normalization is a no-op
        s1 = _make_w2("doc1", wages="50000", withheld="8000", ssn=ssn_raw)
        s2 = _make_w2("doc2", wages="30000", withheld="5000", ssn=ssn_raw)

        result = aggregate([s1, s2], bundle_id="bundle-ssn-ok")

        merged = result.confirmed_fields.confirmed_fields
        assert merged["employee_ssn"].value == ssn_raw


# ---------------------------------------------------------------------------
# Tests — has_1042s wiring
# ---------------------------------------------------------------------------

class TestHas1042sWiring:

    def test_has_1042s_set_on_user_context_when_1042s_present(self):
        """user_context.has_1042s becomes True when bundle contains a 1042-S."""
        s1 = _make_w2("doc1", wages="40000", withheld="6000")
        s2 = _make_1042s("doc2", gross="20000", ch3_wh="3000")
        ctx = UserContext(visa_type="F-1")

        aggregate([s1, s2], bundle_id="bundle-1042s", user_context=ctx)

        assert ctx.has_1042s is True

    def test_has_1042s_not_set_when_no_1042s_in_bundle(self):
        """user_context.has_1042s stays False when no 1042-S doc is present."""
        s1 = _make_w2("doc1", wages="40000", withheld="6000")
        ctx = UserContext(visa_type="H-1B")

        aggregate([s1], bundle_id="bundle-no-1042s", user_context=ctx)

        assert ctx.has_1042s is False


# ---------------------------------------------------------------------------
# Tests — duplicate detection
# ---------------------------------------------------------------------------

class TestDuplicateDetection:

    def test_identical_file_detected_as_duplicate(self, tmp_path):
        """Two sessions pointing to files with the same bytes → duplicate."""
        content = b"FAKE_PDF_BYTES_FOR_HASH_TEST_UNIQUE_12345"
        f1 = tmp_path / "doc1.pdf"
        f2 = tmp_path / "doc2.pdf"
        f1.write_bytes(content)
        f2.write_bytes(content)

        new_sess = _make_session("new-doc", FormType.W2.value, {}, file_path=str(f2))
        existing = _make_session("old-doc", FormType.W2.value, {}, file_path=str(f1))

        dup_id = check_duplicate(new_sess, [existing])
        assert dup_id == "old-doc"

    def test_different_files_not_flagged(self, tmp_path):
        """Two sessions with different file bytes → check_duplicate returns None."""
        f1 = tmp_path / "doc1.pdf"
        f2 = tmp_path / "doc2.pdf"
        f1.write_bytes(b"CONTENT_FILE_A")
        f2.write_bytes(b"CONTENT_FILE_B")

        new_sess = _make_session("new-doc", FormType.W2.value, {}, file_path=str(f2))
        existing = _make_session("old-doc", FormType.W2.value, {}, file_path=str(f1))

        dup_id = check_duplicate(new_sess, [existing])
        assert dup_id is None
