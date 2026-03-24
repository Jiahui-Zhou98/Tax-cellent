"""IRS Form 8843 — AcroForm field name maps and coordinate fallback table.

Field name format notes
-----------------------
``get_fields()`` returns full XFA qualified paths, e.g.::

    "topmostSubform[0].Page1[0].f1_01[0]"

``update_page_form_field_values()`` matches against each annotation's ``/T``
attribute which is the LOCAL name only, e.g. ``"f1_01[0]"``.

Therefore:
  * FIELD_MAP_* values = local names (for filling via pypdf)
  * EXPECTED_FIELDS_* = full qualified paths (for validation via get_fields())

IMPORTANT: Verify field names each January when IRS publishes the new form.
Run::

    python -c "
    import pypdf; r=pypdf.PdfReader('backend/static/forms/f8843_{year}.pdf')
    import json; print(json.dumps(list(r.get_fields()), indent=2))"

Update the appropriate FIELD_MAP_* below, then re-run tests.
See CLAUDE.md "Form 8843 — Annual Maintenance" for full checklist.

Positional analysis (y-coordinate, top=792, bottom=0, Letter page):
    Run: python scripts/inspect_form_fields.py  (to be created)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 2025 form — 34 text + 6 checkbox fields on page 1, 8 text on page 2
# Zero-padded short names: f1_01[0] … f1_34[0], c1_1[0/1] … c1_3[0/1]
# ---------------------------------------------------------------------------

#                        y-pos analysis (top→bottom, page 1)
#  y≈696: f1_01 last_name | f1_02 first_name_mi | f1_03 tin
#  y≈672: f1_04 address_us | f1_05 city_state_zip | f1_06 address_foreign
#  y≈612: f1_07 city_foreign | f1_08 country_foreign
#  y≈588: f1_09 visa_type (Line 1)
#  y≈564: f1_10 date_arrived (Line 2 from)
#  y≈552: f1_11 date_left_or_present (Line 2 to)
#  y≈540: f1_12 days_us_current (Line 3)
#  y≈528: f1_13 days_us_prior  (Line 3, not filled)
#  y≈504: f1_14 inst_name | f1_15 inst_city | f1_16 inst_state
#  y≈492: f1_17 director_name (Line 5)
#  y≈444: f1_18 employer_name (Part III Line 6a)
#  y≈396: f1_19 employer_city_state (Part III Line 6b)
#  y≈384: f1_20 prior_exempt_years (Part III Line 7) | f1_21 (adjacent)
#  y≈372: f1_22 exchange_program | f1_23 sponsor_name | f1_24 sponsor_addr1 | f1_25 sponsor_addr2
#  y≈338: c1_1[0/1] status_change checkboxes
#  y≈264: f1_26 taxpayer_name_sign
#  y≈216: f1_27 sign_date
#  y≈204: f1_28 preparer_date | f1_29 preparer_phone
#  y≈192: f1_30…f1_33 preparer row
#  y≈170: c1_2[0/1] checkboxes
#  y≈110: c1_3[0/1] checkboxes
#  y≈ 72: f1_34 preparer_address

FIELD_MAP_2025: dict[str, str] = {
    # ── Header ────────────────────────────────────────────────
    "last_name":              "f1_01[0]",
    "first_name_mi":          "f1_02[0]",
    "tin":                    "f1_03[0]",
    "address_us":             "f1_04[0]",
    "city_state_zip_us":      "f1_05[0]",
    "address_foreign":        "f1_06[0]",
    "city_foreign":           "f1_07[0]",
    "country_foreign":        "f1_08[0]",
    # ── Part I — All Filers ───────────────────────────────────
    "visa_type":              "f1_09[0]",   # Line 1
    "date_arrived":           "f1_10[0]",   # Line 2 from
    "date_left_or_present":   "f1_11[0]",   # Line 2 to / "Present"
    "days_us_current":        "f1_12[0]",   # Line 3
    # ── Part II — Students ────────────────────────────────────
    "institution_name":       "f1_14[0]",   # Line 4a
    "institution_city":       "f1_15[0]",   # Line 4b
    "institution_state":      "f1_16[0]",   # Line 4c
    "director_name":          "f1_17[0]",   # Line 5
    # ── Part III — Teachers / Researchers ────────────────────
    "employer_name":          "f1_18[0]",   # Line 6a
    "employer_city_state":    "f1_19[0]",   # Line 6b
    "prior_exempt_years":     "f1_20[0]",   # Line 7
    # ── Part V — Exchange Visitors (J-1 / Q) ─────────────────
    "exchange_program":       "f1_22[0]",   # Line 9
    "sponsor_name":           "f1_23[0]",   # Line 10
    "sponsor_address":        "f1_24[0]",   # Line 11 (first line)
    # ── Signature ─────────────────────────────────────────────
    "taxpayer_name_sign":     "f1_26[0]",
    "sign_date":              "f1_27[0]",
    # ── Paid Preparer (optional) ──────────────────────────────
    "preparer_name":          "f1_30[0]",
    "preparer_ptin":          "f1_31[0]",
    "preparer_firm":          "f1_32[0]",
    "preparer_ein":           "f1_33[0]",
    "preparer_address":       "f1_34[0]",
    # ── Checkboxes ────────────────────────────────────────────
    "status_change_applied":  "c1_1[0]",    # Yes option
    "claimed_in_prior_6_yrs": "c1_2[0]",   # Yes option
}

# Full XFA-qualified paths for EXPECTED_FIELDS validation (get_fields() format)
_P1_2025 = "topmostSubform[0].Page1[0]."
_P2_2025 = "topmostSubform[0].Page2[0]."

EXPECTED_FIELDS_2025: set[str] = {
    _P1_2025 + v for v in FIELD_MAP_2025.values()
}

# ---------------------------------------------------------------------------
# 2024 form — 44 text + 6 checkbox fields on page 1 (plus Pg1Header subform),
# 15 text on page 2.  Non-zero-padded short names: f1_1[0] … f1_44[0].
#
# Positional analysis (y-coordinate, top→bottom, page 1):
#  y≈684: f1_1 last_name | f1_2 first_name_mi | f1_3 tin   (in Pg1Header subform)
#  y≈660: f1_4 address_us | f1_5 city_state_zip | f1_6 address_foreign
#  y≈600: f1_7 city_foreign | f1_8 country_foreign
#  y≈576: f1_9 visa_type (Line 1)
#  y≈552: f1_10 date_arrived  |  y≈540: f1_11 date_left_or_present
#  y≈528: f1_12 days_us_current  |  y≈516: f1_13 days_us_prior
#  y≈492: f1_14 inst_name | f1_15 inst_city | f1_16 inst_state
#  y≈480: f1_17 inst_phone/director (right side)
#  y≈456: f1_18 director_name
#  y≈444: f1_19 employer_name (Part III Line 6a)
#  y≈432: f1_20 employer_city_state (Part III Line 6b)
#  y≈408: f1_21 prior_exempt_years (Line 7)
#  y≈396: f1_22 exchange_program (Part V)
#  y≈384: f1_23 sponsor_name
#  y≈372: f1_24 sponsor_addr1 | f1_25 sponsor_addr2
#  y≈360: f1_26 sponsor_more1 | f1_27 … | f1_28 … | f1_29 …
#  y≈326: c1_1[0/1]
#  y≈276: f1_30 sign_date  |  y≈264: f1_31 taxpayer_name_sign
#  … remaining fields are preparer section and additional copies
# ---------------------------------------------------------------------------

FIELD_MAP_2024: dict[str, str] = {
    # ── Header ────────────────────────────────────────────────
    "last_name":              "f1_1[0]",
    "first_name_mi":          "f1_2[0]",
    "tin":                    "f1_3[0]",
    "address_us":             "f1_4[0]",
    "city_state_zip_us":      "f1_5[0]",
    "address_foreign":        "f1_6[0]",
    "city_foreign":           "f1_7[0]",
    "country_foreign":        "f1_8[0]",
    # ── Part I ────────────────────────────────────────────────
    "visa_type":              "f1_9[0]",
    "date_arrived":           "f1_10[0]",
    "date_left_or_present":   "f1_11[0]",
    "days_us_current":        "f1_12[0]",
    # ── Part II — Students ────────────────────────────────────
    "institution_name":       "f1_14[0]",
    "institution_city":       "f1_15[0]",
    "institution_state":      "f1_16[0]",
    "director_name":          "f1_18[0]",   # Line 5 (f1_17 = phone, f1_18 = director)
    # ── Part III — Teachers / Researchers ────────────────────
    "employer_name":          "f1_19[0]",
    "employer_city_state":    "f1_20[0]",
    "prior_exempt_years":     "f1_21[0]",
    # ── Part V — Exchange Visitors ────────────────────────────
    "exchange_program":       "f1_22[0]",
    "sponsor_name":           "f1_23[0]",
    "sponsor_address":        "f1_24[0]",
    # ── Signature ─────────────────────────────────────────────
    "taxpayer_name_sign":     "f1_31[0]",   # y≈264
    "sign_date":              "f1_30[0]",   # y≈276 (to the right of name)
    # ── Checkboxes ────────────────────────────────────────────
    "status_change_applied":  "c1_1[0]",
    "claimed_in_prior_6_yrs": "c1_2[0]",
}

# Full XFA paths for 2024.  Header fields f1_1..f1_3 live inside Pg1Header[0].
_P1_2024_HEADER = "topmostSubform[0].Page1[0].Pg1Header[0]."
_P1_2024       = "topmostSubform[0].Page1[0]."
_P2_2024       = "topmostSubform[0].Page2[0]."

_HEADER_FIELDS_2024 = {"f1_1[0]", "f1_2[0]", "f1_3[0]"}

EXPECTED_FIELDS_2024: set[str] = {
    (_P1_2024_HEADER if v in _HEADER_FIELDS_2024 else _P1_2024) + v
    for v in FIELD_MAP_2024.values()
}

# ---------------------------------------------------------------------------
# Canonical aliases — always point to the MOST RECENT form year.
# Update these aliases each year when a new form is published.
# ---------------------------------------------------------------------------

FIELD_MAP: dict[str, str] = FIELD_MAP_2025
EXPECTED_FIELDS: set[str] = EXPECTED_FIELDS_2025

# Year → (FIELD_MAP, EXPECTED_FIELDS) dispatch table
FIELD_MAPS: dict[int, dict[str, str]] = {
    2025: FIELD_MAP_2025,
    2024: FIELD_MAP_2024,
}
EXPECTED_FIELDS_BY_YEAR: dict[int, set[str]] = {
    2025: EXPECTED_FIELDS_2025,
    2024: EXPECTED_FIELDS_2024,
}

# ---------------------------------------------------------------------------
# Coordinate fallback table (reportlab units: points, origin bottom-left)
# Used when the PDF lacks named AcroForm fields (scanned or flat form).
# Page size: Letter 612 × 792 pt.  Measured on 2025 edition.
# ---------------------------------------------------------------------------
# Format: semantic_key -> (x, y, width, font_size)
COORD_FALLBACK: dict[str, tuple[float, float, float, int]] = {
    "last_name":          ( 72, 718, 180, 10),
    "first_name_mi":      (258, 718, 160, 10),
    "tin":                (424, 718, 116, 10),
    "visa_type":          ( 72, 688,  80, 10),
    "date_arrived":       (158, 688, 100, 10),
    "days_us_current":    (264, 688,  60, 10),
    "institution_name":   ( 72, 658, 240, 10),
    "institution_city":   (318, 658, 100, 10),
    "institution_state":  (424, 658,  60, 10),
    "prior_exempt_years": ( 72, 628, 200, 10),
    "exchange_program":   ( 72, 598, 200, 10),
    "sponsor_name":       ( 72, 568, 200, 10),
    "sponsor_address":    ( 72, 538, 360, 10),
    "sign_date":          (450, 100,  80, 10),
    "taxpayer_name_sign": ( 72, 100, 220, 10),
}
