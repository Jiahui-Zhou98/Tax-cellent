"use client";

import { useState } from "react";
import { confirmFields, type OCROutput, type ValidationOutput } from "../lib/api";
import { SectionCard } from "./SectionCard";
import { FieldRow } from "./FieldRow";

type Variant = "default" | "success" | "warning" | "danger";

const FIELD_GROUPS: Record<string, { title: string; variant: Variant; fields: string[] }[]> = {
  "W-2": [
    {
      title: "Document Info",
      variant: "default",
      fields: ["form_type", "tax_year", "import_code"],
    },
    {
      title: "Employee",
      variant: "default",
      fields: ["employee_name", "employee_ssn", "employee_address"],
    },
    {
      title: "Employer",
      variant: "default",
      fields: ["employer_name", "employer_ein", "employer_address"],
    },
    {
      title: "Federal Boxes",
      variant: "success",
      fields: [
        "box_1_wages",
        "box_2_federal_tax_withheld",
        "box_3_social_security_wages",
        "box_4_social_security_tax",
        "box_5_medicare_wages",
        "box_6_medicare_tax",
        "box_7_social_security_tips",
        "box_8_allocated_tips",
        "box_10_dependent_care_benefits",
        "box_11_nonqualified_plans",
      ],
    },
    {
      title: "Box 12 — Deferred Compensation",
      variant: "default",
      fields: [
        "box_12a_code",
        "box_12a_amount",
        "box_12b_code",
        "box_12b_amount",
        "box_12c_code",
        "box_12c_amount",
        "box_12d_code",
        "box_12d_amount",
      ],
    },
    {
      title: "Box 13 & 14",
      variant: "default",
      fields: [
        "box_13_statutory_employee",
        "box_13_retirement_plan",
        "box_13_third_party_sick_pay",
        "box_14_other",
      ],
    },
    {
      title: "State & Local Boxes",
      variant: "warning",
      fields: [
        "box_15_state",
        "box_15_employer_state_id",
        "box_16_state_wages",
        "box_17_state_income_tax",
        "box_18_local_wages",
        "box_19_local_income_tax",
        "box_20_locality_name",
      ],
    },
  ],
  "1099-NEC": [
    { title: "Document Info", variant: "default", fields: ["form_type", "tax_year"] },
    {
      title: "Payer",
      variant: "default",
      fields: ["payer_name", "payer_tin", "payer_address"],
    },
    {
      title: "Recipient",
      variant: "default",
      fields: ["recipient_name", "recipient_tin", "recipient_address"],
    },
    {
      title: "Boxes",
      variant: "success",
      fields: ["box_1_nonemployee_compensation", "box_4_federal_tax_withheld"],
    },
  ],
  "1099-INT": [
    { title: "Document Info", variant: "default", fields: ["form_type", "tax_year"] },
    { title: "Payer", variant: "default", fields: ["payer_name"] },
    { title: "Recipient", variant: "default", fields: ["recipient_name"] },
    {
      title: "Interest Boxes",
      variant: "success",
      fields: [
        "box_1_interest_income",
        "box_2_early_withdrawal_penalty",
        "box_4_federal_tax_withheld",
      ],
    },
  ],
};

type FieldState = Record<string, { value: string; source: string; confidence: number }>;

export function FieldReviewStep({
  ocr,
  onConfirm,
  onBack,
  savedFields,
  savedUnresolved,
  onStateSave,
}: {
  ocr: OCROutput;
  onConfirm: (validation: ValidationOutput) => void;
  onBack: () => void;
  savedFields?: FieldState;
  savedUnresolved?: string[];
  onStateSave?: (fields: FieldState, unresolved: string[]) => void;
}) {
  const [fields, setFields] = useState<FieldState>(() => {
    if (savedFields) return savedFields;
    const init: FieldState = {};
    for (const [k, v] of Object.entries(ocr.field_candidates)) {
      init[k] = { value: v.value ?? "", source: v.source, confidence: v.confidence };
    }
    const ft = init["form_type"]?.value || "W-2";
    const allGroups = FIELD_GROUPS[ft] ?? FIELD_GROUPS["W-2"];
    for (const group of allGroups) {
      for (const key of group.fields) {
        if (!(key in init)) {
          init[key] = { value: "", source: "missing", confidence: 0 };
        }
      }
    }
    return init;
  });
  const [unresolved, setUnresolved] = useState<Set<string>>(
    savedUnresolved ? new Set(savedUnresolved) : new Set()
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: { ...prev[key], value, source: "user_edited" } }));
    setUnresolved((prev) => { const n = new Set(prev); n.delete(key); return n; });
  };

  const toggleUnresolved = (key: string) => {
    setUnresolved((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });
  };

  const handleConfirm = async () => {
    onStateSave?.(fields, Array.from(unresolved));
    setLoading(true);
    setError(null);
    const payload: Record<string, { value: string | null; source: string; confidence: number }> = {};
    for (const [k, v] of Object.entries(fields)) {
      if (!unresolved.has(k)) {
        payload[k] = {
          value: v.value || null,
          source: v.source === "ocr" ? "user_confirmed" : v.source,
          confidence: v.confidence,
        };
      }
    }
    try {
      const validation = await confirmFields(ocr.document_id, payload, Array.from(unresolved));
      onConfirm(validation);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const formType = fields["form_type"]?.value || "W-2";
  const groups = FIELD_GROUPS[formType] ?? FIELD_GROUPS["W-2"];
  const groupedKeys = new Set(groups.flatMap((g) => g.fields));
  const reviewFlags = Object.entries(fields).filter(([, f]) => f.confidence < 0.6 && f.value);
  const otherKeys = Object.keys(fields).filter((k) => !groupedKeys.has(k) && k !== "raw_note");

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--color-text-primary)" }}>
            Review Extracted Fields
          </h2>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Verify extracted values. Edit incorrect fields or flag unresolved ones.
          </p>
        </div>
        <button
          onClick={() => { onStateSave?.(fields, Array.from(unresolved)); onBack(); }}
          disabled={loading}
          className="text-sm mt-1 whitespace-nowrap disabled:opacity-40 transition-colors"
          style={{ color: "var(--color-text-secondary)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-text-primary)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
        >
          ← Re-upload
        </button>
      </div>

      {reviewFlags.length > 0 && (
        <SectionCard title="Review Flags — Low Confidence" variant="danger">
          {reviewFlags.map(([key]) => (
            <FieldRow key={key} fieldKey={key} field={fields[key]} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      )}

      {groups.map((group) => (
        <SectionCard key={group.title} title={group.title} variant={group.variant}>
          {group.fields.map((key) => (
            <FieldRow key={key} fieldKey={key} field={fields[key] ?? { value: "", source: "missing", confidence: 0 }} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      ))}

      {otherKeys.length > 0 && (
        <SectionCard title="Other Fields" variant="default">
          {otherKeys.map((key) => (
            <FieldRow key={key} fieldKey={key} field={fields[key]} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      )}

      {error && (
        <div
          className="rounded-xl p-4 text-sm"
          style={{
            background: "rgba(255,59,48,0.06)",
            border: "1px solid rgba(255,59,48,0.2)",
            color: "var(--color-danger)",
          }}
        >
          <span className="font-mono mr-2">ERROR</span>
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => { onStateSave?.(fields, Array.from(unresolved)); onBack(); }}
          disabled={loading}
          className="px-5 py-3 rounded-xl font-medium text-sm transition-all disabled:opacity-40"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-primary)",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          ← Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={loading}
          className="flex-1 py-3 rounded-xl text-white font-semibold text-sm transition-all disabled:opacity-40"
          style={{ background: loading ? "#AEAEB2" : "var(--color-accent)", cursor: loading ? "not-allowed" : "pointer" }}
        >
          {loading ? "Confirming…" : "Confirm Fields & Run Validation →"}
        </button>
      </div>
    </div>
  );
}
