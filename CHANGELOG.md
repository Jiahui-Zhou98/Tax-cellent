# Changelog

All notable changes to Tax-cellent are documented in this file.

## [1.0.0.0] - 2026-03-29 — Design Hardening + Multi-Form Support

### Added

- **1042-S form support.** Full OCR extraction, tax calculation, and 1040NR integration for 1042-S (Chapter 3/4 income and withholding). New `_calculate_1042s()` in tax_engine.py.
- **1099-MISC form support.** OCR extraction for rents, royalties, other income, and federal withholding.
- **Multi-document bundle API.** `POST /api/bundle` with add-document, confirm, aggregate, and status endpoints. `DocumentBundle` and `AggregatedFields` schemas. 16 unit tests in test_aggregation.py.
- **Combined tax calculator.** `_calculate_combined()` merges W-2 + 1099-NEC + 1042-S into a single 1040NR with unified withholding and SE tax. 187 test cases in test_engine.py.
- **CURRENT_TAX_YEAR constant.** Dynamic `date.today().year - 1` in tax_constants.py replaces 3 hardcoded "2024" values across backend and frontend.
- **Focus ring for keyboard accessibility.** CSS `focus-visible` rule in globals.css (WCAG 2.1 2.4.7). Removed `outline: none` from inputStyle.
- **DeadlineBanner hasIncome prop.** Zero-income NRA path now correctly shows June 15 deadline instead of April 15.
- **ZeroIncomeStep breadcrumb navigation.** "Upload > Form 8843" breadcrumb with clickable back link.
- **5 new TODOS** (20-24): CURRENT_TAX_YEAR constant, visual PDF test, legal disclaimer, _extract_step_amount test, combined filer test.

### Changed

- **StepBar mobile labels visible.** Changed from `hidden md:block` to `text-[10px] md:text-xs` so labels show on all screen sizes.
- **ZeroIncomeStep download button.** Color changed from cyan (#22d3ee) to blue (#2563eb) to match design system CTAs.
- **UploadStep layout.** Removed self-imposed `max-w-xl mx-auto` so parent container's `max-w-3xl` governs width consistently.
- **ExportButton filename.** Now uses dynamic tax year (`tax-package-{year}.pdf`) instead of hardcoded "2024".
- **ZeroIncomeStep CURRENT_YEAR.** Changed from hardcoded `2025` to `new Date().getFullYear() - 1`.

### Fixed

- **DeadlineBanner showed April 15 for zero-income NRAs.** Should be June 15 (Form 8843 only). Fixed by adding `hasIncome` parameter to `getDeadline()`.
- **Zero-income path had no navigation context.** Added breadcrumb and fade-in animation.
- **form_generator.py cover sheet fallback year.** Used `CURRENT_TAX_YEAR` instead of hardcoded 2024.
