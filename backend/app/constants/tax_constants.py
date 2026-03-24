"""NRA visa type constants shared between tax engine and form generation.

SYNC WARNING: NRA_VISA_TYPES is replicated in frontend/app/lib/constants.ts.
Run `python scripts/sync_constants.py` to regenerate the TypeScript copy.
Do NOT edit the TypeScript copy directly — it will be overwritten.
See CLAUDE.md for sync maintenance instructions.
"""

# Visa types that require filing Form 8843 (Statement for Exempt Individuals).
# Used by:
#   - tax_engine.calculate() → attach Form8843Data to TaxReport
#   - frontend/app/lib/constants.ts → show Form8843Card in CalculationLedgerStep
#
# F-2/J-2 dependents: included here because they also must file Form 8843.
#   Income path: Form8843Card is shown in CalculationLedgerStep for all visa types below.
#   Zero-income path: ZeroIncomeStep shows "Coming soon" for F-2/J-2 only (household
#   bundling deferred; each dependent needs their own Form 8843).
NRA_VISA_TYPES: list[str] = ["F-1", "F-2", "J-1", "J-2", "M-1", "M-2", "Q"]
