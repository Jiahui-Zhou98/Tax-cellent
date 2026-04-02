"use client";

import type { OCROutput } from "../lib/api";

const FORM_BADGES: Record<string, { label: string; color: string }> = {
  "W-2":       { label: "W-2", color: "#34d399" },
  "1099-NEC":  { label: "1099-NEC", color: "#818cf8" },
  "1099-INT":  { label: "1099-INT", color: "#fbbf24" },
  "1042-S":    { label: "1042-S", color: "#f472b6" },
  "1099-MISC": { label: "1099-MISC", color: "#fb923c" },
};

function getKeyValues(ocr: OCROutput): { label: string; value: string }[] {
  const fc = ocr.field_candidates;
  const fv = (key: string) => fc[key]?.value ?? "";
  const formType = fv("form_type");

  if (formType.includes("W-2")) {
    return [
      { label: "Employer", value: fv("employer_name") },
      { label: "Wages", value: fv("box_1_wages") ? `$${fv("box_1_wages")}` : "" },
      { label: "Fed withheld", value: fv("box_2_federal_tax_withheld") ? `$${fv("box_2_federal_tax_withheld")}` : "" },
    ].filter((r) => r.value);
  }
  if (formType.includes("1099-NEC") || formType.includes("NEC")) {
    return [
      { label: "Payer", value: fv("payer_name") },
      { label: "NEC income", value: fv("box_1_nonemployee_compensation") ? `$${fv("box_1_nonemployee_compensation")}` : "" },
    ].filter((r) => r.value);
  }
  if (formType.includes("1042-S")) {
    return [
      { label: "Agent", value: fv("withholding_agent") },
      { label: "Ch3 income", value: fv("gross_income_ch3") ? `$${fv("gross_income_ch3")}` : "" },
    ].filter((r) => r.value);
  }
  if (formType.includes("1099-INT") || formType.includes("INT")) {
    return [
      { label: "Payer", value: fv("payer_name") },
      { label: "Interest", value: fv("box_1_interest_income") ? `$${fv("box_1_interest_income")}` : "" },
    ].filter((r) => r.value);
  }
  if (formType.includes("1099-MISC") || formType.includes("MISC")) {
    return [
      { label: "Payer", value: fv("payer_name") },
      { label: "Other income", value: fv("box_3_other_income") ? `$${fv("box_3_other_income")}` : "" },
    ].filter((r) => r.value);
  }
  return [{ label: "Form", value: formType || "Unknown" }];
}

export function DocumentCard({
  ocr,
  onRemove,
  loading,
  error,
}: {
  ocr?: OCROutput;
  onRemove?: () => void;
  loading?: boolean;
  error?: string;
}) {
  if (loading) {
    return (
      <div
        className="flex items-center gap-3 rounded-xl p-4"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        <div
          className="h-5 w-5 animate-spin rounded-full border-2"
          style={{ borderColor: "var(--color-border)", borderTopColor: "var(--color-accent)" }}
        />
        <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Extracting fields...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex items-center justify-between rounded-xl p-4"
        style={{ background: "rgba(255,59,48,0.06)", border: "1px solid rgba(255,59,48,0.2)" }}
      >
        <span className="text-sm" style={{ color: "var(--color-danger)" }}>
          Upload failed: {error}
        </span>
        {onRemove && (
          <button onClick={onRemove} className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            Dismiss
          </button>
        )}
      </div>
    );
  }

  if (!ocr) return null;

  const formType = ocr.field_candidates["form_type"]?.value || "Unknown";
  const badge = Object.entries(FORM_BADGES).find(([k]) => formType.includes(k))?.[1]
    ?? { label: formType, color: "#64748b" };
  const keyValues = getKeyValues(ocr);

  return (
    <div
      className="flex items-center justify-between rounded-xl p-4"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span
          className="rounded-md px-2 py-0.5 text-xs font-bold whitespace-nowrap"
          style={{ background: `${badge.color}20`, color: badge.color }}
        >
          {badge.label}
        </span>
        <div className="min-w-0">
          {keyValues.map((kv, i) => (
            <span key={i} className="text-xs" style={{ color: i === 0 ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}>
              {i > 0 && <span className="mx-1.5" style={{ color: "var(--color-border)" }}>|</span>}
              {kv.label}: {kv.value}
            </span>
          ))}
        </div>
      </div>
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-3 flex-shrink-0 rounded px-2 py-1 text-xs transition-colors"
          style={{ color: "var(--color-text-secondary)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-danger)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
        >
          Remove
        </button>
      )}
    </div>
  );
}
