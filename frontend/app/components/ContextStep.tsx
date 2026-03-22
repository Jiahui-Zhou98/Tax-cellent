"use client";

import { useState } from "react";
import { saveContext } from "../lib/api";
import { inputStyle, glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";

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

export function ContextStep({
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
