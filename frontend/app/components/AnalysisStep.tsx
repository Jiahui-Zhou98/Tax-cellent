"use client";

import React, { useState } from "react";
import { analyzeDocument, type AnalysisPreferences, type TaxReport } from "../lib/api";
import { ANALYSIS_PROVIDER_OPTIONS } from "../lib/providers";

const ANALYSIS_HINTS = [
  "Applying 2025 IRS tax brackets to your taxable income…",
  "Checking FICA exemption eligibility under IRC §3121(b)(19)…",
  "Calculating your estimated federal balance…",
];

export function AnalysisStep({
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

  const providerLabel = ANALYSIS_PROVIDER_OPTIONS.find((o) => o.value === preferences.provider)?.label ?? preferences.provider;

  return (
    <div className="space-y-8 animate-fade-in text-center">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Calculating…</h2>
        <p className="text-slate-500 text-sm mt-1">
          Applying 2025 IRS rules with {providerLabel} for the explanation layer.
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
        {preferences.provider === "ollama"
          ? "Running locally — this may take 30–90 seconds"
          : "Calling cloud API — usually 5–15 seconds"}
      </p>
    </div>
  );
}
