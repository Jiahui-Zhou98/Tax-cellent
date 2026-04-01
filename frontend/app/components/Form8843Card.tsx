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
    <SectionCard title="Form 8843 — Statement for Exempt Individuals" variant="default">
      <div className="space-y-4">
        {/* Eligibility summary */}
        <div
          className="rounded-lg p-3 text-xs space-y-1"
          style={{ background: "rgba(0,113,227,0.06)", border: "1px solid rgba(0,113,227,0.15)" }}
        >
          <div className="flex items-center gap-2">
            <span style={{ color: "var(--color-accent)" }}>✓</span>
            <span className="font-medium" style={{ color: "var(--color-text-primary)" }}>You are required to file Form 8843</span>
          </div>
          <p className="pl-5" style={{ color: "var(--color-text-secondary)" }}>
            All {data.visa_type} visa holders must file this statement even with zero US income.
            It is not a tax return — it is a residency exemption statement.
          </p>
        </div>

        {/* Key details grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="block" style={{ color: "var(--color-text-secondary)" }}>Visa type</span>
            <span className="font-mono" style={{ color: "var(--color-text-primary)" }}>{data.visa_type}</span>
          </div>
          <div>
            <span className="block" style={{ color: "var(--color-text-secondary)" }}>Tax year(s)</span>
            <span className="font-mono" style={{ color: "var(--color-text-primary)" }}>{allYears.join(", ")}</span>
          </div>
          {data.institution_name && (
            <div className="col-span-2">
              <span className="block" style={{ color: "var(--color-text-secondary)" }}>Institution</span>
              <span style={{ color: "var(--color-text-primary)" }}>
                {data.institution_name}
                {data.institution_city ? `, ${data.institution_city}` : ""}
                {data.institution_state ? ` ${data.institution_state}` : ""}
              </span>
            </div>
          )}
          {data.exempt_prior_years.length > 0 && (
            <div className="col-span-2">
              <span className="block" style={{ color: "var(--color-text-secondary)" }}>Prior exempt years (Line 7)</span>
              <span className="font-mono" style={{ color: "var(--color-text-primary)" }}>
                {data.exempt_prior_years.sort((a, b) => a - b).join(", ")}
              </span>
            </div>
          )}
        </div>

        {/* Mailing instructions */}
        <div
          className="rounded-lg p-3 text-xs space-y-1"
          style={{ background: "var(--color-bg)", border: "1px solid var(--color-border)" }}
        >
          <p className="font-medium" style={{ color: "var(--color-text-primary)" }}>{mailInfo.label}</p>
          <p style={{ color: "var(--color-text-secondary)" }}>
            Mail to:{" "}
            <span className="font-mono" style={{ color: "var(--color-text-primary)" }}>
              Department of the Treasury, Internal Revenue Service, {mailInfo.city}
            </span>
          </p>
          <p style={{ color: "var(--color-text-secondary)" }}>
            Deadline: <span style={{ color: "var(--color-text-primary)" }}>{mailInfo.deadline}</span>
            &nbsp;·&nbsp;Form 8843 cannot be e-filed.
          </p>
        </div>

        {/* Catch-up note */}
        {hasCatchUp && (
          <div
            className="rounded-lg p-3 text-xs"
            style={{ background: "rgba(255,159,10,0.06)", border: "1px solid rgba(255,159,10,0.2)" }}
          >
            <span className="font-medium" style={{ color: "var(--color-warning)" }}>Catch-up filing</span>
            <p className="mt-1" style={{ color: "var(--color-text-secondary)" }}>
              You have {allYears.length} forms to file (years: {allYears.join(", ")}).
              The download below bundles them into a single PDF with a cover sheet.
            </p>
          </div>
        )}

        {error && (
          <div
            className="rounded-lg p-3 text-xs"
            style={{
              background: "rgba(255,59,48,0.06)",
              border: "1px solid rgba(255,59,48,0.2)",
              color: "var(--color-danger)",
            }}
          >
            <span className="font-mono mr-2">ERROR</span>
            {error}
            <p className="mt-1" style={{ color: "var(--color-text-secondary)" }}>
              The PDF template may not be available yet. Contact your DSO or file manually.
            </p>
          </div>
        )}

        <button
          onClick={handleDownload}
          disabled={loading}
          className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 flex items-center justify-center gap-2"
          style={{
            background: loading ? "#AEAEB2" : "var(--color-accent)",
            color: "#FFFFFF",
            border: "none",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? (
            <>
              <span className="animate-spin text-base">⟳</span>
              Generating PDF…
            </>
          ) : (
            <>↓ Download Form 8843{hasCatchUp ? " Bundle" : ""}</>
          )}
        </button>
      </div>
    </SectionCard>
  );
}
