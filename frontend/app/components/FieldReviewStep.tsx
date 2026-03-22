"use client";

import { useState } from "react";
import { confirmFields, type OCROutput, type ValidationOutput } from "../lib/api";
import { glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";
import { FieldRow } from "./FieldRow";

const FIELD_GROUPS: Record<string, { title: string; accent: string; fields: string[] }[]> = {
  "W-2": [
    {
      title: "Document Info",
      accent: "#64748b",
      fields: ["form_type", "tax_year", "import_code"],
    },
    {
      title: "Employee",
      accent: "#22d3ee",
      fields: ["employee_name", "employee_ssn", "employee_address"],
    },
    {
      title: "Employer",
      accent: "#818cf8",
      fields: ["employer_name", "employer_ein", "employer_address"],
    },
    {
      title: "Federal Boxes",
      accent: "#34d399",
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
      accent: "#a78bfa",
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
      accent: "#94a3b8",
      fields: [
        "box_13_statutory_employee",
        "box_13_retirement_plan",
        "box_13_third_party_sick_pay",
        "box_14_other",
      ],
    },
    {
      title: "State & Local Boxes",
      accent: "#fb923c",
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
    { title: "Document Info", accent: "#64748b", fields: ["form_type", "tax_year"] },
    {
      title: "Payer",
      accent: "#818cf8",
      fields: ["payer_name", "payer_tin", "payer_address"],
    },
    {
      title: "Recipient",
      accent: "#22d3ee",
      fields: ["recipient_name", "recipient_tin", "recipient_address"],
    },
    {
      title: "Boxes",
      accent: "#34d399",
      fields: ["box_1_nonemployee_compensation", "box_4_federal_tax_withheld"],
    },
  ],
  "1099-INT": [
    { title: "Document Info", accent: "#64748b", fields: ["form_type", "tax_year"] },
    { title: "Payer", accent: "#818cf8", fields: ["payer_name"] },
    { title: "Recipient", accent: "#22d3ee", fields: ["recipient_name"] },
    {
      title: "Interest Boxes",
      accent: "#34d399",
      fields: [
        "box_1_interest_income",
        "box_2_early_withdrawal_penalty",
        "box_4_federal_tax_withheld",
      ],
    },
  ],
};

export function FieldReviewStep({
  ocr,
  onConfirm,
  onBack,
}: {
  ocr: OCROutput;
  onConfirm: (validation: ValidationOutput) => void;
  onBack: () => void;
}) {
  const [fields, setFields] = useState<
    Record<string, { value: string; source: string; confidence: number }>
  >(() => {
    const init: Record<string, { value: string; source: string; confidence: number }> = {};
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
  const [unresolved, setUnresolved] = useState<Set<string>>(new Set());
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
          <h2 className="text-2xl font-semibold text-white tracking-tight">Review Extracted Fields</h2>
          <p className="text-slate-500 text-sm mt-1">
            Verify extracted values. Edit incorrect fields or flag unresolved ones.
          </p>
        </div>
        <button
          onClick={onBack}
          disabled={loading}
          className="text-sm text-slate-600 hover:text-slate-300 transition-colors mt-1 whitespace-nowrap disabled:opacity-40"
        >
          ← Re-upload
        </button>
      </div>

      {reviewFlags.length > 0 && (
        <SectionCard title="Review Flags — Low Confidence" accent="#f87171">
          {reviewFlags.map(([key]) => (
            <FieldRow key={key} fieldKey={key} field={fields[key]} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      )}

      {groups.map((group) => (
        <SectionCard key={group.title} title={group.title} accent={group.accent}>
          {group.fields.map((key) => (
            <FieldRow key={key} fieldKey={key} field={fields[key] ?? { value: "", source: "missing", confidence: 0 }} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      ))}

      {otherKeys.length > 0 && (
        <SectionCard title="Other Fields" accent="#64748b">
          {otherKeys.map((key) => (
            <FieldRow key={key} fieldKey={key} field={fields[key]} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      )}

      {error && (
        <div
          className="rounded-xl p-4 text-sm text-red-400"
          style={{ background: "rgba(127,29,29,0.2)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <span className="font-mono text-red-500 mr-2">ERROR</span>
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          disabled={loading}
          className="px-5 py-3 rounded-xl text-slate-400 hover:text-slate-200 font-medium text-sm transition-all disabled:opacity-40"
          style={{ border: "1px solid rgba(71,85,105,0.5)" }}
        >
          ← Back
        </button>
        <button
          onClick={handleConfirm}
          disabled={loading}
          className="flex-1 py-3 rounded-xl text-white font-semibold text-sm transition-all disabled:opacity-40"
          style={
            loading
              ? { background: "#2563eb", opacity: 0.6 }
              : { background: "#2563eb", ...glowBtn() }
          }
        >
          {loading ? "Confirming…" : "Confirm Fields & Run Validation →"}
        </button>
      </div>
    </div>
  );
}
