"""IRS Form 1040NR — AcroForm field name maps and coordinate fallback table.

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
    import pypdf; r=pypdf.PdfReader('backend/static/forms/f1040nr_{year}.pdf')
    import json; print(json.dumps(list(r.get_fields()), indent=2))"

Update the appropriate FIELD_MAP_* below, then re-run tests.
See CLAUDE.md "Form 1040NR — Annual Maintenance" for full checklist.

CHECKBOX FIELDS: 1040NR has filing status checkboxes (/Btn type).
Pass "/Yes" to check a box, "/Off" to leave blank.
Never pass "" for checkboxes — use "/Off" for unchecked state.

READONLY FIELDS: Fields with Ff bit 0 set (Ff & 1 == 1) are auto-calculated
by PDF JavaScript. Do NOT pass values for these — pypdf will attempt to set them
but the embedded JS recalculates on open. Omit them from the fill dict entirely.
ReadOnly local names (2024): f1_51[0], f1_52[0], f1_65[0], f2_29[0]

FILL POLICY: For optional/conditional text fields with no value, pass "" (empty
string). Never pass "0" for empty numeric fields — pypdf treats "" as "leave
blank" while "0" would render a zero on the printed form.

MULTI-PAGE FILL: Loop all writer.pages and call update_page_form_field_values on
each page. AcroForm field names are globally unique across pages — the same call
interface works for both page 1 and page 2 fields.

Treaty lines (Part IV / Schedule OI): fill only when treaty_amount > 0.
Schedule OI lines: fill only when visa_type is in NRA_VISA_TYPES.

Positional analysis (y-coordinate, bottom=0, top=792, Letter page 612×792 pt):
    Run: python scripts/inspect_form_fields.py  (to be created)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 2024 form
# Page 1: text fields f1_01[0]…f1_71[0], checkboxes c1_1[0]…c1_25[0]
# Page 2: text fields f2_01[0]…f2_56[0], checkboxes c2_1[0]…c2_8[0]
#
# Field naming convention:
#   f1_NN[0]  = page 1 text field
#   f2_NN[0]  = page 2 text field
#   c1_N[0]   = page 1 checkbox (/Btn)
#   c2_N[0]   = page 2 checkbox (/Btn)
#
# Positional analysis (y-coordinate, bottom→top, page 1):
#  y≈720: f1_01 first_name_mi | f1_02 last_name | f1_03 name_suffix
#  y≈710: c1_1 filing_status_single | c1_2 filing_status_mfs | c1_3 filing_status_qss
#  y≈698: c1_4 filing_status_estate
#  y≈708: f1_04 address_us (home address)
#  y≈696: f1_11 city_or_town | f1_12 province_state | f1_13 postal_code
#  y≈666: f1_14 country_of_citizenship | f1_15 country_of_residence | f1_16 tin
#  y≈384: f1_42 wages_line_1a (W-2 Box 1)
#  y≈372: f1_43 wages_line_1b (household employee wages)
#  y≈360: f1_44 wages_line_1c (tip income)
#  y≈288: f1_51 wages_total_1i [READONLY — auto-calculated]
#  y≈252: f1_53 wages_line_1k (Line 1k, total wages after offset)
#  y≈240: f1_54 nec_income_line_2 (Line 2, NEC from Schedule NEC)
#  y≈228: f1_55 line_3_desc | f1_56 line_3_amount (capital gains)
#  y≈168: f1_62 other_income_line_7 | f1_63 total_income_line_8
#  y≈ 72: f1_70 taxable_income (Line 15)
#  y≈ 60: f1_71 tax (Line 16)
#
# Positional analysis (y-coordinate, bottom→top, page 2):
#  y≈732: f2_01 other_tax_line_17
#  y≈714: f2_02 add_taxes_line_18
#  y≈702: f2_03 withholding_w2 (Line 25a — W-2 Box 2)
#  y≈690: f2_04 withholding_nec (Line 25b — 1099 withholding)
#  y≈678: f2_05 withholding_other (Line 25c — other withholding)
#  y≈666: f2_06 total_withholding (Line 25d — total)
#  y≈654: f2_07 other_payments_line_26
#  y≈642: f2_09 total_payments_line_27
#  y≈630: f2_10 overpaid_line_35
#  y≈618: f2_11 refund_line_36a
#  y≈594: f2_13 amount_owed_line_37
#  y≈582: f2_14 est_tax_penalty_line_38
#  y≈378: f2_29 nec_subtotal [READONLY — auto-calculated]
#  y≈265: f2_38 ein_or_id (9-char identifier)
#  y≈252: f2_39 treaty_article (MaxLen=17, Schedule OI)
#  y≈230: f2_40 treaty_country (wide text, Schedule OI)
#  y≈216: f2_41 treaty_amount_exempt
#  y≈198: f2_42 treaty_income_amount
#  y≈152: f2_44 taxpayer_name_sign | f2_45 sign_date | f2_46 year
# ---------------------------------------------------------------------------

FIELD_MAP_2024: dict[str, str] = {
    # ── Header — Personal Information ─────────────────────────────────
    "first_name_mi":              "f1_01[0]",  # First name + middle initial (Comb)
    "last_name":                  "f1_02[0]",  # Last name (Comb)
    "tin":                        "f1_16[0]",  # SSN or ITIN — MaxLen=9, Comb+RichText
    # ── Filing Status (checkboxes: "/Yes" to check, "/Off" to leave blank) ──
    "filing_status_single":       "c1_1[0]",   # Single (most common for NRA students)
    "filing_status_mfs":          "c1_2[0]",   # Married Filing Separately
    "filing_status_qss":          "c1_3[0]",   # Qualifying Surviving Spouse
    "filing_status_estate":       "c1_4[0]",   # Estate or Trust
    # ── Address ───────────────────────────────────────────────────────
    "address_us":                 "f1_04[0]",  # US home address (street + apt)
    "city_or_town":               "f1_11[0]",  # City/town (Comb)
    "province_state":             "f1_12[0]",  # Province or state (Comb)
    "postal_code":                "f1_13[0]",  # Postal/ZIP code (Comb)
    # ── Country Information ────────────────────────────────────────────
    "country_of_citizenship":     "f1_14[0]",  # Country of citizenship (Comb, wide)
    "country_of_residence":       "f1_15[0]",  # Tax-home country (Comb, wide)
    # ── Part I — Income — Wages (W-2 filers only) ─────────────────────
    "wages_line_1a":              "f1_42[0]",  # Line 1a: W-2 Box 1 wages (Comb)
    "wages_line_1b":              "f1_43[0]",  # Line 1b: household employee wages
    "wages_line_1c":              "f1_44[0]",  # Line 1c: tip income
    # f1_51[0] = wages_total_1i (READONLY — auto-calculated, do NOT fill)
    "wages_line_1k":              "f1_53[0]",  # Line 1k: total wages after offsets
    # ── Part I — Income — NEC (1099-NEC filers only) ──────────────────
    "nec_income_line_2":          "f1_54[0]",  # Line 2: NEC total from Schedule NEC
    # ── Part I — Other Income ──────────────────────────────────────────
    "capital_gain_line_3":        "f1_56[0]",  # Line 3: capital gain or (loss)
    "total_income_line_8":        "f1_63[0]",  # Line 8: total income (sum of sources)
    # ── Part I — Deductions and Taxable Income ─────────────────────────
    # f1_65[0] = deduction subtotal (READONLY — auto-calculated, do NOT fill)
    "total_deductions":           "f1_69[0]",  # Total deductions
    "taxable_income":             "f1_70[0]",  # Line 15: taxable income
    "tax":                        "f1_71[0]",  # Line 16: tax (from tax tables/schedules)
    # ── Page 2 — Other Taxes ──────────────────────────────────────────
    "other_tax_line_17":          "f2_01[0]",  # Line 17: other taxes
    "add_taxes_line_18":          "f2_02[0]",  # Line 18: add'l taxes (Sec 72(m), etc.)
    # ── Page 2 — Payments / Withholding ───────────────────────────────
    "withholding_w2":             "f2_03[0]",  # Line 25a: W-2 Box 2 federal withholding
    "withholding_nec":            "f2_04[0]",  # Line 25b: 1099 federal tax withheld
    "withholding_other":          "f2_05[0]",  # Line 25c: other withholding
    "total_withholding":          "f2_06[0]",  # Line 25d: total withholding
    "other_payments_line_26":     "f2_07[0]",  # Line 26: other credits/payments
    "total_payments_line_27":     "f2_09[0]",  # Line 27: total payments
    "overpaid_line_35":           "f2_10[0]",  # Line 35: amount overpaid
    "refund_line_36a":            "f2_11[0]",  # Line 36a: amount to be refunded
    "applied_to_est_tax":         "f2_12[0]",  # Line 36b: applied to next year
    "amount_owed_line_37":        "f2_13[0]",  # Line 37: amount you owe
    "est_tax_penalty_line_38":    "f2_14[0]",  # Line 38: estimated tax penalty
    # ── Schedule OI / Treaty (fill only when treaty_amount > 0) ───────
    "treaty_article":             "f2_39[0]",  # Treaty article citation — MaxLen=17
    "treaty_country":             "f2_40[0]",  # Treaty country name (wide text)
    "treaty_amount_exempt":       "f2_41[0]",  # Amount exempt under treaty
    "treaty_income_amount":       "f2_42[0]",  # Total income subject to treaty
    # ── Signature ─────────────────────────────────────────────────────
    "taxpayer_name_sign":         "f2_44[0]",  # Taxpayer signature (type name)
    "sign_date":                  "f2_45[0]",  # Date signed
}

# ---------------------------------------------------------------------------
# Full XFA-qualified paths for EXPECTED_FIELDS validation (get_fields() format)
# Fields named f1_*/c1_* live on page 1; f2_*/c2_* live on page 2.
# ---------------------------------------------------------------------------
_P1_2024 = "topmostSubform[0].Page1[0]."
_P2_2024 = "topmostSubform[0].Page2[0]."


def _xfa_2024(local: str) -> str:
    """Return full XFA-qualified path from a 2024 1040NR local field name."""
    if local.startswith(("f1_", "c1_")):
        return _P1_2024 + local
    return _P2_2024 + local


EXPECTED_FIELDS_2024: set[str] = {
    _xfa_2024(v) for v in FIELD_MAP_2024.values()
}

# ---------------------------------------------------------------------------
# Canonical aliases — always point to the MOST RECENT form year.
# Update these aliases each January when IRS publishes a new form.
# ---------------------------------------------------------------------------

FIELD_MAP: dict[str, str] = FIELD_MAP_2024
EXPECTED_FIELDS: set[str] = EXPECTED_FIELDS_2024

# Year → FIELD_MAP and EXPECTED_FIELDS dispatch tables
FIELD_MAPS: dict[int, dict[str, str]] = {
    2024: FIELD_MAP_2024,
    2025: FIELD_MAP_2024,  # 2025 uses same field IDs (placeholder until IRS publishes new form)
}
EXPECTED_FIELDS_BY_YEAR: dict[int, set[str]] = {
    2024: EXPECTED_FIELDS_2024,
    2025: EXPECTED_FIELDS_2024,  # placeholder
}

# ---------------------------------------------------------------------------
# ReadOnly field local names (Ff bit 0 set — auto-calculated by PDF JS).
# Do NOT include these in the fill dict passed to update_page_form_field_values.
# Attempting to fill them is harmless but the PDF will recalculate on open.
# ---------------------------------------------------------------------------
READONLY_FIELDS_2024: frozenset[str] = frozenset({
    "f1_51[0]",  # Line 1i: auto-sum of wages lines 1a–1h
    "f1_52[0]",  # Intermediate wages calculation
    "f1_65[0]",  # Deduction subtotal (auto-calculated)
    "f2_29[0]",  # Schedule NEC subtotal (auto-calculated)
})

# ---------------------------------------------------------------------------
# Checkbox field local names — value "/Yes" to check, "/Off" to leave blank.
# NEVER pass "" for these — use "/Off" for the unchecked state.
# ---------------------------------------------------------------------------
CHECKBOX_FIELDS_2024: frozenset[str] = frozenset({
    "c1_1[0]", "c1_2[0]", "c1_3[0]", "c1_4[0]",   # page 1 filing status
    "c2_1[0]", "c2_2[0]", "c2_3[0]",               # page 2 payment type
    "c2_5[0]",                                       # page 2 NEC area
    "c2_6[0]",                                       # page 2 treaty yes/no
    "c2_7[0]",                                       # page 2 other checkbox
})

# ---------------------------------------------------------------------------
# Coordinate fallback table (reportlab units: points, origin bottom-left)
# Used when pypdf silent-fill fails on the IRS AcroForm (scanned or flat form).
# Page size: Letter 612 × 792 pt.  Measured on 2024 edition.
# ---------------------------------------------------------------------------
# Format: semantic_key -> (x, y, width, font_size)
COORD_FALLBACK: dict[str, tuple[float, float, float, int]] = {
    "first_name_mi":           (229, 712,  88, 10),
    "last_name":               (366, 712,  88, 10),
    "tin":                     (469, 658,  72, 10),
    "country_of_citizenship":  ( 36, 658, 208, 10),
    "address_us":              (210, 700, 161, 10),
    "city_or_town":            ( 66, 688, 171, 10),
    "postal_code":             (411, 688, 165, 10),
    # Income fields (right column x≈504–576)
    "wages_line_1a":           (504, 376,  72, 10),
    "wages_line_1k":           (410, 244,  72, 10),
    "nec_income_line_2":       (504, 232,  72, 10),
    "total_income_line_8":     (504, 160,  72, 10),
    "taxable_income":          (504,  64,  72, 10),
    "tax":                     (504,  52,  72, 10),
    # Withholding (middle column x≈410–482)
    "withholding_w2":          (410, 694,  72, 10),
    "withholding_nec":         (410, 682,  72, 10),
    "total_withholding":       (504, 658,  72, 10),
    "total_payments_line_27":  (504, 634,  72, 10),
    "refund_line_36a":         (504, 610,  72, 10),
    "amount_owed_line_37":     (504, 586,  72, 10),
    # Treaty (Schedule OI area, page 2)
    "treaty_article":          (180, 244, 245, 10),
    "treaty_country":          (166, 222, 310, 10),
    "treaty_amount_exempt":    (410, 208,  72, 10),
    # Signature
    "taxpayer_name_sign":      (130, 144, 165, 10),
    "sign_date":               (324, 144,  94, 10),
}
