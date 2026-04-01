"use client";

import { useState } from "react";
import { downloadTaxPackage } from "../lib/api";

interface ExportButtonProps {
  documentId: string;
}

/**
 * ExportButton — downloads the complete tax filing package (cover sheet +
 * Form 1040NR + optional Form 8843) as a single bundled PDF.
 *
 * Includes a one-time acknowledgment checkbox before download is enabled.
 * Shown only on the CalculationLedgerStep when the session has a completed
 * tax report. The button is disabled while the download is in flight and
 * re-enables automatically on error so the user can retry.
 */
export function ExportButton({ documentId }: ExportButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);

  const handleDownload = async () => {
    if (!acknowledged) return;
    setLoading(true);
    setError(null);
    try {
      const blob = await downloadTaxPackage(documentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const taxYear = new Date().getFullYear() - 1;
      a.download = `tax-package-${taxYear}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Acknowledgment gate */}
      <label
        className="flex items-start gap-2.5 cursor-pointer select-none"
        style={{
          background: "rgba(254,243,199,0.08)",
          border: "1px solid rgba(251,191,36,0.25)",
          borderRadius: "0.75rem",
          padding: "0.75rem 1rem",
        }}
      >
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(e) => setAcknowledged(e.target.checked)}
          className="mt-0.5 accent-amber-500"
        />
        <span className="text-xs text-slate-400 leading-relaxed">
          I understand Tax-cellent is a filing assistance tool, not professional
          tax advice. I will review all pre-filled values for accuracy before
          signing and mailing.
        </span>
      </label>

      <button
        onClick={handleDownload}
        disabled={loading || !acknowledged}
        className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
        style={{
          background:
            loading || !acknowledged
              ? "rgba(99,102,241,0.08)"
              : "rgba(99,102,241,0.18)",
          border: "1px solid rgba(99,102,241,0.45)",
          color: loading || !acknowledged ? "#64748b" : "#a5b4fc",
          cursor: loading || !acknowledged ? "not-allowed" : "pointer",
          opacity: acknowledged ? 1 : 0.6,
        }}
      >
        {loading ? (
          <>
            <span
              className="inline-block w-4 h-4 rounded-full border-2 animate-spin"
              style={{ borderColor: "#818cf8 transparent transparent transparent" }}
            />
            Generating PDF...
          </>
        ) : (
          <>
            <span>{acknowledged ? "\u2193" : "\u26A0"}</span>
            {acknowledged ? "Download Tax Filing Package" : "Check the box above to enable download"}
          </>
        )}
      </button>

      {error && (
        <p className="text-xs text-red-400 text-center px-2">{error}</p>
      )}

      <p className="text-xs text-slate-600 text-center">
        Includes Form 1040-NR · Form 8843 · Filing Instructions
      </p>
    </div>
  );
}
