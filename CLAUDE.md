# Tax-cellent Project Notes

## Critical Sync Points

### NRA_VISA_TYPES — Must be kept in sync across both files:
- `backend/app/constants/tax_constants.py` → `NRA_VISA_TYPES`
- `frontend/app/lib/constants.ts` → `NRA_VISA_TYPES`

If you add or remove a visa type, update BOTH files. This constant drives:
- Backend: whether to generate `Form8843Data` in `tax_engine.calculate()`
- Frontend: whether to show `Form8843Card` in `CalculationLedgerStep`

Drift between these two files will cause the income-path 8843 card to silently not appear for newly-added visa types (or appear for types that shouldn't trigger it).

## Form 8843 — Annual Maintenance (January)

1. Download new IRS Form 8843 PDF from irs.gov/pub/irs-pdf/f8843.pdf
2. Run `scripts/fetch_irs_forms.sh` to update prior-year templates with checksums
3. Verify AcroForm field names haven't changed (run `python -c "import pypdf; print(pypdf.PdfReader('backend/static/forms/f8843_{year}.pdf').get_fields())"`)
4. Update `backend/app/constants/form_8843_fields.py` if field names changed
5. Re-run `backend/tests/test_form_8843.py`

See also: TODO-8 (1040-NR annual update, same window).

## Design System

See `docs/designs/form-8843-zero-income.md` for the Form 8843 zero-income path design.
See `docs/designs/nra-platform.md` for the broader NRA platform roadmap.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
