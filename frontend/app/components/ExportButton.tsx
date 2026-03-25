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
 * Shown only on the CalculationLedgerStep when the session has a completed
 * tax report. The button is disabled while the download is in flight and
 * re-enables automatically on error so the user can retry.
 */
export function ExportButton({ documentId }: ExportButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setLoading(true);
    setError(null);
    try {
      const blob = await downloadTaxPackage(documentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tax-package-2024.pdf";
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
    <div className="space-y-2">
      <button
        onClick={handleDownload}
        disabled={loading}
        className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
        style={{
          background: loading
            ? "rgba(99,102,241,0.12)"
            : "rgba(99,102,241,0.18)",
          border: "1px solid rgba(99,102,241,0.45)",
          color: loading ? "#818cf8" : "#a5b4fc",
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? (
          <>
            <span
              className="inline-block w-4 h-4 rounded-full border-2 animate-spin"
              style={{ borderColor: "#818cf8 transparent transparent transparent" }}
            />
            Generating PDF…
          </>
        ) : (
          <>
            <span>↓</span>
            Download Tax Filing Package
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
