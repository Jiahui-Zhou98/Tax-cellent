# Tax-cellent Design System

Dark-terminal aesthetic. Privacy-first product for tax document review. Every visual decision reinforces trust, precision, and local execution.

---

## Color Palette

### Background layers

| Token | Value | Usage |
|---|---|---|
| `bg-page` | `#060b14` | Page/body background (deepest navy) |
| `bg-card` | `rgba(13,20,36,0.7)` | Card surface — glassmorphism with blur |
| `bg-card-inner` | `rgba(13,20,36,0.5)` | Content area inside SectionCard |
| `bg-section-header` | `rgba(15,23,42,0.8)` | SectionCard title strip |
| `bg-row` | `rgba(15,23,42,0.5)` | Field rows, ledger rows |
| `bg-deep` | `rgba(6,11,20,0.6)` | Expanded ledger detail rows |
| `bg-select-option` | `#0d1424` | `<option>` background in dark selects |
| `bg-connector` | `rgba(30,41,59,0.8)` | StepBar inactive connectors |

### Cyan — primary accent

All interactive highlights, active step, focus states, and primary glows.

| Token | Value | Usage |
|---|---|---|
| `cyan-500` | `#22d3ee` | Active step circle, focus ring, icon stroke |
| `cyan-300` | `#67e8f9` | Active step circle border |
| `cyan-glow-strong` | `rgba(34,211,238,0.55)` | Active step circle box-shadow |
| `cyan-glow-ring` | `rgba(34,211,238,0.5)` | Completed step circle border |
| `cyan-glow-soft` | `rgba(34,211,238,0.2)` | Gradient tail on completed connectors |
| `cyan-glow-faint` | `rgba(34,211,238,0.12)` | Drag-active dropzone box-shadow |
| `cyan-fill-light` | `rgba(34,211,238,0.1)` | Completed step circle background |
| `cyan-fill-faint` | `rgba(34,211,238,0.08)` | Icon container background |
| `cyan-fill-hover` | `rgba(34,211,238,0.05)` | Drag-active dropzone background |
| `cyan-fill-checkbox` | `rgba(34,211,238,0.2)` | Checked checkbox background |
| `cyan-border-icon` | `rgba(34,211,238,0.2)` | Icon container border |
| `cyan-border-drag` | `rgba(34,211,238,0.7)` | Drag-active dashed border |
| `cyan-border-check` | `rgba(34,211,238,0.7)` | Checked checkbox border |
| `cyan-input-focus` | `rgba(34,211,238,0.5)` | Field input underline on focus |
| `cyan-spinner` | `#22d3ee` | Spinner top-border color |
| `cyan-stroke-icon` | `rgba(34,211,238,0.8)` | Upload SVG icon stroke |
| `cyan-corner` | `rgba(34,211,238,0.3)` | Dropzone corner accent borders |

### Blue — primary action

All CTA buttons (Confirm, Continue, Calculate, etc.).

| Token | Value | Usage |
|---|---|---|
| `blue-600` | `#2563eb` | Button background (all primary CTAs) |
| `blue-glow` | `rgba(59,130,246,0.45)` | Button box-shadow (`glowBtn()` default) |

### Semantic status colors

| Token | Value | State | Usage |
|---|---|---|---|
| `emerald-400` | `#34d399` | Success / refund / pass | Outcome banner, validation PASS, calculation steps |
| `emerald-bg` | `rgba(16,185,129,0.05)` | Success background | Privacy badge, PASS badge bg |
| `emerald-border` | `rgba(16,185,129,0.12)` | Success border | Privacy badge border |
| `emerald-border-strong` | `rgba(16,185,129,0.25)` | Success border | Privacy icon border |
| `amber-400` | `#fbbf24` | Warning | WARN badge, FLAG button active, FICA card |
| `amber-bg` | `rgba(251,191,36,0.05–0.06)` | Warning background | FICA card, unresolved field row, WARN badge |
| `amber-border` | `rgba(251,191,36,0.15–0.25)` | Warning border | Issue rows, FICA card, FLAG button |
| `red-400` | `#f87171` | Error | ERR badge, error messages, low-confidence flags |
| `red-bg` | `rgba(127,29,29,0.15–0.2)` | Error background | Error alert, ERR issue row |
| `red-border` | `rgba(239,68,68,0.15–0.2)` | Error border | Error alert, ERR issue row |
| `blue-400` | `#60a5fa` | Balanced | Balanced tax outcome banner |

### SectionCard accent palette

Accents are assigned per semantic domain and stay consistent across all steps.

| Accent | Hex | Domain |
|---|---|---|
| Cyan | `#22d3ee` | Primary (status, AI provider) |
| Emerald | `#34d399` | Earnings, success, additional context |
| Purple | `#818cf8` | Payer / employer info |
| Violet | `#a78bfa` | Deferred compensation (Box 12) |
| Orange | `#fb923c` | State/local boxes, validation notes |
| Slate | `#64748b` | Document info, other/misc |
| Muted slate | `#94a3b8` | Box 13/14, secondary |
| Red | `#f87171` | Review flags — low confidence |

### Text scale

| Token | Value | Usage |
|---|---|---|
| `text-primary` | `#ffffff` / Tailwind `text-white` | Headings |
| `text-secondary` | `#e2e8f0` | Body text, input values |
| `text-muted-1` | `#94a3b8` | Secondary labels, completed step labels |
| `text-muted-2` | `#64748b` | Tertiary labels, source tags |
| `text-muted-3` | `#475569` | Inactive step labels, disabled indicators |
| `text-disabled` | `#334155` | Future step labels |
| `text-mono-dark` | `#475569` | Ledger table header |

### Border / divider scale

| Token | Value | Usage |
|---|---|---|
| `border-card` | `rgba(255,255,255,0.07)` | Card outer border |
| `border-section-header` | `rgba(255,255,255,0.06)` | SectionCard header bottom |
| `border-row` | `rgba(255,255,255,0.05)` | Field row border (standard) |
| `border-row-faint` | `rgba(255,255,255,0.04)` | Ledger row dividers |
| `border-input` | `rgba(71,85,105,0.4)` | Input underline (resting) |
| `border-secondary-btn` | `rgba(71,85,105,0.5)` | Back/secondary button border |
| `border-secondary-btn-light` | `rgba(71,85,105,0.3)` | Secondary button border (light variant) |
| `border-dropzone` | `rgba(100,116,139,0.3)` | Dropzone dashed border (resting) |
| `border-step-inactive` | `rgba(100,116,139,0.3)` | Inactive step circle border |
| `border-checkbox` | `rgba(71,85,105,0.5)` | Unchecked checkbox border |

---

## Typography

Font stack: system default via Tailwind (`font-sans`). Monospace: `font-mono` (system mono stack).

| Role | Classes | Usage |
|---|---|---|
| Page heading | `text-2xl font-semibold text-white tracking-tight` | Step titles |
| Large number | `text-5xl font-bold tracking-tight` | Outcome dollar amount |
| Button label | `font-semibold text-sm` | Primary CTA buttons |
| Body | `text-sm text-slate-200` | Card body text, field values |
| Secondary body | `text-sm text-slate-400` | Explanations, ledger details |
| Label | `text-xs text-slate-500` | Field labels, section hints |
| Hint/meta | `text-xs text-slate-600` | Hints, source tags, footnotes |
| Disabled | `text-xs text-slate-700` | Fine print, timing hints |
| Mono label | `text-xs font-mono tracking-widest uppercase` | SectionCard titles, badge labels |
| Mono value | `font-mono text-sm text-slate-100` | Field values, ledger amounts |
| Mono code | `text-xs font-mono text-slate-600` | Rule references, IDs |

---

## Spacing Scale

| Token | Value | Usage |
|---|---|---|
| Step bar margin | `mb-12` | Gap between StepBar and step content |
| Section gap | `space-y-5` | Between SectionCards within a step |
| Card content | `p-3 space-y-2` | SectionCard inner padding |
| Card header | `px-4 py-2.5` | SectionCard title strip padding |
| Row padding | `px-4 py-3` | Field rows |
| Row padding (tall) | `px-4 py-3.5` | ValidationStep status badge |
| Button padding | `py-3 px-5` | Secondary/back buttons |
| Button padding (primary) | `py-3.5` / `py-3` | Full-width primary CTAs |
| Banner padding | `px-6 py-5` | Outcome banner |
| Alert padding | `p-4` | Error alerts |

---

## Border Radius

| Token | Tailwind | Usage |
|---|---|---|
| Card | `rounded-xl` | SectionCards, alerts, ledger table, info panels |
| Feature card | `rounded-2xl` | Dropzone, outcome banner |
| Button | `rounded-xl` | All buttons |
| Circle | `rounded-full` | Step circles, privacy icon, spinner |
| Row | `rounded-lg` | Field rows |
| Checkbox | `rounded` | Custom checkbox |
| Input override | `0.5rem` inline | Inputs inside SectionCards |

---

## Shadows & Glows

| Name | Value | Usage |
|---|---|---|
| `glowBtn()` | `0 0 22px rgba(59,130,246,0.45)` | Primary CTA hover/active state |
| Step active glow | `0 0 20px rgba(34,211,238,0.55)` | Active step circle |
| Drag active glow | `0 0 32px rgba(34,211,238,0.12)` | Dropzone drag-over state |
| Outcome banner | `0 0 36px {outcome-color}` | Outcome result banner (color varies) |

---

## Motion & Animation

| Token | Usage |
|---|---|
| `animate-fade-in` | Every step mounts with fade-in (defined in Tailwind config or globals.css) |
| `animate-spin` | Upload spinner, analysis spinner |
| `transition-all duration-300` | StepBar circle and connector color transitions |
| `transition-colors` | Button hover, input focus, field row hover |
| `transition-all` | Buttons, general interactive elements |

---

## Glassmorphism Card

The canonical card style used for the dropzone and any floating surfaces:

```ts
// frontend/app/styles.ts
export const card: React.CSSProperties = {
  background: "rgba(13,20,36,0.7)",
  border: "1px solid rgba(255,255,255,0.07)",
  backdropFilter: "blur(12px)",
};
```

---

## Input Style

All `<input>` and `<select>` elements inside forms use this shared style:

```ts
// frontend/app/styles.ts
export const inputStyle: React.CSSProperties = {
  background: "rgba(13,20,36,0.6)",
  border: "1px solid rgba(71,85,105,0.4)",
  borderRadius: "0.5rem",
  color: "#e2e8f0",
  padding: "0.5rem 0.75rem",
  width: "100%",
  fontSize: "0.875rem",
  outline: "none",
};
```

Text inputs with inline underline style (FieldRow):
- Resting: `borderBottom: 1px solid rgba(71,85,105,0.4)`, no other border
- Focus: `borderBottom: 1px solid rgba(34,211,238,0.5)`

---

## Confidence Indicator Colors

Used in FieldRow to signal OCR extraction confidence:

| Confidence | Color | Hex |
|---|---|---|
| ≥ 80% | Emerald | `#34d399` |
| 50–79% | Amber | `#fbbf24` |
| < 50% | Red | `#f87171` |

```ts
export const confColor = (c: number) =>
  c >= 0.8 ? "#34d399" : c >= 0.5 ? "#fbbf24" : "#f87171";
```

---

## Outcome Banner Colors

Four possible tax outcomes, each with a full color theme:

| Outcome | Color | Background | Border | Glow |
|---|---|---|---|---|
| `refund` | `#34d399` | `rgba(52,211,153,0.07)` | `rgba(52,211,153,0.25)` | `rgba(52,211,153,0.25)` |
| `owe` | `#f87171` | `rgba(248,113,113,0.07)` | `rgba(248,113,113,0.25)` | `rgba(248,113,113,0.2)` |
| `balanced` | `#60a5fa` | `rgba(96,165,250,0.07)` | `rgba(96,165,250,0.25)` | `rgba(96,165,250,0.2)` |
| `unknown` | `#94a3b8` | `rgba(100,116,139,0.07)` | `rgba(100,116,139,0.25)` | `rgba(100,116,139,0.1)` |

---

## Validation Status Colors

| Status | Label | Icon | Color | Background | Border |
|---|---|---|---|---|---|
| `ok` | PASS | ✓ | `#34d399` | `rgba(52,211,153,0.06)` | `rgba(52,211,153,0.2)` |
| `warning` | WARN | ! | `#fbbf24` | `rgba(251,191,36,0.06)` | `rgba(251,191,36,0.2)` |
| `error` | FAIL | ✕ | `#f87171` | `rgba(248,113,113,0.06)` | `rgba(248,113,113,0.2)` |

---

## Component File Map

| Component | File |
|---|---|
| Shared tokens | `frontend/app/styles.ts` |
| Provider list | `frontend/app/lib/providers.ts` |
| Step progress bar | `frontend/app/components/StepBar.tsx` |
| Section card wrapper | `frontend/app/components/SectionCard.tsx` |
| Editable field row | `frontend/app/components/FieldRow.tsx` |
| Step 1 — Upload | `frontend/app/components/UploadStep.tsx` |
| Step 2 — Context | `frontend/app/components/ContextStep.tsx` |
| Step 3 — Review | `frontend/app/components/FieldReviewStep.tsx` |
| Step 4 — Validate | `frontend/app/components/ValidationStep.tsx` |
| Step 5 — Settings | `frontend/app/components/SettingsStep.tsx` |
| Step 6 — Analysis | `frontend/app/components/AnalysisStep.tsx` |
| Step 7 — Report | `frontend/app/components/CalculationLedgerStep.tsx` |
