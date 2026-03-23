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
