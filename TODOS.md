# TODOS

Design and product debt tracked here. Items added by /plan-design-review on 2026-03-21.

---

## TODO-1: Create DESIGN.md — Design System Formalization

**What:** Extract the app's design tokens (color palette, border radii, shadows, spacing scale, typography) from inline styles in `page.tsx` into a single `DESIGN.md` document.

**Why:** The dark-terminal aesthetic is coherent but lives entirely in scattered inline styles. As the app grows (component split Exp 6, new Settings step, Form 843 card), tokens will drift. A DESIGN.md gives future contributors a reference for the intentional palette.

**Pros:** Prevents visual inconsistency as components multiply. Enables `/design-consultation` to build on an existing foundation. Makes the aesthetic replicable across new features.

**Cons:** Low immediate value while still a single-file app. The aesthetic is already consistent — this is documentation, not new capability.

**Context:** The CEO plan (2026-03-21) already lists this in the "Deferred" section. The `/plan-design-review` review confirmed the aesthetic is consistent; this is a formalization pass, not a fix.

**Depends on / blocked by:** Nothing. Can be done independently at any time.

---

## TODO-2: Full App Accessibility Audit

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

---

## TODO-3: Form 843 PDF Download

**What:** A "Download as PDF" button on the Form 843 pre-fill card in the Report step. The minimal implementation uses `window.print()` with a `@media print` CSS block that isolates the Form 843 card and formats it for letter paper.

**Why:** Copy-paste to a text editor then mail is friction-heavy. Students who want to mail the Form 843 need a printable artifact. The IRS accepts typed forms. A print-to-PDF flow produces a document they can attach to their return.

**Pros:** Significant UX improvement over clipboard copy for the primary user action (actually mailing the form). `window.print()` requires no extra library. Impressive demo feature.

**Cons:** `@media print` CSS adds complexity. The print layout needs to be tested across browsers. True PDF pre-fill into the official IRS form (using a PDF library + form field injection) is a much larger lift.

**Context:** The CEO plan's 10x vision is "Form 843 draft ready to mail." Copy-paste covers the minimum; PDF download completes the vision. This TODO represents the delta between 80% and 100%.

**Depends on / blocked by:** Exp 2 (Form 843 pre-fill card) must be implemented first. Start here after Exp 2 ships.

---

## TODO-4: Configurable CORS Origins

**What:** Replace the hardcoded `allow_origins=["http://localhost:3000"]` in `backend/app/main.py` with a configurable env var `CORS_ORIGINS`.

**Why:** The 10x vision is university-hosted deployment. Any non-localhost deployment will hit CORS errors until this is fixed. Currently there's no way to configure allowed origins without editing source code.

**Pros:** Required for any non-localhost deployment. 3-line change. Zero risk.

**Cons:** None meaningful.

**Context:** Flagged by /plan-eng-review (2026-03-21). Add `CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"` to `config.py` and split by comma in `main.py`. The `allow_origins` list populates from this env var.

**Depends on / blocked by:** Nothing.

---

## TODO-5: Run candidate_extractor in Thread Pool

**What:** Wrap `extract_candidates(parsed_json)` in `asyncio.to_thread()` inside `extraction_service.py:extract_fields_structured()`.

**Why:** `candidate_extractor.py` is 1,142 lines of synchronous CPU work running inside an `async` FastAPI handler. For multi-page PDFs, this blocks the event loop and prevents the server from handling concurrent requests.

**Pros:** Frees the event loop during extraction. One-line change. Standard FastAPI pattern.

**Cons:** `to_thread` adds minor overhead for small PDFs. Negligible in practice.

**Context:** Flagged by /plan-eng-review (2026-03-21). The extraction pipeline already has `from __future__ import annotations` and is async-compatible — the only change is wrapping the sync call with `await asyncio.to_thread(extract_candidates, parsed_json)`.

**Depends on / blocked by:** Nothing.
