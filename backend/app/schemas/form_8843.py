"""Pydantic schema for IRS Form 8843 (Statement for Exempt Individuals).

Form 8843 must be filed by ALL individuals on F-1/F-2/J-1/J-2/M-1/M-2/Q visas,
regardless of income.  It is never e-filed — always paper-mailed.

Filing paths:
  Zero-income:  standalone 8843 → Austin, TX → due June 15
  With income:  attach behind 1040-NR → Philadelphia, PA → due April 15
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Form8843Data(BaseModel):
    """Data required to fill IRS Form 8843 for a single tax year.

    Part I  — Students (F-1 as student, M-1, M-2, Q as student).
    Part II — Teachers/Researchers (J-1 or Q as teacher/researcher).

    ``role`` drives Part I vs Part II routing:
      "student"             → fill Part I only  (F-1/M-1 always student)
      "teacher_researcher"  → fill Part II  (J-1/Q when role radio = teacher)

    ``tin_status`` drives Line 2 (taxpayer identification number):
      "ssn"         → print the SSN value from tin_value
      "itin"        → print the ITIN value from tin_value
      "applied_for" → print "Applied for"  (student awaiting ITIN)
      "none"        → print "N/A"          (standalone 8843, no TIN required)
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    first_name: str = ""
    last_name: str = ""
    tin_status: Literal["ssn", "itin", "applied_for", "none"] = "none"
    # tin_value: omit for "none" / "applied_for"; only present when ssn/itin
    tin_value: Optional[str] = None

    # ── Visa / residency ─────────────────────────────────────────────────────
    visa_type: str = ""
    first_us_entry_date: Optional[str] = None  # YYYY or YYYY-MM-DD (Line 3a start)
    days_in_us_current_year: Optional[int] = None  # Line 3a

    # ── Part I — Students ────────────────────────────────────────────────────
    role: Literal["student", "teacher_researcher"] = "student"
    institution_name: Optional[str] = None   # Line 4a: academic institution name
    institution_city: Optional[str] = None   # Line 4b: city
    institution_state: Optional[str] = None  # Line 4c: state (2-letter)

    # Line 7: calendar years the individual previously claimed exempt status.
    # The count of items drives the "number of years" box on Form 8843.
    # Example: [2022, 2023, 2024] → 3 prior exempt years.
    exempt_prior_years: list[int] = []

    # Line 8: applied for change of nonimmigrant status during tax year
    status_change_applied: bool = False

    # ── Part II — Teachers / Researchers (J-1 or Q visa) ─────────────────────
    exchange_program_name: Optional[str] = None   # Line 9
    sponsor_name: Optional[str] = None            # Line 10: sponsoring organization
    sponsor_address: Optional[str] = None         # Line 10: organization address
    years_claimed_exemption: Optional[int] = None # Line 11: years claimed as T/R
    claimed_in_prior_6_years: Optional[bool] = None  # Line 12

    # ── Filing metadata ───────────────────────────────────────────────────────
    # has_income drives:
    #   False → standalone 8843 (Austin TX, June 15 deadline)
    #   True  → attached behind 1040-NR (Philadelphia PA, April 15 deadline)
    has_income: bool = False

    # Tax year selects PDF template: backend/static/forms/f8843_{tax_year}.pdf
    tax_year: int = 2025

    # Prior years being filed as catch-up returns (generates one PDF per year).
    # Distinct from exempt_prior_years — these are years whose 8843 was NEVER filed.
    # Example: [2023, 2022] → generate two additional PDFs (+ current tax_year).
    catch_up_years: list[int] = []
