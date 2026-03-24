# TODOS

Design and product debt tracked here. Items added by /plan-design-review on 2026-03-21.

---

## ~~TODO-1: Create DESIGN.md — Design System Formalization~~ ✅ DONE 2026-03-22

**What:** Extract the app's design tokens (color palette, border radii, shadows, spacing scale, typography) from inline styles in `page.tsx` into a single `DESIGN.md` document.

**Why:** The dark-terminal aesthetic is coherent but lives entirely in scattered inline styles. As the app grows (component split Exp 6, new Settings step, Form 843 card), tokens will drift. A DESIGN.md gives future contributors a reference for the intentional palette.

**Pros:** Prevents visual inconsistency as components multiply. Enables `/design-consultation` to build on an existing foundation. Makes the aesthetic replicable across new features.

**Cons:** Low immediate value while still a single-file app. The aesthetic is already consistent — this is documentation, not new capability.

**Context:** The CEO plan (2026-03-21) already lists this in the "Deferred" section. The `/plan-design-review` review confirmed the aesthetic is consistent; this is a formalization pass, not a fix.

**Depends on / blocked by:** Nothing. Can be done independently at any time.

---

## ~~TODO-2: Full App Accessibility Audit~~ ✅ DONE 2026-03-22

**What:** A systematic a11y pass covering the full app beyond the Settings step provider picker (which has a11y specified as part of Exp 1).

**Why:** Identified high-risk gaps:
- `FieldRow` inputs have no `<label>` element — uses visual `<span>` only; screen readers won't announce the field name
- `StepBar` step circles have no `aria-label` (e.g. `aria-label="Step 3: Review Fields, completed"`)
- Calculation ledger rows use `<button>` for expand/collapse but no ARIA expanded state (`aria-expanded`)
- `confColor()` uses color alone to signal confidence — no text alternative for colorblind users

**Pros:** Makes the app usable by screen reader users. Required for any university partnership or official distribution. Low implementation cost with CC.

**Cons:** No immediate user-visible change for the majority of users. Can feel like polish-only work.

**Context:** The design review specified a11y only for the new Settings step (Exp 1). The rest of the app was out of scope for this review iteration.

**Depends on / blocked by:** Exp 6 (component split) — easier to add a11y to individual component files than to one 1400-line file. Do this after Exp 6 lands.

**Completed:** All four identified gaps fixed across 6 component files. See commit for details.

---

## ~~TODO-3: Form 843 PDF Download~~ ✅ DONE 2026-03-22

**What:** A "Download as PDF" button on the Form 843 pre-fill card in the Report step. The minimal implementation uses `window.print()` with a `@media print` CSS block that isolates the Form 843 card and formats it for letter paper.

**Why:** Copy-paste to a text editor then mail is friction-heavy. Students who want to mail the Form 843 need a printable artifact. The IRS accepts typed forms. A print-to-PDF flow produces a document they can attach to their return.

**Pros:** Significant UX improvement over clipboard copy for the primary user action (actually mailing the form). `window.print()` requires no extra library. Impressive demo feature.

**Cons:** `@media print` CSS adds complexity. The print layout needs to be tested across browsers. True PDF pre-fill into the official IRS form (using a PDF library + form field injection) is a much larger lift.

**Context:** The CEO plan's 10x vision is "Form 843 draft ready to mail." Copy-paste covers the minimum; PDF download completes the vision. This TODO represents the delta between 80% and 100%.

**Depends on / blocked by:** Exp 2 (Form 843 pre-fill card) must be implemented first. Start here after Exp 2 ships.

---

## ~~TODO-4: Configurable CORS Origins~~ ✅ DONE 2026-03-22

**What:** Replace the hardcoded `allow_origins=["http://localhost:3000"]` in `backend/app/main.py` with a configurable env var `CORS_ORIGINS`.

**Why:** The 10x vision is university-hosted deployment. Any non-localhost deployment will hit CORS errors until this is fixed. Currently there's no way to configure allowed origins without editing source code.

**Pros:** Required for any non-localhost deployment. 3-line change. Zero risk.

**Cons:** None meaningful.

**Context:** Flagged by /plan-eng-review (2026-03-21). Add `CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"` to `config.py` and split by comma in `main.py`. The `allow_origins` list populates from this env var.

**Depends on / blocked by:** Nothing.

---

## ~~TODO-5: Run candidate_extractor in Thread Pool~~ ✅ DONE 2026-03-22

**What:** Wrap `extract_candidates(parsed_json)` in `asyncio.to_thread()` inside `extraction_service.py:extract_fields_structured()`.

**Why:** `candidate_extractor.py` is 1,142 lines of synchronous CPU work running inside an `async` FastAPI handler. For multi-page PDFs, this blocks the event loop and prevents the server from handling concurrent requests.

**Pros:** Frees the event loop during extraction. One-line change. Standard FastAPI pattern.

**Cons:** `to_thread` adds minor overhead for small PDFs. Negligible in practice.

**Context:** Flagged by /plan-eng-review (2026-03-21). The extraction pipeline already has `from __future__ import annotations` and is async-compatible — the only change is wrapping the sync call with `await asyncio.to_thread(extract_candidates, parsed_json)`.

**Depends on / blocked by:** Nothing.

---

## ~~TODO-6: Form 1040-NR vs 1040 Filing Determination~~ ✅ DONE 2026-03-22

**What:** Add a determination step in `tax_engine.py` that detects whether the user should file Form 1040-NR (nonresident alien) vs Form 1040 (resident alien), and applies the correct tax rates and deduction rules accordingly.

**Why:** The app currently always applies Form 1040 logic (standard deduction, resident-alien brackets). F-1/J-1 students in their first 5 calendar years in the US are almost certainly nonresident aliens (NRAs) who must file 1040-NR, which has no standard deduction and uses different rate schedules. Showing a 1040 estimate to an NRA produces a materially wrong result (over-estimates their refund by ~$2,000+ for a typical student).

**Pros:** Closes the biggest accuracy gap for the primary target user. Makes the tool's estimates defensible. All the data needed (visa_type, days_in_us, first_us_entry_date) is already in UserContext.

**Cons:** Requires IRS Publication 519 NRA bracket tables (2025 not yet published; use 2024 as proxy). Substantial additions to `tax_engine.py`. The substantial presence test (183-day rule with weighting) is complex to implement fully. State NRA rules add another layer.

**Context:** Flagged by /plan-ceo-review (2026-03-22) as "the biggest accuracy gap for the primary user type." The residency determination is already partially seeded: `_is_fica_exempt()` uses `first_us_entry_date` and `years_elapsed < 5`, which is the core of the NRA test for F-1 students. Extend this logic to drive the deduction and bracket selection.

**Depends on / blocked by:** Can be built independently after the 1099-NEC PR.

**Depends on / blocked by:** Can be built independently after the 1099-NEC PR.

---

## ~~TODO-7: State Income Tax Estimates~~ ✅ DONE 2026-03-22

**What:** Add optional state income tax calculation for the most common US states where international students reside: CA, NY, TX, WA, IL, MA. (TX and WA have no income tax.) Add a state dropdown to ContextStep.

**Why:** A student expecting a federal refund may simultaneously owe substantial state income tax (California top rate 13.3%). The app's federal-only estimate is incomplete for high-tax-state residents and may leave users underprepared.

**Pros:** Materially more complete picture. The ContextStep infrastructure already collects user info. State brackets are stable and can be hardcoded like the federal tables.

**Cons:** Requires per-state bracket tables (6 states × ~7 brackets = ~42 rows). State NRA treatment varies. Adds UI complexity (state dropdown). Requires annual updates.

**Context:** Flagged by /plan-ceo-review (2026-03-22). Focus on the 6 highest-enrollment international student states first. Can show "state estimate unavailable" for other states rather than nothing.

**Depends on / blocked by:** TODO-6 (1040-NR determination) would provide helpful context on NRA state treatment, but state estimates can launch as resident-alien calculations first.

---

## ~~TODO-8: 1040-NR PDF Template Annual Update Obligation~~ ✅ DONE 2026-03-22

**What:** Each January, when the IRS publishes the new tax-year 1040-NR PDF, extract the updated AcroForm field IDs, diff against the prior-year mapping table in `generate_1040nr_pdf.py`, update any changed field names, and re-run the accuracy test suite to confirm field mapping is correct.

**Why:** IRS AcroForm field IDs change when form layout changes (e.g., a new line is added). If the mapping table is stale, the generated PDF will silently write values to the wrong fields — users could mail an incorrectly-mapped return to the IRS.

**Pros:** Prevents silent accuracy regression on the highest-stakes output (the mailable return). The fix each year is a diff + table update, not a rewrite. The accuracy test suite validates the result automatically.

**Cons:** Requires manual attention every January. If the IRS delays publishing the new form (common), the update is blocked until it ships. Teams without tax calendar awareness will miss this.

**Context:** Flagged by /plan-ceo-review (2026-03-22) as part of the NRA Platform plan (Exp 3: 1040-NR PDF generation). The field extraction script (to be written as part of Exp 3) should live in `scripts/extract_1040nr_fields.py` and produce a mapping diff. The maintenance window is January–February before the April filing deadline.

**Effort:** S (human: ~2 hours / CC: ~10 min per update cycle)

**Priority:** P1 — must not be missed; user-facing harm if skipped.

**Depends on / blocked by:** Exp 3 (1040-NR PDF generation) must ship first.

**Completed:** `scripts/extract_1040nr_fields.py` created with full AcroForm extraction + diff-against-FIELD_MAP logic (gracefully stubs when Exp 3 not yet present). `pypdf==4.3.1` added to requirements.txt. 11 unit tests in `backend/tests/test_extract_fields.py`. Diff logic will be fully active once Exp 3 ships `generate_1040nr_pdf.py` with `FIELD_MAP` constant.

---

## ~~TODO-9: Treaty Table Expansion Beyond Top 10 Countries~~ ✅ DONE 2026-03-22

**What:** Expand the `TREATY_TABLE` in `tax_engine.py` from the top 10 student-origin countries (CN, KR, CA, GB, DE, JP, MX, IN, BR, SA) to the full set of 68 IRS treaty countries. For each country: article citation, income type (scholarship/wages), annual cap, and maximum years of eligibility.

**Why:** A student from Thailand, France, the Philippines, or any of the other ~58 treaty countries will currently hit the `NO_TREATY` fallback and receive an incorrect estimate. The top 10 covers ~70% of international students; adding the next 20 gets to ~90%.

**Pros:** Pure lookup-table work — no new logic. Each row is a citation from IRS Publication 901. Directly improves accuracy for a large cohort. Parallelizable with a research agent.

**Cons:** Requires reading 58 country-specific articles from IRS Pub 901. Annual updates needed (treaties change). Some treaties have complex multi-tiered caps that need design decisions (cap by degree level, etc.).

**Context:** Flagged by /plan-ceo-review (2026-03-22). Source data: IRS Publication 901 (updated annually), Table 1 (students and apprentices). The existing `TREATY_TABLE` structure in the plan is the correct schema — just add rows.

**Effort:** M (human: ~1 day / CC: ~20 min with Pub 901 research)

**Priority:** P2 — meaningful accuracy gap but top 10 covers the majority of users.

**Depends on / blocked by:** Exp 2 (treaty calculation engine) must ship first.

**Completed:** Full 68-country `TREATY_TABLE` added to `tax_engine.py` with article citation, annual cap, and max years per IRS Publication 901. `compute_report_extras()` function implements treaty lookup and ITIN detection. `country_of_origin` added to `UserContext` schema and `ContextStep.tsx`.

---

## ~~TODO-10: Prior-Year Filing Flag~~ ✅ DONE 2026-03-22

**What:** Detect the tax year from uploaded documents (W-2 Box c, 1042-S Box 1, 1099 header), compare to the current tax year, and show a warning banner if there is a mismatch: "This document is from [year] — you may need to file a late return or amended return, not a [current year] return."

**Why:** International students who missed a prior filing deadline (common for first-year F-1s who were unaware) will upload a 2023 W-2 expecting 2023 guidance. The app currently applies 2024 brackets and rates to it silently. This produces a wrong estimate and could lead a user to underpay or overpay.

**Pros:** Closes a silent accuracy failure. The tax year is already embedded in document metadata that the extraction pipeline parses. The fix is a year comparison + banner, not a bracket-table rewrite.

**Cons:** Supporting prior-year bracket tables (2023, 2022, etc.) adds storage and maintenance overhead. The minimal fix (warning only, no prior-year calculation) still defers the actual accuracy problem.

**Context:** Flagged by /plan-ceo-review (2026-03-22). Minimal version: detect year mismatch and show a banner with IRS late-filing guidance link. Full version: prior-year bracket tables and form logic. Start with minimal.

**Effort:** S for warning only (human: ~2 hours / CC: ~10 min), L for full prior-year support.

**Priority:** P2 — real population of affected users (late filers), but warning-only version has low risk.

**Depends on / blocked by:** Nothing. Can be built independently.

**Completed:** Prior-year check added to `validation_service.py` — emits `prior_year` warning when `tax_year < CURRENT_YEAR` with IRS late-filing guidance text.

---

## ~~TODO-11: Tax Deadline Banner~~ ✅ DONE 2026-03-22

**What:** Add a deadline-awareness banner to the app header that shows the relevant filing deadline based on visa type and current date. Domestic filers: April 15. NRAs with US wages: April 15. NRAs without US wages: June 15. All filers with extension: October 15. Show urgency ("3 days left") when within 2 weeks of a deadline.

**Why:** A student who discovers the April 15 deadline on April 14 may panic, rush, or make errors. The app has all the information needed to surface this proactively. This is a trust signal — a tax tool that doesn't know the tax calendar feels incomplete.

**Pros:** Zero complexity (hardcoded calendar constants, current date comparison). High visibility. Differentiates from TaxSnapPro which has no deadline awareness. NRA-specific deadline rules (June 15) are a unique feature.

**Cons:** Dates change if the IRS moves deadlines (rare but happened during COVID). Requires hardcoded calendar that needs annual review alongside TODO-8.

**Context:** Flagged by /plan-ceo-review (2026-03-22). Implement as a `<DeadlineBanner>` component in the app header. Read `visa_type` from ContextStep state to select the correct deadline. Use `urgency` color coding: green > 30 days, amber 8–30 days, red ≤ 7 days.

**Effort:** S (human: ~3 hours / CC: ~15 min)

**Priority:** P2 — polish feature, but high user-trust value near deadline season.

**Depends on / blocked by:** Nothing. Can be built independently.

**Completed:** `DeadlineBanner.tsx` component created with NRA-aware deadline logic (Apr 15 / Jun 15), 3-tier urgency coloring (green/amber/red), and `role="status"` accessibility. Wired into `page.tsx` via `onContextSaved` callback on `ContextStep`; banner updates live when user saves context.

---

## ~~TODO-12: ITIN Guidance for Students Without SSN~~ ✅ DONE 2026-03-22

**What:** Add an informational card in the Report step for users who have no SSN. The card should explain: what an ITIN is, when it's required (no SSN + must file US return), how to apply (Form W-7 + passport copy + tax return), and that processing takes 7–11 weeks. Include a link to IRS Form W-7 instructions.

**Why:** First-year F-1 students frequently have no SSN when filing season begins (they arrived in August, haven't worked, haven't applied). Without ITIN guidance, they stall at the Form 843 or 1040-NR step with no explanation of why they're blocked. This is the most common unmet need for first-year international students.

**Pros:** Zero backend work — a static informational card. Closes the biggest UX gap for first-year students. A unique feature vs TaxSnapPro (no ITIN guidance exists there either).

**Cons:** ITIN rules are complex (not everyone who files needs one; treaty countries may have different rules). The card risks over-simplifying. Must include a "consult a tax professional" disclaimer.

**Context:** Flagged by /plan-ceo-review (2026-03-22). Detect ITIN need from visa_type (F-1, J-1, OPT) and absence of SSN field in uploaded documents. Show the card only when relevant. Source: IRS ITIN page and Form W-7 instructions.

**Effort:** S (human: ~2 hours / CC: ~10 min)

**Priority:** P2 — high impact for first-year students, zero implementation complexity.

**Depends on / blocked by:** Nothing. Can be built independently.

**Completed:** ITIN Guidance Card added to `CalculationLedgerStep.tsx` — shown when `report.needs_itin_guidance === true`. Explains Form W-7 process with ordered next steps. `needs_itin_guidance` computed in backend `compute_report_extras()` and surfaced on `TaxReport`.

---

## ~~TODO-13: Form 8833 Disclosure Advisory~~ ✅ DONE 2026-03-22

**What:** When a user's tax calculation includes a treaty exemption (i.e., `treaty_exempt_amount > 0`), show a compliance warning in the Report step: "You claimed a tax treaty exemption. US law (IRC §6114) requires you to attach Form 8833 (Treaty-Based Return Position Disclosure) to your 1040-NR. Failure to attach Form 8833 when required is a $1,000 penalty. See IRS instructions for Form 8833."

**Why:** Tax-cellent will calculate treaty benefits correctly, but users who don't know to attach Form 8833 face a $1,000 IRS penalty per occurrence. Surfacing this warning is a compliance obligation for a tool that facilitates treaty claims.

**Pros:** Protects users from a real penalty. The trigger condition (`treaty_exempt_amount > 0`) is already a computed field in the tax engine output. The fix is a conditional warning card — no new logic required.

**Cons:** Adds legal complexity to the disclaimer. The tool should not be seen as providing legal advice. Requires careful wording ("you may need to" vs "you must").

**Context:** Flagged by /plan-ceo-review (2026-03-22). IRC §6114 mandates disclosure for treaty-based positions that reduce US tax liability. The Form 8833 is a one-page disclosure, not a complex form — but users need to know it exists. Wording should include: "This is informational — consult a tax professional for your specific situation."

**Effort:** S (human: ~1 hour / CC: ~5 min)

**Priority:** P1 — compliance gap with user-facing dollar penalty if missed.

**Depends on / blocked by:** Exp 2 (treaty calculation engine) must ship first so `treaty_exempt_amount` is a computed output.

**Completed:** Form 8833 Advisory Card added to `CalculationLedgerStep.tsx` — shown when `report.treaty_exempt_amount > 0`. Displays treaty country, exempt amount, IRC §6114 citation, ordered next steps, and $1,000 penalty warning. `treaty_exempt_amount` and `treaty_country` surfaced from `compute_report_extras()` in `tax_advisor.py`.

---

## ~~TODO-14: Model List Single Source of Truth~~ ✅ DONE 2026-03-23

**What:** Move the per-provider model lists (currently hardcoded in both `SettingsStep.tsx` and `backend/app/api/review.py`) into a single backend constant (`backend/app/constants/models.py`) exposed via `GET /api/providers/models`. Frontend fetches on mount.

**Why:** When model lists live in two places, adding a new model requires updating both files. Drift risk: the backend validation list rejects a model the frontend shows as valid (or vice versa). As providers release new models frequently, this dual-maintenance creates silent breakage.

**Pros:** Single update point. Frontend always shows currently-valid models. Backend validation stays in sync automatically.

**Cons:** Adds one more API endpoint + one more fetch in SettingsStep. For a hackathon, SYNC comments in both files are sufficient.

**Context:** Flagged by /plan-ceo-review (2026-03-23) during cloud API feature review. For now, both files have `# SYNC: model lists must match SettingsStep.tsx / review.py` comments pointing to each other. This TODO tracks the post-hackathon cleanup.

**Effort:** S (human: ~2 hours / CC: ~15 min)

**Priority:** P3 — no user-facing impact until model lists diverge; SYNC comments mitigate risk.

**Depends on / blocked by:** Cloud API providers feature (TODO completes after that ships).

**Completed:** `backend/app/constants/models.py` created as single source of truth. `review.py` now imports from constants and exposes `GET /api/providers/models`. `SettingsStep.tsx` fetches on mount with hardcoded fallback on network error. 12 tests in `test_provider_models.py` including an identity check (`REVIEW_PROVIDER_MODELS is PROVIDER_MODELS`) that will fail if divergence ever occurs.

---

## ~~TODO-15: API Key Session Persistence~~ ✅ DONE 2026-03-23

**What:** Add an opt-in "Remember for this session" checkbox next to the API key input in SettingsStep. If checked, store the api_key in `sessionStorage` (clears on tab close, not a full localStorage persist). Pre-populate the input field if a stored key exists for the selected provider.

**Why:** Users running multiple Tax-cellent analyses (e.g., testing different documents, demo scenarios) currently have to re-type their API key after each page refresh. sessionStorage provides convenience without the security risk of localStorage persistence.

**Pros:** Reduces friction for power users and demo scenarios. sessionStorage is tab-scoped and clears automatically. No server-side changes needed.

**Cons:** Key is briefly accessible via DevTools. Should include a note: "Stored in browser session only — clears when tab closes."

**Context:** Flagged by /plan-ceo-review (2026-03-23). Inline api_key (TODO for current sprint) stores in React state only; this is the follow-on to add opt-in session persistence.

**Effort:** S (human: ~1 hour / CC: ~10 min)

**Priority:** P3 — polish, not correctness.

**Depends on / blocked by:** Cloud API providers feature must ship first (api_key field must exist).

**Completed:** `SettingsStep.tsx` updated with opt-in "Remember for this session" checkbox. On provider change, reads from `sessionStorage[tax_api_key_{provider}]` and pre-populates the input + checkbox. On analyze click, saves or clears sessionStorage based on checkbox state. Note "(clears when tab closes)" shown in UI. Ollama (local provider) never saves a key.

---

## TODO-16: University Name Autocomplete

**What:** Autocomplete for the institution name field in `ContextStep.tsx` and `ZeroIncomeStep.tsx`. Source: SEVIS-approved schools list or US Department of Education institution database. Currently both fields use plain text inputs.

**Why:** Typos in the institution name on Form 8843 don't invalidate the form (IRS doesn't validate institution names mechanically), but autocomplete builds trust, speeds up the flow, and reduces errors on Line 5 of Form 8843. Also prevents the "MIT" vs "Massachusetts Institute of Technology" ambiguity in future data analytics.

**Pros:** Delightful UX — students recognize their school instantly. Reduces typos on a mailed legal document. Differentiator vs plain-text competitors.

**Cons:** Requires a school name database or API (SEVIS SEVP search or DOE IPEDS). Non-trivial backend work. School names change. Edge case: student's school isn't in the database.

**Context:** Flagged by /plan-ceo-review (2026-03-23) during Form 8843 zero-income path review. ContextStep and ZeroIncomeStep ship with plain text inputs. This TODO is the follow-on to add autocomplete. The field name is `institution_name` in `UserContext` and `Form8843Data`.

**Effort:** M (human: ~2-3 days / CC: ~1 hour)

**Priority:** P3 — UX polish; form is valid without it.

**Depends on / blocked by:** Form 8843 zero-income feature must ship first (creates the institution fields).

---

## TODO-17: Form 8843 IRS Instructions Cross-Check

**What:** Cross-reference every `Form8843Data` field mapping against the IRS Form 8843 instructions and IRS Publication 519 Chapter 1 before any public launch. Verify line-by-line that each field maps to the correct IRS form line with the correct semantics.

**Why:** The plan claims "legally correct Form 8843" but no compliance review step exists. pypdf fills whatever field names are provided — incorrect mapping produces a silently wrong mailable document. An F-1 student who files a Form 8843 with wrong field values faces potential IRS correspondence or compliance issues.

**Pros:** Backs the "legally correct" claim. Covers: Line 7 (`exempt_years_count` → correct checkbox set), Line 3a (`days_in_us` → correct calendar-year count), Line 8 (`status_change_applied` default=False is safe assumption), Part II lines 9-12 teacher/researcher instructions. One-time research task.

**Cons:** Requires reading IRS Form 8843 instructions carefully (~1 hour human / ~15 min CC). Risk of over-confidence — IRS instructions are authoritative but may require tax professional judgment for edge cases.

**Context:** Flagged by /plan-eng-review (2026-03-24) outside voice. The AcroForm spike and `EXPECTED_FIELDS` validation protect against wrong field names, but not against filling the right fields with the wrong values. This TODO is the field-semantics check, not the field-names check.

**Effort:** S (human: ~2 hours / CC: ~15 min)

**Priority:** P2 — required before public launch; form generation is functional without it during testing.

**Depends on / blocked by:** Form 8843 zero-income feature must ship first (so there's actual field mapping code to cross-check).

