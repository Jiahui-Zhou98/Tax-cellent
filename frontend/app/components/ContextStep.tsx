"use client";

import { useState } from "react";
import { saveContext } from "../lib/api";
import { NRA_VISA_TYPES } from "../lib/constants";
import { inputStyle, glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";

const STATE_OPTIONS = [
  { value: "",      label: "Select a state…" },
  { value: "CA",    label: "California" },
  { value: "NY",    label: "New York" },
  { value: "TX",    label: "Texas (no state income tax)" },
  { value: "WA",    label: "Washington (no state income tax)" },
  { value: "IL",    label: "Illinois" },
  { value: "MA",    label: "Massachusetts" },
  { value: "OTHER", label: "Other (estimate unavailable)" },
];

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

export type ContextValues = {
  visaType: string;
  entryDate: string;
  days0: string;
  days1: string;
  days2: string;
  has1042s: boolean;
  wantsState: boolean;
  stateCode: string;
  claimsExempt: boolean;
  necExpenses: string;
  countryOfOrigin: string;
  instName: string;
  instCity: string;
  instState: string;
};

export function ContextStep({
  documentId,
  formType,
  onConfirm,
  onBack,
  onContextSaved,
  initialValues,
}: {
  documentId: string;
  formType?: string;
  onConfirm: () => void;
  onBack: () => void;
  initialValues?: ContextValues;
  onContextSaved?: (ctx: ContextValues & {
    entryYear?: string;
    institutionName?: string;
    institutionCity?: string;
    institutionState?: string;
  }) => void;
}) {
  const [visaType, setVisaType] = useState(initialValues?.visaType ?? "US_CITIZEN");
  const [entryDate, setEntryDate] = useState(initialValues?.entryDate ?? "");
  const [days0, setDays0] = useState(initialValues?.days0 ?? "");
  const [days1, setDays1] = useState(initialValues?.days1 ?? "");
  const [days2, setDays2] = useState(initialValues?.days2 ?? "");
  const [has1042s, setHas1042s] = useState(initialValues?.has1042s ?? false);
  const [wantsState, setWantsState] = useState(initialValues?.wantsState ?? false);
  const [stateCode, setStateCode] = useState(initialValues?.stateCode ?? "");
  const [claimsExempt, setClaimsExempt] = useState(initialValues?.claimsExempt ?? false);
  const [necExpenses, setNecExpenses] = useState(initialValues?.necExpenses ?? "");
  const [countryOfOrigin, setCountryOfOrigin] = useState(initialValues?.countryOfOrigin ?? "");
  const [instName, setInstName] = useState(initialValues?.instName ?? "");
  const [instCity, setInstCity] = useState(initialValues?.instCity ?? "");
  const [instState, setInstState] = useState(initialValues?.instState ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNEC = formType?.includes("NEC") || formType?.includes("1099-NEC");
  const showInstitutionFields = NRA_VISA_TYPES.includes(visaType);

  const isDomesticStatus = DOMESTIC_STATUS_VALUES.has(visaType);
  const showResidencyTravelQuestions = !isDomesticStatus;
  const showStudentQuestions = STUDENT_STATUS_VALUES.has(visaType);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const expenses = necExpenses ? parseFloat(necExpenses.replace(/,/g, "")) : undefined;
      await saveContext(documentId, {
        visa_type: visaType,
        first_us_entry_date: entryDate || undefined,
        current_year_days_in_us: days0 ? parseInt(days0) : undefined,
        prior_year_days_in_us: days1 ? parseInt(days1) : undefined,
        second_prior_year_days_in_us: days2 ? parseInt(days2) : undefined,
        has_1042s: has1042s,
        wants_state_estimate: wantsState,
        state_code: (wantsState && stateCode) ? stateCode : undefined,
        claims_exempt_individual: claimsExempt,
        nec_business_expenses: expenses,
        country_of_origin: countryOfOrigin.trim().toUpperCase() || undefined,
        institution_name: instName.trim() || undefined,
        institution_city: instCity.trim() || undefined,
        institution_state: instState.trim().toUpperCase() || undefined,
      });
      onContextSaved?.({
        visaType,
        entryDate,
        days0, days1, days2,
        has1042s, wantsState, stateCode,
        claimsExempt, necExpenses, countryOfOrigin,
        instName, instCity, instState,
        // backward-compat aliases consumed by ZeroIncomeStep prefill
        entryYear: entryDate || undefined,
        institutionName: instName.trim() || undefined,
        institutionCity: instCity.trim() || undefined,
        institutionState: instState.trim().toUpperCase() || undefined,
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
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Taxpayer Context</h2>
        <p className="text-slate-500 text-sm mt-1">
          Used to tailor residency checks and special tax rules when relevant. Domestic and international filers are both supported.
        </p>
      </div>

      <SectionCard title="Residency / Status" accent="#22d3ee">
        <div className="space-y-3">
          <div>
            <label htmlFor="visa-type-select" className="text-xs text-slate-500 mb-1.5 block">
              Tax residency or visa status during the tax year
            </label>
            <select
              id="visa-type-select"
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
              <label htmlFor="entry-date-input" className="text-xs text-slate-500 mb-1.5 block">
                First year you entered the US in the status above
                <span className="text-slate-700 ml-1">(if relevant, e.g. 2021)</span>
              </label>
              <input
                id="entry-date-input"
                type="text"
                placeholder="e.g. 2021"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                style={inputStyle}
              />
            </div>
          )}
          {showStudentQuestions && (
            <div>
              <label htmlFor="country-of-origin-input" className="text-xs text-slate-500 mb-1.5 block">
                Country of origin <span className="text-slate-700">(ISO 2-letter code, e.g. CN, IN, KR)</span>
                <span className="text-slate-600 ml-1">— used for tax treaty lookup</span>
              </label>
              <input
                id="country-of-origin-input"
                type="text"
                maxLength={2}
                placeholder="e.g. CN"
                value={countryOfOrigin}
                onChange={(e) => setCountryOfOrigin(e.target.value.toUpperCase())}
                style={{ ...inputStyle, maxWidth: "8rem", textTransform: "uppercase" }}
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
              { label: "Current tax year", value: days0, set: setDays0, id: "days-current" },
              { label: "Prior year", value: days1, set: setDays1, id: "days-prior" },
              { label: "Second prior year", value: days2, set: setDays2, id: "days-second-prior" },
            ].map(({ label, value, set, id }) => (
              <div key={label} className="flex items-center gap-3">
                <label htmlFor={id} className="text-xs text-slate-500 w-36 flex-shrink-0">{label}</label>
                <input
                  id={id}
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
            <div
              key={label}
              role="checkbox"
              aria-checked={value}
              tabIndex={0}
              onClick={() => set(!value)}
              onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); set(!value); } }}
              className="flex items-start gap-3 cursor-pointer group outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 rounded"
            >
              <div
                className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"
                aria-hidden="true"
                style={
                  value
                    ? { background: "rgba(34,211,238,0.2)", border: "1.5px solid rgba(34,211,238,0.7)" }
                    : { background: "transparent", border: "1.5px solid rgba(71,85,105,0.5)" }
                }
              >
                {value && <span className="text-xs" style={{ color: "#22d3ee" }}>✓</span>}
              </div>
              <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors leading-snug">
                {label}
              </span>
            </div>
          ))}
        </div>
      </SectionCard>

      {wantsState && (
        <SectionCard title="State for Tax Estimate" accent="#60a5fa">
          <div>
            <label htmlFor="state-select" className="text-xs text-slate-500 mb-1.5 block">
              Which state do you file in?
              <span className="text-slate-700 ml-1">(used only for the optional state estimate)</span>
            </label>
            <select
              id="state-select"
              value={stateCode}
              onChange={(e) => setStateCode(e.target.value)}
              style={inputStyle}
            >
              {STATE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value} style={{ background: "#0d1424" }}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </SectionCard>
      )}

      {showInstitutionFields && (
        <SectionCard title="Academic Institution (Form 8843)" accent="#818cf8">
          <p className="text-xs text-slate-600 mb-3">
            Required for Form 8843 (filed by all {visaType} visa holders, even with income).
            Leave blank if unknown — you can fill it in the Form 8843 step.
          </p>
          <div className="space-y-3">
            <div>
              <label htmlFor="ctx-inst-name" className="text-xs text-slate-500 mb-1.5 block">
                School / university name <span className="text-slate-700">(Line 4a)</span>
              </label>
              <input
                id="ctx-inst-name"
                type="text"
                placeholder="e.g. University of Michigan"
                value={instName}
                onChange={(e) => setInstName(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="ctx-inst-city" className="text-xs text-slate-500 mb-1.5 block">
                  City <span className="text-slate-700">(4b)</span>
                </label>
                <input
                  id="ctx-inst-city"
                  type="text"
                  placeholder="Ann Arbor"
                  value={instCity}
                  onChange={(e) => setInstCity(e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label htmlFor="ctx-inst-state" className="text-xs text-slate-500 mb-1.5 block">
                  State <span className="text-slate-700">(4c, 2-letter)</span>
                </label>
                <input
                  id="ctx-inst-state"
                  type="text"
                  maxLength={2}
                  placeholder="MI"
                  value={instState}
                  onChange={(e) => setInstState(e.target.value.toUpperCase())}
                  style={{ ...inputStyle, maxWidth: "6rem", textTransform: "uppercase" }}
                />
              </div>
            </div>
          </div>
        </SectionCard>
      )}

      {isNEC && (
        <SectionCard title="Self-Employment Expenses (1099-NEC)" accent="#fbbf24">
          <p className="text-xs text-slate-500 mb-3">
            If you had deductible business expenses (home office, equipment, software, etc.), enter the total here.
            This reduces your net self-employment income and lowers your SE tax. Leave blank if none.
          </p>
          <div>
            <label htmlFor="nec-expenses-input" className="text-xs text-slate-500 mb-1.5 block">
              Estimated business expenses (optional)
            </label>
            <input
              id="nec-expenses-input"
              type="number"
              min={0}
              max={9999999}
              step={1}
              placeholder="e.g. 2500"
              value={necExpenses}
              onChange={(e) => setNecExpenses(e.target.value)}
              style={{ ...inputStyle, maxWidth: "14rem" }}
            />
          </div>
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
