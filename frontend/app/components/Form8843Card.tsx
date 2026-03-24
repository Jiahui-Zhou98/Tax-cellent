"use client";

import { useState } from "react";
import { type Form8843Data, generate8843, bundleForms } from "../lib/api";
import { SectionCard } from "./SectionCard";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function Form8843Card({ data }: { data: Form8843Data }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasCatchUp = data.catch_up_years && data.catch_up_years.length > 0;
  const allYears = hasCatchUp
    ? [data.tax_year, ...data.catch_up_years].sort((a, b) => a - b)
    : [data.tax_year];

  const mailInfo = data.has_income
    ? { city: "Philadelphia, PA 19255", deadline: "April 15", label: "Attach to 1040-NR" }
    : { city: "Austin, TX 73301", deadline: "June 15", label: "Standalone (no income)" };

  async function handleDownload() {
    setLoading(true);
    setError(null);
    try {
      if (hasCatchUp && allYears.length > 1) {
        const blob = await bundleForms(data, allYears);
        const nameSlug = data.last_name.toLowerCase() || "form";
        triggerDownload(blob, `f8843_bundle_${nameSlug}.pdf`);
      } else {
        const blob = await generate8843(data, data.tax_year);
        const nameSlug = data.last_name.toLowerCase() || "form";
        triggerDownload(blob, `f8843_${data.tax_year}_${nameSlug}.pdf`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SectionCard title="Form 8843 — Statement for Exempt Individuals" accent="#22d3ee">
      <div className="space-y-4">
        {/* Eligibility summary */}
        <div
          className="rounded-lg p-3 text-xs space-y-1"
          style={{ background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.15)" }}
        >
          <div className="flex items-center gap-2">
            <span style={{ color: "#22d3ee" }}>✓</span>
            <span className="text-slate-300 font-medium">You are required to file Form 8843</span>
          </div>
          <p className="text-slate-500 pl-5">
            All {data.visa_type} visa holders must file this statement even with zero US income.
            It is not a tax return — it is a residency exemption statement.
          </p>
        </div>

        {/* Key details grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-slate-600 block">Visa type</span>
            <span className="text-slate-300 font-mono">{data.visa_type}</span>
          </div>
          <div>
            <span className="text-slate-600 block">Tax year(s)</span>
            <span className="text-slate-300 font-mono">{allYears.join(", ")}</span>
          </div>
          {data.institution_name && (
            <div className="col-span-2">
              <span className="text-slate-600 block">Institution</span>
              <span className="text-slate-300">
                {data.institution_name}
                {data.institution_city ? `, ${data.institution_city}` : ""}
                {data.institution_state ? ` ${data.institution_state}` : ""}
              </span>
            </div>
          )}
          {data.exempt_prior_years.length > 0 && (
            <div className="col-span-2">
              <span className="text-slate-600 block">Prior exempt years (Line 7)</span>
              <span className="text-slate-300 font-mono">
                {data.exempt_prior_years.sort((a, b) => a - b).join(", ")}
              </span>
            </div>
          )}
        </div>

        {/* Mailing instructions */}
        <div
          className="rounded-lg p-3 text-xs space-y-1"
          style={{ background: "rgba(71,85,105,0.15)", border: "1px solid rgba(71,85,105,0.25)" }}
        >
          <p className="text-slate-400 font-medium">{mailInfo.label}</p>
          <p className="text-slate-500">
            Mail to:{" "}
            <span className="text-slate-300 font-mono">
              Department of the Treasury, Internal Revenue Service, {mailInfo.city}
            </span>
          </p>
          <p className="text-slate-500">
            Deadline: <span className="text-slate-300">{mailInfo.deadline}</span>
            &nbsp;·&nbsp;Form 8843 cannot be e-filed.
          </p>
        </div>

        {/* Catch-up note */}
        {hasCatchUp && (
          <div
            className="rounded-lg p-3 text-xs"
            style={{ background: "rgba(251,191,36,0.07)", border: "1px solid rgba(251,191,36,0.2)" }}
          >
            <span className="font-medium" style={{ color: "#fbbf24" }}>Catch-up filing</span>
            <p className="text-slate-500 mt-1">
              You have {allYears.length} forms to file (years: {allYears.join(", ")}).
              The download below bundles them into a single PDF with a cover sheet.
            </p>
          </div>
        )}

        {error && (
          <div
            className="rounded-lg p-3 text-xs text-red-400"
            style={{ background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.2)" }}
          >
            <span className="font-mono text-red-500 mr-2">ERROR</span>
            {error}
            <p className="text-slate-500 mt-1">
              The PDF template may not be available yet. Contact your DSO or file manually.
            </p>
          </div>
        )}

        <button
          onClick={handleDownload}
          disabled={loading}
          className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 flex items-center justify-center gap-2"
          style={
            loading
              ? { background: "rgba(34,211,238,0.1)", color: "#22d3ee", border: "1px solid rgba(34,211,238,0.3)" }
              : { background: "rgba(34,211,238,0.12)", color: "#22d3ee", border: "1px solid rgba(34,211,238,0.4)" }
          }
        >
          {loading ? (
            <>
              <span className="animate-spin text-base">⟳</span>
              Generating PDF…
            </>
          ) : (
            <>
              ↓ Download Form 8843{hasCatchUp ? " Bundle" : ""}
            </>
          )}
        </button>
      </div>
    </SectionCard>
  );
}
