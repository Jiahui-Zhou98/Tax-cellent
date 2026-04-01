"use client";

export const FIELD_LABELS: Record<string, string> = {
  form_type: "Form Type",
  tax_year: "Tax Year",
  import_code: "Import Code",
  employee_name: "Employee Name",
  employee_ssn: "Employee SSN",
  employee_address: "Employee Address",
  employer_name: "Employer Name",
  employer_ein: "Employer EIN",
  employer_address: "Employer Address",
  box_1_wages: "Box 1 — Wages, Tips, Other Comp.",
  box_2_federal_tax_withheld: "Box 2 — Federal Income Tax Withheld",
  box_3_social_security_wages: "Box 3 — Social Security Wages",
  box_4_social_security_tax: "Box 4 — Social Security Tax Withheld",
  box_5_medicare_wages: "Box 5 — Medicare Wages & Tips",
  box_6_medicare_tax: "Box 6 — Medicare Tax Withheld",
  box_7_social_security_tips: "Box 7 — Social Security Tips",
  box_8_allocated_tips: "Box 8 — Allocated Tips",
  box_10_dependent_care_benefits: "Box 10 — Dependent Care Benefits",
  box_11_nonqualified_plans: "Box 11 — Nonqualified Plans",
  box_12a_code: "Box 12a — Code",
  box_12a_amount: "Box 12a — Amount",
  box_12b_code: "Box 12b — Code",
  box_12b_amount: "Box 12b — Amount",
  box_12c_code: "Box 12c — Code",
  box_12c_amount: "Box 12c — Amount",
  box_12d_code: "Box 12d — Code",
  box_12d_amount: "Box 12d — Amount",
  box_13_statutory_employee: "Box 13 — Statutory Employee",
  box_13_retirement_plan: "Box 13 — Retirement Plan",
  box_13_third_party_sick_pay: "Box 13 — Third-Party Sick Pay",
  box_14_other: "Box 14 — Other",
  box_15_state: "Box 15 — State",
  box_15_employer_state_id: "Box 15 — Employer State ID",
  box_16_state_wages: "Box 16 — State Wages",
  box_17_state_income_tax: "Box 17 — State Income Tax",
  box_18_local_wages: "Box 18 — Local Wages",
  box_19_local_income_tax: "Box 19 — Local Income Tax",
  box_20_locality_name: "Box 20 — Locality Name",
  payer_name: "Payer Name",
  payer_tin: "Payer TIN",
  payer_address: "Payer Address",
  recipient_name: "Recipient Name",
  recipient_tin: "Recipient TIN",
  recipient_address: "Recipient Address",
  box_1_nonemployee_compensation: "Box 1 — Nonemployee Compensation",
  box_1_interest_income: "Box 1 — Interest Income",
  box_2_early_withdrawal_penalty: "Box 2 — Early Withdrawal Penalty",
  box_4_federal_tax_withheld: "Box 4 — Federal Tax Withheld",
};

export const confColor = (c: number) =>
  c >= 0.8 ? "#34C759" : c >= 0.5 ? "#FF9F0A" : "#FF3B30";

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ai_regex_agree:    { label: "AI verified", color: "#34d399" },
  ai_regex_disagree: { label: "AI differs", color: "#f87171" },
  ai:                { label: "AI only", color: "#818cf8" },
  ocr:               { label: "OCR", color: "#64748b" },
  user_confirmed:    { label: "confirmed", color: "#64748b" },
  user_edited:       { label: "edited", color: "#22d3ee" },
  missing:           { label: "", color: "#475569" },
};

export function FieldRow({
  fieldKey,
  field,
  isUnresolved,
  onChange,
  onToggle,
}: {
  fieldKey: string;
  field: { value: string; source: string; confidence: number };
  isUnresolved: boolean;
  onChange: (key: string, value: string) => void;
  onToggle: (key: string) => void;
}) {
  return (
    <div
      className="rounded-lg px-4 py-3 transition-all"
      style={
        isUnresolved
          ? { background: "rgba(255,159,10,0.06)", border: "1px solid rgba(255,159,10,0.25)" }
          : { background: "var(--color-bg)", border: "1px solid var(--color-border)" }
      }
    >
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs" id={`label-${fieldKey}`} style={{ color: "var(--color-text-secondary)" }}>
              {FIELD_LABELS[fieldKey] ?? fieldKey}
            </span>
            {field.confidence > 0 ? (
              <>
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: confColor(field.confidence) }}
                  aria-hidden="true"
                />
                <span
                  className="text-xs font-mono"
                  style={{ color: confColor(field.confidence) }}
                  aria-label={
                    field.confidence >= 0.8
                      ? `High confidence (${Math.round(field.confidence * 100)}%)`
                      : field.confidence >= 0.5
                      ? `Medium confidence (${Math.round(field.confidence * 100)}%)`
                      : `Low confidence (${Math.round(field.confidence * 100)}%)`
                  }
                >
                  {Math.round(field.confidence * 100)}%
                </span>
              </>
            ) : (
              <span className="text-xs font-mono" style={{ color: "var(--color-text-secondary)", opacity: 0.5 }}>not detected</span>
            )}
            {field.source && field.source !== "missing" && (
              <span
                className="ml-auto text-xs font-mono px-1.5 py-0.5 rounded"
                style={{
                  color: SOURCE_LABELS[field.source]?.color ?? "var(--color-text-secondary)",
                  background: field.source === "ai_regex_agree"
                    ? "rgba(52,211,153,0.1)"
                    : field.source === "ai_regex_disagree"
                    ? "rgba(248,113,113,0.1)"
                    : field.source === "ai"
                    ? "rgba(129,140,248,0.1)"
                    : "transparent",
                }}
              >
                {SOURCE_LABELS[field.source]?.label ?? field.source}
              </span>
            )}
          </div>
          <input
            type="text"
            aria-labelledby={`label-${fieldKey}`}
            value={field.value}
            onChange={(e) => onChange(fieldKey, e.target.value)}
            disabled={isUnresolved}
            className="w-full font-mono text-sm py-0.5 transition-colors focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: "transparent",
              border: "none",
              borderBottom: "1px solid var(--color-border)",
              color: "var(--color-text-primary)",
            }}
            onFocus={(e) => { e.target.style.borderBottomColor = "var(--color-accent)"; }}
            onBlur={(e) => { e.target.style.borderBottomColor = "var(--color-border)"; }}
          />
        </div>
        <button
          onClick={() => onToggle(fieldKey)}
          aria-label={isUnresolved ? `Mark ${FIELD_LABELS[fieldKey] ?? fieldKey} as resolved` : `Flag ${FIELD_LABELS[fieldKey] ?? fieldKey} as unresolved`}
          aria-pressed={isUnresolved}
          className="text-xs px-2 py-0.5 rounded border transition-all flex-shrink-0 font-mono"
          style={
            isUnresolved
              ? { borderColor: "rgba(255,159,10,0.4)", color: "var(--color-warning)", background: "rgba(255,159,10,0.08)" }
              : { borderColor: "var(--color-border)", color: "var(--color-text-secondary)", background: "transparent" }
          }
        >
          {isUnresolved ? "UNRESOLVED" : "FLAG"}
        </button>
      </div>
    </div>
  );
}
