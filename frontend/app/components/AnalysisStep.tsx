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
  onBack,
}: {
  documentId: string;
  preferences: AnalysisPreferences;
  onComplete: (report: TaxReport) => void;
  onBack: () => void;
}) {
  const [hintIndex, setHintIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setError(null);

    analyzeDocument(documentId, preferences)
      .then((report) => {
        if (!cancelled) onComplete(report);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });

    const cycle = setInterval(() => {
      if (!cancelled) setHintIndex((i) => (i + 1) % ANALYSIS_HINTS.length);
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(cycle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, preferences, retryCount]);

  const providerLabel =
    ANALYSIS_PROVIDER_OPTIONS.find((o) => o.value === preferences.provider)?.label ??
    preferences.provider;

  return (
    <div className="animate-fade-in space-y-8 text-center">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--color-text-primary)" }}
        >
          Calculating…
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Applying 2025 IRS rules with {providerLabel} for the explanation layer.
        </p>
      </div>

      {/* Spinner */}
      <div className="flex justify-center" role="status" aria-label="Analyzing document">
        <div
          className="h-16 w-16 animate-spin rounded-full border-2"
          style={{
            borderColor: "rgba(0,113,227,0.15)",
            borderTopColor: "var(--color-accent)",
          }}
        />
      </div>

      {/* Rotating hint */}
      <p
        className="min-h-[1.5rem] font-mono text-sm transition-all"
        aria-live="polite"
        aria-atomic="true"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {ANALYSIS_HINTS[hintIndex]}
      </p>

      {error && (
        <div className="space-y-3">
          <div
            className="rounded-xl p-4 text-left text-sm"
            style={{
              background: "rgba(255,59,48,0.06)",
              border: "1px solid rgba(255,59,48,0.2)",
              color: "var(--color-danger)",
            }}
          >
            <span className="mr-2 font-mono">ERROR</span>
            {error}
          </div>
          <div className="flex justify-center gap-3">
            <button
              onClick={onBack}
              className="rounded-xl px-5 py-2.5 text-sm font-semibold transition-all"
              style={{
                background: "transparent",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-primary)",
                cursor: "pointer",
              }}
            >
              ← Back to Settings
            </button>
            <button
              onClick={() => {
                setHintIndex(0);
                setRetryCount((c) => c + 1);
              }}
              className="rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all"
              style={{ background: "var(--color-accent)", cursor: "pointer" }}
            >
              ↺ Retry
            </button>
          </div>
        </div>
      )}

      <p
        className="font-mono text-xs"
        style={{ color: "var(--color-text-secondary)", opacity: 0.7 }}
      >
        {preferences.provider === "ollama"
          ? "Running locally — this may take 30–90 seconds"
          : "Calling cloud API — usually 5–15 seconds"}
      </p>
    </div>
  );
}
