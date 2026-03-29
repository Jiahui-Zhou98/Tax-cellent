"""Aggregation service — merges N confirmed documents into one ConfirmedFields.

Aggregation rules:
  Numeric fields:  sum across all source documents of the same form type.
  Identity fields: validate consistency; warn on conflict (SSN, name).
  Non-aggregatable: take from the primary (first) document.

Called by: POST /api/bundle/{bundle_id}/aggregate
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from app.schemas.document import (
    AggregatedFields,
    ConfirmedFields,
    FieldValue,
    FormType,
    SessionState,
    UserContext,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field classification by form type
# ---------------------------------------------------------------------------

# Numeric fields that are summed across documents of the same type.
_NUMERIC_FIELDS: dict[str, set[str]] = {
    FormType.W2: {
        "box_1_wages",
        "box_2_federal_tax_withheld",
        "box_3_social_security_wages",
        "box_4_social_security_tax",
        "box_5_medicare_wages",
        "box_6_medicare_tax",
        "box_16_state_wages",
        "box_17_state_income_tax",
    },
    FormType.NEC_1099: {
        "box_1_nonemployee_compensation",
        "box_4_federal_tax_withheld",
    },
    FormType.INT_1099: {
        "box_1_interest_income",
        "box_4_federal_tax_withheld",
    },
    FormType.FORM_1042S: {
        "gross_income_ch3",
        "ch3_withholding",
        "ch4_withholding",
    },
    FormType.MISC_1099: {
        "box_1_royalties",
        "box_3_other_income",
        "box_2_federal_tax_withheld",
    },
}

# Identity fields: values must match across all documents; conflict → warning.
_IDENTITY_FIELDS = {
    "employee_ssn",
    "recipient_tin",
    "employee_name",
    "recipient_name",
}

# Non-aggregatable: take from primary document (index 0).
_NONTRANSFERABLE_FIELDS = {
    "tax_year",
    "employer_name",
    "employer_state",
    "state_code",
    "visa_type",
}


# ---------------------------------------------------------------------------
# SSN normalisation — strip punctuation, compare numeric strings only
# ---------------------------------------------------------------------------

def _normalize_ssn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 9 else raw.strip()


def _parse_amount(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", raw)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _file_hash(file_path: str) -> Optional[str]:
    """SHA-256 of raw file bytes — primary duplicate signal."""
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def check_duplicate(
    new_session: SessionState,
    existing_sessions: list[SessionState],
) -> Optional[str]:
    """Return document_id of a likely duplicate, or None.

    Checks SHA-256 of raw file bytes first; falls back to SSN + EIN match.
    Returns the existing document_id if a duplicate is detected.
    """
    new_hash = _file_hash(new_session.file_path)

    for sess in existing_sessions:
        # Primary check: file hash
        if new_hash and _file_hash(sess.file_path) == new_hash:
            return sess.document_id

        # Secondary check: SSN + employer EIN from confirmed fields
        if new_session.confirmed_fields and sess.confirmed_fields:
            def _get(cf: ConfirmedFields, key: str) -> Optional[str]:
                fv = cf.confirmed_fields.get(key)
                return fv.value if fv else None

            new_ssn = _normalize_ssn(_get(new_session.confirmed_fields, "employee_ssn")
                                      or _get(new_session.confirmed_fields, "recipient_tin"))
            ex_ssn  = _normalize_ssn(_get(sess.confirmed_fields, "employee_ssn")
                                      or _get(sess.confirmed_fields, "recipient_tin"))

            if new_ssn and ex_ssn and new_ssn == ex_ssn:
                new_ein = _get(new_session.confirmed_fields, "employer_ein")
                ex_ein  = _get(sess.confirmed_fields, "employer_ein")
                if new_ein and ex_ein and new_ein == ex_ein:
                    return sess.document_id

    return None


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------

def aggregate(
    sessions: list[SessionState],
    bundle_id: str,
    user_context: Optional[UserContext] = None,
) -> AggregatedFields:
    """Merge N confirmed SessionState objects into one AggregatedFields.

    Rules:
    - sessions must be non-empty and all have confirmed_fields set.
    - Primary document = sessions[0].
    - Numeric fields are summed per form type across all documents.
    - Identity fields are consistency-checked; conflicts surface as log warnings.
    - Non-aggregatable fields (visa, employer state) taken from primary document.
    - has_1042s is set on user_context when any source doc is FormType.FORM_1042S.
    - form_type = "COMBINED" when more than one distinct form type is present;
      otherwise, keeps the single form type unchanged (pass-through).

    Raises:
        ValueError: if sessions is empty or any session has no confirmed_fields.
    """
    if not sessions:
        raise ValueError("Cannot aggregate zero documents")

    for sess in sessions:
        if not sess.confirmed_fields:
            raise ValueError(
                f"Document {sess.document_id} has no confirmed_fields — "
                "all documents must be confirmed before aggregation"
            )

    log: list[str] = []
    source_ids = [s.document_id for s in sessions]
    primary = sessions[0]

    # ── Detect form types ────────────────────────────────────────────────────
    form_types: list[str] = []
    for sess in sessions:
        fv = sess.confirmed_fields.confirmed_fields.get("form_type")
        ft = (fv.value or FormType.UNKNOWN) if fv else FormType.UNKNOWN
        form_types.append(ft)

    distinct_types = list(dict.fromkeys(form_types))  # preserve insertion order
    has_1042s = any(ft == FormType.FORM_1042S for ft in form_types)

    if len(distinct_types) == 1:
        merged_form_type = distinct_types[0]
    else:
        merged_form_type = FormType.COMBINED

    log.append(f"Source form types: {form_types} → merged as '{merged_form_type}'")

    # ── Wire has_1042s on user_context ───────────────────────────────────────
    if has_1042s and user_context is not None:
        user_context.has_1042s = True
        log.append("has_1042s=True set on user_context (1042-S source detected)")

    # ── Sum numeric fields per form type ─────────────────────────────────────
    numeric_totals: dict[str, float] = {}

    for sess, form_type_str in zip(sessions, form_types):
        # Match form_type_str to a FormType enum key for numeric field lookup
        numeric_field_set: set[str] = set()
        for ft_enum, fields in _NUMERIC_FIELDS.items():
            if ft_enum.value == form_type_str or ft_enum == form_type_str:
                numeric_field_set = fields
                break

        for field_name in numeric_field_set:
            fv = sess.confirmed_fields.confirmed_fields.get(field_name)
            amount = _parse_amount(fv.value if fv else None)
            if amount:
                prev = numeric_totals.get(field_name, 0.0)
                numeric_totals[field_name] = prev + amount
                log.append(f"  + {field_name}: {amount} from {sess.document_id} (total={prev + amount})")

    # ── Identity field consistency check ────────────────────────────────────
    merged_identity: dict[str, str] = {}
    for id_field in _IDENTITY_FIELDS:
        values: list[tuple[str, str]] = []  # (document_id, normalized_value)
        for sess in sessions:
            fv = sess.confirmed_fields.confirmed_fields.get(id_field)
            if fv and fv.value:
                raw = fv.value
                norm = _normalize_ssn(raw) if "ssn" in id_field or "tin" in id_field else raw.strip()
                values.append((sess.document_id, norm))

        if not values:
            continue

        unique_vals = list(dict.fromkeys(v for _, v in values))
        if len(unique_vals) > 1:
            log.append(
                f"WARNING: {id_field} conflict across documents — "
                f"{[f'{doc_id}:{val}' for doc_id, val in values]}; "
                f"using value from primary document"
            )
        merged_identity[id_field] = values[0][1]  # always take from primary

    # ── Non-aggregatable fields from primary document ────────────────────────
    non_agg_fields: dict[str, FieldValue] = {}
    primary_fields = primary.confirmed_fields.confirmed_fields
    for field_name in _NONTRANSFERABLE_FIELDS:
        fv = primary_fields.get(field_name)
        if fv and fv.value:
            non_agg_fields[field_name] = FieldValue(
                value=fv.value, confidence=fv.confidence, source="primary_document"
            )

    # ── Assemble merged confirmed_fields ─────────────────────────────────────
    merged: dict[str, FieldValue] = {}

    # form_type
    merged["form_type"] = FieldValue(
        value=merged_form_type.value if hasattr(merged_form_type, "value") else merged_form_type,
        confidence=1.0,
        source="aggregation_service",
    )

    # Numeric totals
    for field_name, total in numeric_totals.items():
        merged[field_name] = FieldValue(
            value=str(round(total, 2)),
            confidence=1.0,
            source="aggregation_service",
        )

    # Identity fields (already normalized)
    for field_name, val in merged_identity.items():
        merged[field_name] = FieldValue(value=val, confidence=0.9, source="aggregation_service")

    # Non-aggregatable from primary
    merged.update(non_agg_fields)

    # ── Build AggregatedFields ───────────────────────────────────────────────
    confirmed_fields = ConfirmedFields(
        document_id=bundle_id,    # bundle_id is the sentinel document_id
        confirmed_fields=merged,
    )

    log.append(f"Merged {len(sessions)} documents into {len(merged)} fields")

    return AggregatedFields(
        bundle_id=bundle_id,
        source_document_ids=source_ids,
        confirmed_fields=confirmed_fields,
        aggregation_log=log,
    )
