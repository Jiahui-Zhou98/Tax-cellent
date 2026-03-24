"""IRS Form 8843 — AcroForm field name map and coordinate fallback table.

IMPORTANT: Verify field names each January when IRS publishes the new form.
Run:  python -c "import pypdf; print(pypdf.PdfReader('backend/static/forms/f8843_{year}.pdf').get_fields())"
Update FIELD_MAP below if names changed, then re-run backend/tests/test_form_8843.py.
See CLAUDE.md "Form 8843 — Annual Maintenance" for full checklist.
"""

# ---------------------------------------------------------------------------
# AcroForm field name map
# Keys  = semantic names used in form_generator.py
# Values = PDF AcroForm widget /T (field name) strings
# ---------------------------------------------------------------------------
# Source: pypdf.PdfReader("backend/static/forms/f8843_2024.pdf").get_fields()
# IRS uses a two-layer key pattern: short widget names like "f1_01" through "f1_xx"
# for data fields and "c1_1" etc. for check boxes.
FIELD_MAP: dict[str, str] = {
    # Part I header info
    "last_name":              "f1_01",
    "first_name_mi":          "f1_02",
    "tin":                    "f1_03",
    "address_us":             "f1_04",
    "city_state_zip_us":      "f1_05",
    "address_foreign":        "f1_06",
    "city_foreign":           "f1_07",
    "country_foreign":        "f1_08",
    # Line 1 — visa type
    "visa_type":              "f1_09",
    # Line 2 — dates of current visit
    "date_arrived":           "f1_10",
    "date_left_or_present":   "f1_11",
    # Line 3 — days in US current year
    "days_us_current":        "f1_12",
    # Lines 4a/4b/4c — institution
    "institution_name":       "f1_13",
    "institution_city_state": "f1_14",
    "institution_phone":      "f1_15",
    # Line 5 — student director/DSO name
    "director_name":          "f1_16",
    # Part II (teacher/researcher) — lines 6-7
    "employer_name":          "f1_17",
    "employer_city_state":    "f1_18",
    # Line 7 — years previously claimed
    "prior_exempt_years":     "f1_19",
    # Part III (J-1/Q) — line 8
    "exchange_program":       "f1_20",
    "sponsor_name":           "f1_21",
    "sponsor_address":        "f1_22",
    # Signature area
    "taxpayer_name_sign":     "f1_23",
    "sign_date":              "f1_24",
    # Paid preparer section
    "preparer_name":          "f1_25",
    "preparer_ptin":          "f1_26",
    "preparer_firm":          "f1_27",
    "preparer_ein":           "f1_28",
    "preparer_phone":         "f1_29",
    "preparer_address":       "f1_30",
    # Checkboxes
    "status_change_applied":  "c1_1",
    "claimed_in_prior_6_yrs": "c1_2",
}

# Canonical set of expected AcroForm field names — used at startup to confirm
# the downloaded PDF has the expected widget tree.  If any name is absent the
# generator falls back to the reportlab coordinate overlay (see COORD_FALLBACK).
EXPECTED_FIELDS: set[str] = set(FIELD_MAP.values())

# ---------------------------------------------------------------------------
# Coordinate fallback table (reportlab units: points, origin bottom-left)
# Used when the PDF lacks named AcroForm fields (scanned or flat form).
# Page size: Letter 612 × 792 pt.  Measured on 2024 edition.
# ---------------------------------------------------------------------------
# Format: semantic_key -> (x, y, width, font_size)
COORD_FALLBACK: dict[str, tuple[float, float, float, int]] = {
    "last_name":              (72,  718, 180, 10),
    "first_name_mi":          (258, 718, 160, 10),
    "tin":                    (424, 718, 116, 10),
    "visa_type":              (72,  688,  80, 10),
    "date_arrived":           (158, 688, 100, 10),
    "days_us_current":        (264, 688,  60, 10),
    "institution_name":       (72,  658, 240, 10),
    "institution_city_state": (318, 658, 160, 10),
    "prior_exempt_years":     (72,  628, 200, 10),
    "exchange_program":       (72,  598, 200, 10),
    "sponsor_name":           (72,  568, 200, 10),
    "sponsor_address":        (72,  538, 360, 10),
    "sign_date":              (450, 100,  80, 10),
    "taxpayer_name_sign":     (72,  100, 220, 10),
}
