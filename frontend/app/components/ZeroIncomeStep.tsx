"use client";

/**
 * ZeroIncomeStep — NRA zero-income Form 8843 filing path.
 *
 * Flow:
 *   UploadStep "No income" button  →  ZeroIncomeStep  →  direct PDF download
 *
 * Pre-populates institution fields from page.tsx context state when the user
 * previously completed ContextStep in the income path.
 */

import { useState } from "react";
import { type Form8843Data, generate8843, bundleForms } from "../lib/api";
import { NRA_VISA_TYPES } from "../lib/constants";
import { inputStyle, glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";

const CURRENT_YEAR = 2025;

const TIN_OPTIONS = [
  { value: "ssn",         label: "Social Security Number (SSN)" },
  { value: "itin",        label: "Individual Taxpayer Identification Number (ITIN)" },
  { value: "applied_for", label: "Applied for (ITIN application pending)" },
  { value: "none",        label: "None — exempt individuals need not obtain one" },
];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  onBack: () => void;
  /** Pre-populated from ContextStep if user went through income path first */
  prefill?: {
    visaType?: string;
    entryYear?: string;
    institutionName?: string;
    institutionCity?: string;
    institutionState?: string;
  };
}

export function ZeroIncomeStep({ onBack, prefill }: Props) {
  // Identity
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [tinStatus, setTinStatus] = useState<"ssn" | "itin" | "applied_for" | "none">("none");
  const [tinValue, setTinValue] = useState("");

  // Visa / residency
  const [visaType, setVisaType] = useState(prefill?.visaType ?? "F-1");
  const [entryYear, setEntryYear] = useState(prefill?.entryYear ?? "");
  const [daysInUs, setDaysInUs] = useState("");

  // Role
  const [role, setRole] = useState<"student" | "teacher_researcher">("student");

  // Institution (pre-populated from ContextStep when available)
  const [instName, setInstName] = useState(prefill?.institutionName ?? "");
  const [instCity, setInstCity] = useState(prefill?.institutionCity ?? "");
  const [instState, setInstState] = useState(prefill?.institutionState ?? "");

  // J-1/Q exchange info
  const [exchangeProgram, setExchangeProgram] = useState("");
  const [sponsorName, setSponsorName] = useState("");
  const [sponsorAddress, setSponsorAddress] = useState("");

  // Catch-up years
  const [showCatchUp, setShowCatchUp] = useState(false);
  const [catchUpYears, setCatchUpYears] = useState<number[]>([]);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);

  const needsExchangeInfo = visaType === "J-1" || visaType === "Q";

  // Compute prior exempt years list (entry year → current year - 1)
  function computeExemptPriorYears(): number[] {
    const ey = parseInt(entryYear);
    if (!ey || ey > CURRENT_YEAR) return [];
    const years: number[] = [];
    for (let y = ey; y < CURRENT_YEAR; y++) {
      years.push(y);
    }
    return years.slice(0, 5); // cap at 5 per IRS rules
  }

  function buildFormData(): Form8843Data {
    return {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      tin_status: tinStatus,
      tin_value: tinValue.trim() || undefined,
      visa_type: visaType,
      first_us_entry_date: entryYear || undefined,
      days_in_us_current_year: daysInUs ? parseInt(daysInUs) : undefined,
      role,
      institution_name: instName.trim() || undefined,
      institution_city: instCity.trim() || undefined,
      institution_state: instState.trim().toUpperCase() || undefined,
      exempt_prior_years: computeExemptPriorYears(),
      status_change_applied: false,
      exchange_program_name: exchangeProgram.trim() || undefined,
      sponsor_name: sponsorName.trim() || undefined,
      sponsor_address: sponsorAddress.trim() || undefined,
      has_income: false,
      tax_year: CURRENT_YEAR,
      catch_up_years: catchUpYears,
    };
  }

  async function handleDownload() {
    if (!firstName.trim() || !lastName.trim()) {
      setError("First and last name are required.");
      return;
    }
    if (!NRA_VISA_TYPES.includes(visaType)) {
      setError("Form 8843 is only required for NRA visa types (F-1, F-2, J-1, J-2, M-1, M-2, Q).");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = buildFormData();
      const allYears = catchUpYears.length > 0
        ? [CURRENT_YEAR, ...catchUpYears].sort((a, b) => a - b)
        : [CURRENT_YEAR];

      let blob: Blob;
      if (allYears.length > 1) {
        blob = await bundleForms(data, allYears);
        triggerDownload(blob, `f8843_bundle_${lastName.toLowerCase()}.pdf`);
      } else {
        blob = await generate8843(data, CURRENT_YEAR);
        triggerDownload(blob, `f8843_${CURRENT_YEAR}_${lastName.toLowerCase()}.pdf`);
      }
      setDownloaded(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Form 8843 — Zero Income</h2>
        <p className="text-slate-500 text-sm mt-1">
          All {NRA_VISA_TYPES.slice(0, 4).join(", ")} and other NRA visa holders must file this statement
          even with no US-source income. It is not a tax return.
        </p>
      </div>

      {/* Identity */}
      <SectionCard title="Your Name" accent="#22d3ee">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="zi-first-name" className="text-xs text-slate-500 mb-1.5 block">First name</label>
            <input
              id="zi-first-name"
              type="text"
              placeholder="Jane"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              style={inputStyle}
            />
          </div>
          <div>
            <label htmlFor="zi-last-name" className="text-xs text-slate-500 mb-1.5 block">Last name</label>
            <input
              id="zi-last-name"
              type="text"
              placeholder="Doe"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              style={inputStyle}
            />
          </div>
        </div>
      </SectionCard>

      {/* TIN */}
      <SectionCard title="Taxpayer ID" accent="#818cf8">
        <div className="space-y-3">
          <div>
            <label htmlFor="zi-tin-status" className="text-xs text-slate-500 mb-1.5 block">
              Do you have a US taxpayer identification number?
            </label>
            <select
              id="zi-tin-status"
              value={tinStatus}
              onChange={(e) => setTinStatus(e.target.value as typeof tinStatus)}
              style={inputStyle}
            >
              {TIN_OPTIONS.map((o) => (
                <option key={o.value} value={o.value} style={{ background: "#0d1424" }}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {(tinStatus === "ssn" || tinStatus === "itin") && (
            <div>
              <label htmlFor="zi-tin-value" className="text-xs text-slate-500 mb-1.5 block">
                {tinStatus === "ssn" ? "SSN" : "ITIN"} (format: XXX-XX-XXXX)
              </label>
              <input
                id="zi-tin-value"
                type="text"
                placeholder="000-00-0000"
                value={tinValue}
                onChange={(e) => setTinValue(e.target.value)}
                style={{ ...inputStyle, maxWidth: "14rem", fontFamily: "monospace" }}
              />
            </div>
          )}
        </div>
      </SectionCard>

      {/* Visa / residency */}
      <SectionCard title="Visa &amp; Residency" accent="#22d3ee">
        <div className="space-y-3">
          <div>
            <label htmlFor="zi-visa-type" className="text-xs text-slate-500 mb-1.5 block">Visa type</label>
            <select
              id="zi-visa-type"
              value={visaType}
              onChange={(e) => setVisaType(e.target.value)}
              style={inputStyle}
            >
              {NRA_VISA_TYPES.map((v) => (
                <option key={v} value={v} style={{ background: "#0d1424" }}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="zi-entry-year" className="text-xs text-slate-500 mb-1.5 block">
              Year you first entered the US under this visa
            </label>
            <input
              id="zi-entry-year"
              type="text"
              placeholder="e.g. 2022"
              value={entryYear}
              onChange={(e) => setEntryYear(e.target.value)}
              style={{ ...inputStyle, maxWidth: "8rem" }}
            />
          </div>
          <div>
            <label htmlFor="zi-days" className="text-xs text-slate-500 mb-1.5 block">
              Days in the US during {CURRENT_YEAR} (Line 3)
            </label>
            <input
              id="zi-days"
              type="number"
              min={0}
              max={366}
              placeholder="—"
              value={daysInUs}
              onChange={(e) => setDaysInUs(e.target.value)}
              style={{ ...inputStyle, maxWidth: "6rem" }}
            />
          </div>
        </div>
      </SectionCard>

      {/* Role */}
      <SectionCard title="Your Role" accent="#34d399">
        <div className="space-y-2">
          {[
            { value: "student",            label: "Student (Part I — most F-1/J-1 filers)" },
            { value: "teacher_researcher", label: "Teacher or researcher (Part II)" },
          ].map(({ value, label }) => (
            <div
              key={value}
              role="radio"
              aria-checked={role === value}
              tabIndex={0}
              onClick={() => setRole(value as typeof role)}
              onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); setRole(value as typeof role); } }}
              className="flex items-start gap-3 cursor-pointer group outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 rounded"
            >
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"
                aria-hidden="true"
                style={
                  role === value
                    ? { background: "rgba(52,211,153,0.2)", border: "1.5px solid rgba(52,211,153,0.7)" }
                    : { background: "transparent", border: "1.5px solid rgba(71,85,105,0.5)" }
                }
              >
                {role === value && <div className="w-2.5 h-2.5 rounded-full" style={{ background: "#34d399" }} />}
              </div>
              <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">{label}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Institution */}
      <SectionCard title="Academic Institution (Lines 4a–4c)" accent="#818cf8">
        <div className="space-y-3">
          <div>
            <label htmlFor="zi-inst-name" className="text-xs text-slate-500 mb-1.5 block">
              School / university name <span className="text-slate-700">(Line 4a)</span>
            </label>
            <input
              id="zi-inst-name"
              type="text"
              placeholder="e.g. University of Michigan"
              value={instName}
              onChange={(e) => setInstName(e.target.value)}
              style={inputStyle}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="zi-inst-city" className="text-xs text-slate-500 mb-1.5 block">City <span className="text-slate-700">(4b)</span></label>
              <input
                id="zi-inst-city"
                type="text"
                placeholder="Ann Arbor"
                value={instCity}
                onChange={(e) => setInstCity(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="zi-inst-state" className="text-xs text-slate-500 mb-1.5 block">State <span className="text-slate-700">(4c, 2-letter)</span></label>
              <input
                id="zi-inst-state"
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

      {/* J-1/Q exchange info */}
      {needsExchangeInfo && (
        <SectionCard title="Exchange Program Info (Part III)" accent="#fbbf24">
          <div className="space-y-3">
            <div>
              <label htmlFor="zi-exchange" className="text-xs text-slate-500 mb-1.5 block">Exchange program name</label>
              <input
                id="zi-exchange"
                type="text"
                placeholder="e.g. Fulbright Program"
                value={exchangeProgram}
                onChange={(e) => setExchangeProgram(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="zi-sponsor" className="text-xs text-slate-500 mb-1.5 block">Sponsoring organization name</label>
              <input
                id="zi-sponsor"
                type="text"
                placeholder="e.g. US Dept of State"
                value={sponsorName}
                onChange={(e) => setSponsorName(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="zi-sponsor-addr" className="text-xs text-slate-500 mb-1.5 block">Sponsor address</label>
              <input
                id="zi-sponsor-addr"
                type="text"
                placeholder="2200 C St NW, Washington DC 20520"
                value={sponsorAddress}
                onChange={(e) => setSponsorAddress(e.target.value)}
                style={inputStyle}
              />
            </div>
          </div>
        </SectionCard>
      )}

      {/* Catch-up filing */}
      <SectionCard title="Catch-Up Filing" accent="#f87171">
        <div className="space-y-3">
          <p className="text-xs text-slate-500">
            If you forgot to file Form 8843 in prior years, you can file late without penalty.
            Select additional years to include them in your download bundle.
          </p>
          <div
            role="checkbox"
            aria-checked={showCatchUp}
            tabIndex={0}
            onClick={() => { setShowCatchUp(!showCatchUp); if (showCatchUp) setCatchUpYears([]); }}
            onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); setShowCatchUp(!showCatchUp); if (showCatchUp) setCatchUpYears([]); } }}
            className="flex items-start gap-3 cursor-pointer group outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 rounded"
          >
            <div
              className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5 transition-all"
              aria-hidden="true"
              style={
                showCatchUp
                  ? { background: "rgba(248,113,113,0.2)", border: "1.5px solid rgba(248,113,113,0.7)" }
                  : { background: "transparent", border: "1.5px solid rgba(71,85,105,0.5)" }
              }
            >
              {showCatchUp && <span className="text-xs" style={{ color: "#f87171" }}>✓</span>}
            </div>
            <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
              I also need to file for prior years
            </span>
          </div>

          {showCatchUp && (
            <div className="space-y-2 pl-8">
              <p className="text-xs text-slate-600">Select the years you missed:</p>
              {[CURRENT_YEAR - 1, CURRENT_YEAR - 2, CURRENT_YEAR - 3, CURRENT_YEAR - 4].map((yr) => {
                const checked = catchUpYears.includes(yr);
                return (
                  <div
                    key={yr}
                    role="checkbox"
                    aria-checked={checked}
                    tabIndex={0}
                    onClick={() => setCatchUpYears(checked ? catchUpYears.filter((y) => y !== yr) : [...catchUpYears, yr])}
                    onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); setCatchUpYears(checked ? catchUpYears.filter((y) => y !== yr) : [...catchUpYears, yr]); } }}
                    className="flex items-center gap-3 cursor-pointer group outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 rounded"
                  >
                    <div
                      className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 transition-all"
                      aria-hidden="true"
                      style={
                        checked
                          ? { background: "rgba(248,113,113,0.2)", border: "1.5px solid rgba(248,113,113,0.6)" }
                          : { background: "transparent", border: "1.5px solid rgba(71,85,105,0.4)" }
                      }
                    >
                      {checked && <span className="text-xs" style={{ color: "#f87171" }}>✓</span>}
                    </div>
                    <span className="text-sm text-slate-400 group-hover:text-slate-300">{yr}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </SectionCard>

      {/* Mailing reminder */}
      <div
        className="rounded-xl p-4 text-xs space-y-1"
        style={{ background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.12)" }}
      >
        <p className="text-slate-400 font-medium">After downloading</p>
        <p className="text-slate-500">
          Sign the form, then mail to:{" "}
          <span className="text-slate-300 font-mono">
            Department of the Treasury, Internal Revenue Service, Austin, TX 73301
          </span>
        </p>
        <p className="text-slate-500">
          Deadline: <span className="text-slate-300">June 15, {CURRENT_YEAR}</span>
          &nbsp;·&nbsp;Form 8843 cannot be e-filed.
        </p>
      </div>

      {error && (
        <div
          className="rounded-xl p-4 text-sm text-red-400"
          style={{ background: "rgba(127,29,29,0.2)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <span className="font-mono text-red-500 mr-2">ERROR</span>
          {error}
        </div>
      )}

      {downloaded && (
        <div
          className="rounded-xl p-3 text-sm"
          style={{ background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.2)" }}
        >
          <span style={{ color: "#34d399" }}>✓</span>{" "}
          <span className="text-slate-300">
            Form 8843 downloaded.
            {catchUpYears.length > 0 && ` Bundle includes ${1 + catchUpYears.length} years.`}{" "}
            Remember to sign before mailing.
          </span>
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
          onClick={handleDownload}
          disabled={loading || !firstName.trim() || !lastName.trim()}
          className="flex-1 py-3 rounded-xl text-white font-semibold text-sm transition-all disabled:opacity-40"
          style={loading ? { background: "#22d3ee", opacity: 0.6 } : { background: "#22d3ee", color: "#0d1424", ...glowBtn() }}
        >
          {loading
            ? "Generating PDF…"
            : catchUpYears.length > 0
              ? `↓ Download Bundle (${1 + catchUpYears.length} forms)`
              : "↓ Download Form 8843"}
        </button>
      </div>
    </div>
  );
}
