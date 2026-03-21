# TaxDebate Local — TODOs

## Post-Hackathon Design Debt

### TODO-1: Create DESIGN.md
**What:** Formalize the existing design token system into a `DESIGN.md` file —
colors (`#060b14`, `#22d3ee`, etc.), spacing scale, typography hierarchy,
glassmorphism card pattern, glow effect specs.

**Why:** All tokens are currently scattered across `page.tsx` (inline `card`/`glowBtn`
objects) and `layout.tsx`. As more components are added, this will cause copy-paste
drift and inconsistency.

**Pros:** Single source of truth for contributors; faster future development;
easier design review.

**Cons:** 30–60 minutes of documentation work. Low urgency during hackathon.

**Context:** The design language is intentional and strong — dark navy `#060b14`,
cyan `#22d3ee` accent, glassmorphism cards, monospace for data. Worth preserving.

**Depends on:** Nothing. Can be done any time post-demo.

---

### TODO-2: Add inline help text to Context step questions
**What:** For each immigration/residency question in the new Context step, add
a short inline help text or tooltip that explains the term in plain English.

Example:
- "Days present in the US in the second prior year" →
  *"Count days you were physically inside the US borders during [year-2].
   Do not count days in transit at airports."*
- "Exempt individual" → *"You are likely exempt if you are on F, J, M, or Q status
  and within your first 5 calendar years in the US."*

**Why:** International students unfamiliar with US tax residency rules will get
stuck or enter incorrect values. Wrong inputs produce wrong residency analysis.

**Pros:** Reduces drop-off; increases data quality; builds trust.

**Cons:** Requires content writing, not just code. Some rules are nuanced.

**Context:** The Context step targets international students who may not know
terms like "substantial presence test" or "exempt individual." Reduce cognitive
load at the input stage.

**Depends on:** Context step being built first (see improve.md for field spec).

---

### TODO-3: Mobile card reflow for Calculation Ledger
**What:** Replace the horizontal-scroll table with stacked cards on screens < 640px.
Each card shows: step number (large), step label, amount (large, colored), IRS rule reference.

**Why:** Horizontal scroll is the hackathon ship target. Card reflow is the production-quality UX.
First-time users on mobile won't intuit horizontal scrolling, and investor demos on phones will
feel janky with a scrolling table.

**Pros:** Better mobile experience; consistent with existing glassmorphism card pattern; premium
feel for phone demos.

**Cons:** ~45 min of additional frontend work (human: ~1hr / CC: ~10min post-hackathon).

**Context:** The current Calculation Ledger uses `overflow-x: auto` with a scroll hint below 640px.
This is intentional for the hackathon. The card reflow is the post-hackathon follow-up.

**Depends on:** Calculation Ledger component being shipped first.

---

### TODO-4: Add 1099-NEC and 1099-INT paths to TaxCalculationEngine
**What:** Port the 1099-NEC (self-employment) and 1099-INT (interest income) calculation
logic from the old `tax_analysis.txt` prompt into deterministic Python in `TaxCalculationEngine`.

**Why:** The hackathon scope implements W-2 single-filer only. Without this, users who upload
1099-NEC or 1099-INT forms will get no calculation steps (or a "missing fields" unknown outcome).
Freelancers and contractors are a large market segment for a privacy-first tax tool.

**Pros:** Extends reliability to 3 form types. Math is already documented in the old prompt.
1099-NEC: `se_tax = box_1 * 0.9235 * 0.153`, `deductible_se = se_tax / 2`. 1099-INT: simpler.

**Cons:** SE tax (Schedule SE) is more complex than W-2. Requires careful IRS source verification.
~2 hours human / ~20 min CC.

**Context:** See `backend/app/prompts/tax_analysis.txt` (the old prompt) for the full logic.
Port each form's calculation into a separate method on `TaxCalculationEngine`. Add tests
for each form path (same pattern as the W-2 tests).

**Depends on:** W-2 path implemented and tested first (current scope).

---

## Implemented (2026-03-21)

- [x] **a11y: aria-label on file dropzone** — Added `aria-label="Upload tax document"`
  to the dropzone container and `aria-label="Select tax document file"` to the
  hidden file input. Screen readers can now identify the upload control.
