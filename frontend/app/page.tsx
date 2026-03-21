"use client";

import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  uploadDocument,
  saveContext,
  confirmFields,
  analyzeDocument,
  AnalysisPreferences,
  OCROutput,
  ValidationOutput,
  TaxReport,
} from "./lib/api";

// ── Design tokens ─────────────────────────────────────────────────────────────

const card = {
  background: "rgba(13,20,36,0.7)",
  border: "1px solid rgba(255,255,255,0.07)",
  backdropFilter: "blur(12px)",
};

function glowBtn(color = "rgba(59,130,246,0.45)") {
  return { boxShadow: `0 0 22px ${color}` };
}

// ── Step bar ──────────────────────────────────────────────────────────────────

const STEPS = ["Upload", "Context", "Review Fields", "Validate", "Analysis", "Report"];

function StepBar({ current }: { current: number }) {
  return (
    <div className="flex items-start mb-12">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-start flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-2">
            {/* Circle */}
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-mono font-bold border transition-all duration-300"
              style={
                i === current
                  ? {
                      background: "#22d3ee",
                      borderColor: "#67e8f9",
                      color: "#060b14",
                      boxShadow: "0 0 20px rgba(34,211,238,0.55)",
                    }
                  : i < current
                  ? {
                      background: "rgba(34,211,238,0.1)",
                      borderColor: "rgba(34,211,238,0.5)",
                      color: "#22d3ee",
                    }
                  : {
                      background: "rgba(15,23,42,0.6)",
                      borderColor: "rgba(100,116,139,0.3)",
                      color: "#475569",
                    }
              }
            >
              {i < current ? "✓" : `0${i + 1}`}
            </div>
            {/* Label */}
            <span
              className="text-xs font-medium tracking-wide whitespace-nowrap"
              style={{
                color:
                  i === current
                    ? "#22d3ee"
                    : i < current
                    ? "#94a3b8"
                    : "#334155",
              }}
            >
              {label}
            </span>
          </div>

          {/* Connector line */}
          {i < STEPS.length - 1 && (
            <div
              className="flex-1 h-px mx-2 mt-[18px] transition-all duration-300"
              style={{
                background:
                  i < current
                    ? "linear-gradient(90deg, rgba(34,211,238,0.6), rgba(34,211,238,0.2))"
                    : "rgba(30,41,59,0.8)",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Upload step ───────────────────────────────────────────────────────────────

function UploadStep({ onUpload }: { onUpload: (ocr: OCROutput) => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setLoading(true);
      setError(null);
      try {
        const ocr = await uploadDocument(files[0]);
        onUpload(ocr);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".png", ".jpg", ".jpeg", ".tiff"],
    },
    maxFiles: 1,
    disabled: loading,
  });

  return (
    <div className="max-w-xl mx-auto space-y-5 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-white tracking-tight">
          Upload Tax Document
        </h2>
        <p className="text-slate-500 text-sm">
          Supported forms: W-2 · 1099-NEC · 1099-INT
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        aria-label="Upload tax document — drop a file here or click to browse"
        role="button"
        className="relative rounded-2xl cursor-pointer transition-all duration-300 overflow-hidden"
        style={
          isDragActive
            ? {
                background: "rgba(34,211,238,0.05)",
                border: "1.5px dashed rgba(34,211,238,0.7)",
                boxShadow: "0 0 32px rgba(34,211,238,0.12)",
              }
            : loading
            ? { ...card, border: "1.5px dashed rgba(100,116,139,0.3)", opacity: 0.6 }
            : {
                ...card,
                border: "1.5px dashed rgba(100,116,139,0.3)",
              }
        }
      >
        <input {...getInputProps()} aria-label="Select tax document file" />

        {/* Corner accents */}
        {["top-3 left-3 border-t-2 border-l-2 rounded-tl",
          "top-3 right-3 border-t-2 border-r-2 rounded-tr",
          "bottom-3 left-3 border-b-2 border-l-2 rounded-bl",
          "bottom-3 right-3 border-b-2 border-r-2 rounded-br",
        ].map((cls, i) => (
          <div
            key={i}
            className={`absolute w-4 h-4 ${cls}`}
            style={{ borderColor: "rgba(34,211,238,0.3)" }}
          />
        ))}

        <div className="py-16 px-8 text-center">
          {loading ? (
            <div className="inline-block w-10 h-10 mb-5 rounded-full border-2 border-slate-700 border-t-cyan-400 animate-spin" />
          ) : (
            <div
              className="w-12 h-12 mx-auto mb-5 rounded-xl flex items-center justify-center"
              style={{
                background: "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.2)",
              }}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="rgba(34,211,238,0.8)"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
          )}

          <p className="text-slate-300 font-medium">
            {loading
              ? "Extracting text from document…"
              : isDragActive
              ? "Release to upload"
              : "Drop a file here, or click to browse"}
          </p>
          <p className="text-slate-600 text-xs mt-2 font-mono">
            PDF · PNG · JPG · TIFF — MAX 20 MB
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded-xl p-4 text-sm text-red-400"
          style={{
            background: "rgba(127,29,29,0.2)",
            border: "1px solid rgba(239,68,68,0.2)",
          }}
        >
          <span className="font-mono text-red-500 mr-2">ERROR</span>
          {error}
        </div>
      )}

      {/* Privacy note */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl"
        style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.12)" }}
      >
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs flex-shrink-0"
          style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}
        >
          <span className="text-emerald-400">✦</span>
        </div>
        <p className="text-xs text-slate-500">
          <span className="text-emerald-400 font-semibold">100% on-device.</span>{" "}
          OCR and AI inference run locally. No data is sent to any external server.
        </p>
      </div>
    </div>
  );
}

// ── Field Review step ─────────────────────────────────────────────────────────

// Field grouping definitions per form type
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

const FIELD_LABELS: Record<string, string> = {
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

// ── Shared review sub-components (must be module-level to preserve focus) ─────

const confColor = (c: number) =>
  c >= 0.8 ? "#34d399" : c >= 0.5 ? "#fbbf24" : "#f87171";

function SectionCard({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <div
        className="px-4 py-2.5 flex items-center gap-2"
        style={{ background: "rgba(15,23,42,0.8)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: accent }} />
        <span className="text-xs font-mono tracking-widest uppercase" style={{ color: accent }}>
          {title}
        </span>
      </div>
      <div className="p-3 space-y-2" style={{ background: "rgba(13,20,36,0.5)" }}>
        {children}
      </div>
    </div>
  );
}

function FieldRow({
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
          ? { background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.25)" }
          : { background: "rgba(15,23,42,0.5)", border: "1px solid rgba(255,255,255,0.05)" }
      }
    >
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs text-slate-500">
              {FIELD_LABELS[fieldKey] ?? fieldKey}
            </span>
            {field.confidence > 0 ? (
              <>
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: confColor(field.confidence) }}
                />
                <span className="text-xs font-mono" style={{ color: confColor(field.confidence) }}>
                  {Math.round(field.confidence * 100)}%
                </span>
              </>
            ) : (
              <span className="text-xs font-mono text-slate-700">not detected</span>
            )}
            <span className="ml-auto text-xs font-mono text-slate-700">
              {field.source !== "missing" ? field.source : ""}
            </span>
          </div>
          <input
            type="text"
            value={field.value}
            onChange={(e) => onChange(fieldKey, e.target.value)}
            disabled={isUnresolved}
            className="w-full text-slate-100 font-mono text-sm py-0.5 transition-colors focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: "transparent",
              border: "none",
              borderBottom: "1px solid rgba(71,85,105,0.4)",
            }}
            onFocus={(e) => { e.target.style.borderBottomColor = "rgba(34,211,238,0.5)"; }}
            onBlur={(e) => { e.target.style.borderBottomColor = "rgba(71,85,105,0.4)"; }}
          />
        </div>
        <button
          onClick={() => onToggle(fieldKey)}
          className="text-xs px-2 py-0.5 rounded border transition-all flex-shrink-0 font-mono"
          style={
            isUnresolved
              ? { borderColor: "rgba(251,191,36,0.4)", color: "#fbbf24", background: "rgba(251,191,36,0.08)" }
              : { borderColor: "rgba(71,85,105,0.4)", color: "#475569" }
          }
        >
          {isUnresolved ? "UNRESOLVED" : "FLAG"}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function FieldReviewStep({
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
    // Populate from backend OCR results
    for (const [k, v] of Object.entries(ocr.field_candidates)) {
      init[k] = { value: v.value ?? "", source: v.source, confidence: v.confidence };
    }
    // Add empty placeholders for every field in the group layout that wasn't returned
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

  // Determine which group layout to use
  const formType = fields["form_type"]?.value || "W-2";
  const groups = FIELD_GROUPS[formType] ?? FIELD_GROUPS["W-2"];

  // Track which field keys are covered by groups
  const groupedKeys = new Set(groups.flatMap((g) => g.fields));

  // Low-confidence fields (< 0.6) for the review flags section
  const reviewFlags = Object.entries(fields).filter(
    ([, f]) => f.confidence < 0.6 && f.value
  );

  // Any fields not covered by the group definitions (extra fields from LLM)
  const otherKeys = Object.keys(fields).filter(
    (k) => !groupedKeys.has(k) && k !== "raw_note"
  );

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
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

      {/* Review flags — low confidence fields surfaced at top */}
      {reviewFlags.length > 0 && (
        <SectionCard title="Review Flags — Low Confidence" accent="#f87171">
          {reviewFlags.map(([key]) => (
            <FieldRow key={key} fieldKey={key} field={fields[key]} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      )}

      {/* Grouped sections — always show all defined fields so user can fill missing ones */}
      {groups.map((group) => (
        <SectionCard key={group.title} title={group.title} accent={group.accent}>
          {group.fields.map((key) => (
            <FieldRow key={key} fieldKey={key} field={fields[key] ?? { value: "", source: "missing", confidence: 0 }} isUnresolved={unresolved.has(key)} onChange={handleChange} onToggle={toggleUnresolved} />
          ))}
        </SectionCard>
      ))}

      {/* Other fields not covered by group definitions */}
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

// ── Validation step ───────────────────────────────────────────────────────────

const ANALYSIS_PROVIDER_OPTIONS: {
  value: AnalysisPreferences["provider"];
  label: string;
  hint: string;
  placeholder: string;
}[] = [
  {
    value: "ollama",
    label: "Local Ollama",
    hint: "Uses the Ollama model configured on your machine.",
    placeholder: "Optional override, e.g. qwen3:8b",
  },
  {
    value: "openai",
    label: "ChatGPT / OpenAI",
    hint: "Uses the OpenAI API key configured in the backend.",
    placeholder: "Optional override, e.g. gpt-5.2",
  },
  {
    value: "anthropic",
    label: "Claude / Anthropic",
    hint: "Uses the Anthropic API key configured in the backend.",
    placeholder: "Optional override, e.g. claude-sonnet-4-20250514",
  },
  {
    value: "gemini",
    label: "Gemini / Google",
    hint: "Uses the Gemini API key configured in the backend.",
    placeholder: "Optional override, e.g. gemini-3-flash-preview",
  },
];

function ValidationStep({
  validation,
  onAnalyze,
  onBack,
}: {
  validation: ValidationOutput;
  onAnalyze: (preferences: AnalysisPreferences) => void;
  onBack: () => void;
}) {
  const [provider, setProvider] = useState<AnalysisPreferences["provider"]>("ollama");
  const [model, setModel] = useState("");

  const statusCfg = {
    ok:      { label: "PASS", icon: "✓", color: "#34d399", bg: "rgba(52,211,153,0.06)", bd: "rgba(52,211,153,0.2)" },
    warning: { label: "WARN", icon: "!", color: "#fbbf24", bg: "rgba(251,191,36,0.06)", bd: "rgba(251,191,36,0.2)" },
    error:   { label: "FAIL", icon: "✕", color: "#f87171", bg: "rgba(248,113,113,0.06)", bd: "rgba(248,113,113,0.2)" },
  };
  const cfg = statusCfg[validation.status as keyof typeof statusCfg] ?? statusCfg.warning;
  const selectedProvider = ANALYSIS_PROVIDER_OPTIONS.find((option) => option.value === provider) ?? ANALYSIS_PROVIDER_OPTIONS[0];
  const inputStyle = {
    background: "rgba(13,20,36,0.6)",
    border: "1px solid rgba(71,85,105,0.4)",
    borderRadius: "0.5rem",
    color: "#e2e8f0",
    padding: "0.5rem 0.75rem",
    width: "100%",
    fontSize: "0.875rem",
    outline: "none",
  } as React.CSSProperties;

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Validation Results</h2>
        <p className="text-slate-500 text-sm mt-1">
          Rule checks passed. Ready to calculate your tax outcome.
        </p>
      </div>

      {/* Status badge */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 rounded-xl"
        style={{ background: cfg.bg, border: `1px solid ${cfg.bd}` }}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
          style={{ background: cfg.bg, border: `1.5px solid ${cfg.bd}`, color: cfg.color }}
        >
          {cfg.icon}
        </div>
        <div>
          <p className="font-mono font-bold text-sm" style={{ color: cfg.color }}>
            {cfg.label}
          </p>
          <p className="text-xs text-slate-500">
            {validation.issues.length === 0
              ? "All checks passed"
              : `${validation.issues.length} issue${validation.issues.length !== 1 ? "s" : ""} found`}
          </p>
        </div>
      </div>

      {/* Issues */}
      {validation.issues.length > 0 && (
        <div className="space-y-2">
          {validation.issues.map((issue, i) => (
            <div
              key={i}
              className="flex gap-3 px-4 py-3 rounded-xl"
              style={
                issue.severity === "error"
                  ? { background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.15)" }
                  : { background: "rgba(120,53,15,0.15)", border: "1px solid rgba(251,191,36,0.15)" }
              }
            >
              <span
                className="font-mono text-xs font-bold flex-shrink-0 mt-0.5"
                style={{ color: issue.severity === "error" ? "#f87171" : "#fbbf24" }}
              >
                {issue.severity === "error" ? "ERR" : "WRN"}
              </span>
              <div>
                <p className="text-sm text-slate-200">{issue.message}</p>
                <p className="text-xs font-mono text-slate-600 mt-0.5">
                  {issue.field} · {issue.type}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <SectionCard title="AI Explanation Provider" accent="#22d3ee">
        <div className="space-y-3">
          <div>
            <p className="text-xs text-slate-500 mb-1.5">
              Choose the model provider for the report explanations
            </p>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as AnalysisPreferences["provider"])}
              style={inputStyle}
            >
              {ANALYSIS_PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value} style={{ background: "#0d1424" }}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-slate-600">{selectedProvider.hint}</p>
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Optional model override</p>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={selectedProvider.placeholder}
              style={inputStyle}
            />
          </div>
          <p className="text-xs text-slate-700">
            This only changes the AI explanations in the final report. Extraction, validation, and tax math stay on the current pipeline.
          </p>
        </div>
      </SectionCard>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="py-3.5 px-5 rounded-xl text-sm font-semibold transition-all"
          style={{ background: "rgba(71,85,105,0.2)", border: "1px solid rgba(71,85,105,0.3)", color: "#94a3b8" }}
        >
          ← Back
        </button>
        <button
          onClick={() =>
            onAnalyze({
              provider,
              model: model.trim() || undefined,
            })
          }
          className="flex-1 py-3.5 rounded-xl text-white font-semibold text-sm transition-all"
          style={{ background: "#2563eb", ...glowBtn() }}
        >
          Calculate Tax Outcome →
        </button>
      </div>
    </div>
  );
}

// ── Context step (taxpayer / residency questionnaire) ─────────────────────────

const STATUS_OPTIONS = [
  { value: "US_CITIZEN", label: "US Citizen / Domestic Filer" },
  { value: "GREEN_CARD", label: "Green Card Holder / Permanent Resident" },
  { value: "RESIDENT_ALIEN", label: "Resident for US Tax Purposes" },
  { value: "F-1", label: "F-1 — Student" },
  { value: "J-1", label: "J-1 — Exchange Visitor" },
  { value: "OPT", label: "OPT — Optional Practical Training" },
  { value: "CPT", label: "CPT — Curricular Practical Training" },
  { value: "H-1B", label: "H-1B — Specialty Occupation" },
  { value: "other", label: "Other / Not Sure" },
];

const DOMESTIC_STATUS_VALUES = new Set(["US_CITIZEN", "GREEN_CARD", "RESIDENT_ALIEN"]);
const STUDENT_STATUS_VALUES = new Set(["F-1", "J-1", "OPT", "CPT"]);

function ContextStep({
  documentId,
  onConfirm,
  onBack,
}: {
  documentId: string;
  onConfirm: () => void;
  onBack: () => void;
}) {
  const [visaType, setVisaType] = useState("US_CITIZEN");
  const [entryDate, setEntryDate] = useState("");
  const [days0, setDays0] = useState("");
  const [days1, setDays1] = useState("");
  const [days2, setDays2] = useState("");
  const [has1042s, setHas1042s] = useState(false);
  const [wantsState, setWantsState] = useState(false);
  const [claimsExempt, setClaimsExempt] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputStyle = {
    background: "rgba(13,20,36,0.6)",
    border: "1px solid rgba(71,85,105,0.4)",
    borderRadius: "0.5rem",
    color: "#e2e8f0",
    padding: "0.5rem 0.75rem",
    width: "100%",
    fontSize: "0.875rem",
    outline: "none",
  } as React.CSSProperties;

  const isDomesticStatus = DOMESTIC_STATUS_VALUES.has(visaType);
  const showResidencyTravelQuestions = !isDomesticStatus;
  const showStudentQuestions = STUDENT_STATUS_VALUES.has(visaType);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await saveContext(documentId, {
        visa_type: visaType,
        first_us_entry_date: entryDate || undefined,
        current_year_days_in_us: days0 ? parseInt(days0) : undefined,
        prior_year_days_in_us: days1 ? parseInt(days1) : undefined,
        second_prior_year_days_in_us: days2 ? parseInt(days2) : undefined,
        has_1042s: has1042s,
        wants_state_estimate: wantsState,
        claims_exempt_individual: claimsExempt,
      });
      onConfirm();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Taxpayer Context</h2>
          <p className="text-slate-500 text-sm mt-1">
            Used to tailor residency checks and special tax rules when relevant. Domestic and international filers are both supported.
          </p>
        </div>
        <button
          onClick={onBack}
          className="text-sm text-slate-600 hover:text-slate-300 transition-colors mt-1 whitespace-nowrap"
        >
          ← Re-upload
        </button>
      </div>

      <SectionCard title="Residency / Status" accent="#22d3ee">
        <div className="space-y-3">
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Tax residency or visa status during the tax year</p>
            <select
              value={visaType}
              onChange={(e) => setVisaType(e.target.value)}
              style={inputStyle}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value} style={{ background: "#0d1424" }}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-slate-600">
            {isDomesticStatus
              ? "Domestic filer selected. International-only residency questions are hidden below."
              : "We use this to determine whether nonresident, treaty, or FICA-related rules may apply."}
          </p>
          {showResidencyTravelQuestions && (
          <div>
            <p className="text-xs text-slate-500 mb-1.5">
                First year you entered the US in the status above
                <span className="text-slate-700 ml-1">(if relevant, e.g. 2021)</span>
            </p>
            <input
              type="text"
              placeholder="e.g. 2021"
              value={entryDate}
              onChange={(e) => setEntryDate(e.target.value)}
              style={inputStyle}
            />
          </div>
          )}
        </div>
      </SectionCard>

      {showResidencyTravelQuestions && (
      <SectionCard title="Days Present in the US" accent="#818cf8">
        <p className="text-xs text-slate-600 mb-3">
            Count every day you were physically inside the US. Used for substantial presence and nonresident checks when applicable.
        </p>
        <div className="space-y-3">
          {[
            { label: "Current tax year", value: days0, set: setDays0 },
            { label: "Prior year", value: days1, set: setDays1 },
            { label: "Second prior year", value: days2, set: setDays2 },
          ].map(({ label, value, set }) => (
            <div key={label} className="flex items-center gap-3">
              <span className="text-xs text-slate-500 w-36 flex-shrink-0">{label}</span>
              <input
                type="number"
                min={0}
                max={366}
                placeholder="—"
                value={value}
                onChange={(e) => set(e.target.value)}
                style={{ ...inputStyle, width: "6rem" }}
              />
            </div>
          ))}
        </div>
      </SectionCard>
      )}

      <SectionCard title="Additional Context" accent="#34d399">
        <div className="space-y-3">
          {[
            ...(!isDomesticStatus
              ? [{ label: "I received Form 1042-S (treaty / scholarship income)", value: has1042s, set: setHas1042s }]
              : []),
            { label: "I want a state tax estimate in addition to federal", value: wantsState, set: setWantsState },
            ...(showStudentQuestions
              ? [{ label: "I believe I qualify as an exempt individual (F/J/M/Q within first 5 years)", value: claimsExempt, set: setClaimsExempt }]
              : []),
          ].map(({ label, value, set }) => (
            <label key={label} className="flex items-start gap-3 cursor-pointer group">
              <div
                className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"
                style={
                  value
                    ? { background: "rgba(34,211,238,0.2)", border: "1.5px solid rgba(34,211,238,0.7)" }
                    : { background: "transparent", border: "1.5px solid rgba(71,85,105,0.5)" }
                }
                onClick={() => set(!value)}
              >
                {value && <span className="text-xs" style={{ color: "#22d3ee" }}>✓</span>}
              </div>
              <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors leading-snug">
                {label}
              </span>
            </label>
          ))}
        </div>
      </SectionCard>

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
          className="py-3 px-5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40"
          style={{ background: "rgba(71,85,105,0.2)", border: "1px solid rgba(71,85,105,0.3)", color: "#94a3b8" }}
        >
          ← Back
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="flex-1 py-3 rounded-xl text-white font-semibold text-sm transition-all disabled:opacity-40"
          style={loading ? { background: "#2563eb", opacity: 0.6 } : { background: "#2563eb", ...glowBtn() }}
        >
          {loading ? "Saving…" : "Continue to Field Review →"}
        </button>
      </div>
    </div>
  );
}

// ── Analysis step (spinner + rotating hints) ──────────────────────────────────

const ANALYSIS_HINTS = [
  "Applying 2025 IRS tax brackets to your taxable income…",
  "Checking FICA exemption eligibility under IRC §3121(b)(19)…",
  "Calculating your estimated federal balance…",
];

function AnalysisStep({
  documentId,
  preferences,
  onComplete,
}: {
  documentId: string;
  preferences: AnalysisPreferences;
  onComplete: (report: TaxReport) => void;
}) {
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    analyzeDocument(documentId, preferences)
      .then((report) => { if (!cancelled) onComplete(report); })
      .catch((e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });

    const cycle = setInterval(() => {
      if (!cancelled) setHintIndex((i) => (i + 1) % ANALYSIS_HINTS.length);
    }, 3000);

    return () => { cancelled = true; clearInterval(cycle); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, preferences]);

  return (
    <div className="space-y-8 animate-fade-in text-center">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Calculating…</h2>
        <p className="text-slate-500 text-sm mt-1">
          Applying 2025 IRS rules with {preferences.provider === "ollama" ? "a local Ollama model" : `${preferences.provider} for the explanation layer`}.
        </p>
      </div>

      {/* Spinner */}
      <div className="flex justify-center">
        <div
          className="w-16 h-16 rounded-full border-2 animate-spin"
          style={{ borderColor: "rgba(34,211,238,0.15)", borderTopColor: "#22d3ee" }}
        />
      </div>

      {/* Rotating hint */}
      <p className="text-sm font-mono text-slate-500 min-h-[1.5rem] transition-all">
        {ANALYSIS_HINTS[hintIndex]}
      </p>

      {error && (
        <div
          className="rounded-xl p-4 text-sm text-red-400 text-left"
          style={{ background: "rgba(127,29,29,0.2)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <span className="font-mono text-red-500 mr-2">ERROR</span>
          {error}
        </div>
      )}

      <p className="text-xs text-slate-700 font-mono">
        Running locally — this may take 30–90 seconds
      </p>
    </div>
  );
}

// ── Calculation Ledger step ───────────────────────────────────────────────────

function CalculationLedgerStep({ report }: { report: TaxReport }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleRow = (n: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });

  const outcomeConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string }> = {
    refund:   { label: "ESTIMATED REFUND",   color: "#34d399", bg: "rgba(52,211,153,0.07)",  border: "rgba(52,211,153,0.25)",  glow: "rgba(52,211,153,0.25)"  },
    owe:      { label: "ESTIMATED TAX OWED", color: "#f87171", bg: "rgba(248,113,113,0.07)", border: "rgba(248,113,113,0.25)", glow: "rgba(248,113,113,0.2)"  },
    balanced: { label: "BALANCED",           color: "#60a5fa", bg: "rgba(96,165,250,0.07)",  border: "rgba(96,165,250,0.25)",  glow: "rgba(96,165,250,0.2)"   },
    unknown:  { label: "OUTCOME UNKNOWN",    color: "#94a3b8", bg: "rgba(100,116,139,0.07)", border: "rgba(100,116,139,0.25)", glow: "rgba(100,116,139,0.1)"  },
  };

  const cfg = outcomeConfig[report.estimated_outcome] ?? outcomeConfig.unknown;
  const amountStr = report.estimated_amount != null
    ? `$${report.estimated_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : null;

  const flagSteps = report.calculation_steps.filter((s) => s.is_flag);
  const normalSteps = report.calculation_steps.filter((s) => !s.is_flag);

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Tax Report</h2>
        <p className="text-xs font-mono text-slate-700 mt-1">{report.document_id}</p>
      </div>

      {/* Outcome banner */}
      <div
        className="rounded-2xl px-6 py-5 text-center"
        style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, boxShadow: `0 0 36px ${cfg.glow}` }}
      >
        <p className="text-xs font-mono tracking-widest mb-3" style={{ color: cfg.color }}>
          {cfg.label}
        </p>
        {amountStr && (
          <p className="text-5xl font-bold tracking-tight mb-2" style={{ color: cfg.color }}>
            {amountStr}
          </p>
        )}
        {report.outcome_explanation && (
          <p className="text-sm text-slate-400 mt-3 leading-relaxed max-w-md mx-auto">
            {report.outcome_explanation}
          </p>
        )}
        <p className="text-xs text-slate-600 mt-3">
          Estimate only — consult a qualified tax professional before filing.
        </p>
      </div>

      {/* Calculation Ledger */}
      {normalSteps.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.07)" }}
        >
          {/* Table header */}
          <div
            className="grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-2.5 text-xs font-mono tracking-widest uppercase"
            style={{ background: "rgba(15,23,42,0.9)", borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#475569" }}
          >
            <span>#</span>
            <span>Step</span>
            <span>Amount</span>
          </div>

          {normalSteps.map((step) => {
            const isOpen = expanded.has(step.step_number);
            return (
              <div key={step.step_number} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                {/* Row */}
                <button
                  onClick={() => toggleRow(step.step_number)}
                  className="w-full grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
                  style={{ background: "rgba(13,20,36,0.5)" }}
                >
                  <span className="text-xs font-mono text-slate-600 pt-0.5">{step.step_number}</span>
                  <div>
                    <p className="text-sm text-slate-200">{step.label}</p>
                    <p className="text-xs text-slate-600 font-mono mt-0.5">{step.rule_reference}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-slate-100 whitespace-nowrap">{step.output_value}</p>
                    <p className="text-xs text-slate-700 mt-0.5">{isOpen ? "▲" : "▼"}</p>
                  </div>
                </button>

                {/* Inline expansion */}
                {isOpen && (
                  <div
                    className="px-4 py-3 text-sm text-slate-400 leading-relaxed"
                    style={{ background: "rgba(6,11,20,0.6)", borderTop: "1px solid rgba(255,255,255,0.04)" }}
                  >
                    <span className="text-xs font-mono text-slate-600 mr-2">Input:</span>
                    <span className="font-mono text-slate-500">{step.input_value}</span>
                    {step.explanation && (
                      <p className="mt-2 text-slate-400">{step.explanation}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* FICA Handoff Card */}
      {flagSteps.length > 0 && (
        <div
          className="rounded-xl p-5 space-y-3"
          style={{ background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.25)" }}
        >
          <div className="flex items-center gap-2">
            <span className="text-base">⚠</span>
            <p className="text-sm font-semibold text-amber-300">Potential FICA Refund Opportunity</p>
          </div>
          {flagSteps.map((step) => (
            <div key={step.step_number} className="space-y-1">
              <p className="text-sm text-amber-200/80">{step.label.replace("⚠ ", "")}</p>
              <p className="text-xs font-mono text-amber-200/50">{step.output_value}</p>
              {step.explanation && (
                <p className="text-xs text-slate-500 leading-relaxed">{step.explanation}</p>
              )}
              <p className="text-xs text-slate-600 font-mono">{step.rule_reference}</p>
            </div>
          ))}
          <p className="text-xs text-slate-500 pt-1">
            File <span className="text-amber-300 font-semibold">Form 843</span> with the IRS to claim a refund of incorrectly withheld FICA taxes. Attach a copy of your W-2 and a statement from your employer.
          </p>
        </div>
      )}

      {/* Validation notes */}
      {report.validation_results.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div
            className="px-4 py-2.5"
            style={{ background: "rgba(15,23,42,0.8)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
          >
            <span className="text-xs font-mono tracking-widest uppercase" style={{ color: "#fb923c" }}>
              Validation Notes
            </span>
          </div>
          <div className="px-4 py-3 space-y-2" style={{ background: "rgba(13,20,36,0.5)" }}>
            {report.validation_results.map((v, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <span className="font-mono text-xs flex-shrink-0 mt-0.5"
                  style={{ color: v.severity === "error" ? "#f87171" : "#fbbf24" }}>
                  {v.severity === "error" ? "ERR" : "WRN"}
                </span>
                <span className="text-slate-400">{v.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => window.location.reload()}
        className="w-full py-3 rounded-xl text-slate-400 hover:text-slate-200 font-medium text-sm transition-all"
        style={{ border: "1px solid rgba(71,85,105,0.4)" }}
      >
        Review Another Document
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [step, setStep] = useState(0);
  const [ocr, setOcr] = useState<OCROutput | null>(null);
  const [validation, setValidation] = useState<ValidationOutput | null>(null);
  const [report, setReport] = useState<TaxReport | null>(null);
  const [analysisPreferences, setAnalysisPreferences] = useState<AnalysisPreferences>({
    provider: "ollama",
  });

  return (
    <div>
      <StepBar current={step} />

      {/* Step 0: Upload */}
      {step === 0 && (
        <UploadStep onUpload={(o) => { setOcr(o); setStep(1); }} />
      )}

      {/* Step 1: Immigration context */}
      {step === 1 && ocr && (
        <ContextStep
          documentId={ocr.document_id}
          onConfirm={() => setStep(2)}
          onBack={() => { setOcr(null); setStep(0); }}
        />
      )}

      {/* Step 2: Field review */}
      {step === 2 && ocr && (
        <FieldReviewStep
          ocr={ocr}
          onConfirm={(v) => { setValidation(v); setStep(3); }}
          onBack={() => setStep(1)}
        />
      )}

      {/* Step 3: Validation */}
      {step === 3 && validation && (
        <ValidationStep
          validation={validation}
          onAnalyze={(preferences) => {
            setAnalysisPreferences(preferences);
            setStep(4);
          }}
          onBack={() => setStep(2)}
        />
      )}

      {/* Step 4: Analysis (spinner + hints) */}
      {step === 4 && ocr && (
        <AnalysisStep
          documentId={ocr.document_id}
          preferences={analysisPreferences}
          onComplete={(r) => { setReport(r); setStep(5); }}
        />
      )}

      {/* Step 5: Calculation Ledger */}
      {step === 5 && report && <CalculationLedgerStep report={report} />}
    </div>
  );
}
