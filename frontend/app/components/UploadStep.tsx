"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument, type OCROutput } from "../lib/api";
import { inputStyle } from "../styles";

const UPLOAD_HINTS = [
  "Extracting text from document\u2026",
  "Running OCR pipeline\u2026",
  "Identifying tax fields\u2026",
];

const AI_UPLOAD_HINTS = [
  "Extracting text from document\u2026",
  "Running AI verification with Gemini\u2026",
  "Cross-checking extracted values\u2026",
  "Merging results for best accuracy\u2026",
];

const AI_KEY_STORAGE = "tax_ai_gemini_key";
// Also check the key stored by SettingsStep (different sessionStorage key)
const SETTINGS_KEY_STORAGE = "tax_api_key_gemini";

export function UploadStep({
  onUploaded,
  onZeroIncome,
}: {
  onUploaded: (ocr: OCROutput) => void;
  onZeroIncome?: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hintIndex, setHintIndex] = useState(0);
  const [aiKey, setAiKey] = useState("");
  const [showAiBanner, setShowAiBanner] = useState(true);

  // Load saved key from sessionStorage on mount — check both Upload and Settings keys
  useEffect(() => {
    const saved =
      sessionStorage.getItem(AI_KEY_STORAGE) || sessionStorage.getItem(SETTINGS_KEY_STORAGE);
    if (saved) {
      setAiKey(saved);
      // Sync to Upload key so it persists for next time
      sessionStorage.setItem(AI_KEY_STORAGE, saved);
    }
  }, []);

  const hints = aiKey ? AI_UPLOAD_HINTS : UPLOAD_HINTS;

  useEffect(() => {
    if (!loading) return;
    const cycle = setInterval(() => setHintIndex((i) => (i + 1) % hints.length), 2500);
    return () => clearInterval(cycle);
  }, [loading, hints.length]);

  const saveAiKey = () => {
    if (aiKey.trim()) {
      sessionStorage.setItem(AI_KEY_STORAGE, aiKey.trim());
    } else {
      sessionStorage.removeItem(AI_KEY_STORAGE);
    }
  };

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setLoading(true);
      setError(null);
      setHintIndex(0);
      try {
        const ocr = await uploadDocument(
          files[0],
          aiKey.trim() || undefined,
          aiKey.trim() ? "gemini-2.0-flash" : undefined
        );
        onUploaded(ocr);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [onUploaded, aiKey]
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
    <div className="animate-fade-in space-y-5">
      <div className="space-y-1">
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--color-text-primary)" }}
        >
          Upload Tax Document
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Upload your W-2, 1099-NEC, or 1099-INT and we'll extract the fields automatically — then
          guide you through filing your 1040-NR and Form 8843.
        </p>
      </div>

      {/* AI Extraction banner */}
      {showAiBanner && (
        <div
          className="rounded-xl p-4"
          style={{
            background: "rgba(99,102,241,0.06)",
            border: "1px solid rgba(99,102,241,0.2)",
          }}
        >
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-medium text-indigo-400">AI-Powered Extraction</p>
            <button
              onClick={() => setShowAiBanner(false)}
              className="cursor-pointer px-2 py-2 text-xs text-slate-600 hover:text-slate-400"
            >
              dismiss
            </button>
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Enter your Gemini API key for dramatically more accurate field extraction. Your document
            is sent to Google for processing. Key saved for this session only.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder="Gemini API key"
              value={aiKey}
              onChange={(e) => setAiKey(e.target.value)}
              onBlur={saveAiKey}
              style={{ ...inputStyle, fontSize: "0.75rem" }}
              className="flex-1"
            />
            {aiKey && (
              <span className="self-center text-xs whitespace-nowrap text-emerald-500">Saved</span>
            )}
          </div>
        </div>
      )}

      {/* Dropzone */}
      <div
        {...getRootProps()}
        aria-label="Upload tax document, drop a file here or click to browse"
        role="button"
        className="relative cursor-pointer overflow-hidden rounded-2xl transition-all duration-300"
        style={
          isDragActive
            ? {
                background: "rgba(0,113,227,0.05)",
                border: "1.5px dashed var(--color-accent)",
                boxShadow: "0 0 24px rgba(0,113,227,0.08)",
              }
            : loading
              ? {
                  background: "var(--color-bg)",
                  border: "1.5px dashed var(--color-border)",
                  opacity: 0.7,
                }
              : {
                  background: "var(--color-surface)",
                  border: "1.5px dashed var(--color-border)",
                }
        }
      >
        <input {...getInputProps()} aria-label="Select tax document file" />

        <div className="px-8 py-14 text-center">
          {loading ? (
            <div
              className="mb-5 inline-block h-10 w-10 animate-spin rounded-full border-2"
              style={{ borderColor: "var(--color-border)", borderTopColor: "var(--color-accent)" }}
            />
          ) : (
            <div
              className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-xl"
              style={{
                background: "rgba(0,113,227,0.06)",
                border: "1px solid rgba(0,113,227,0.15)",
              }}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--color-accent)"
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

          <p className="font-medium" style={{ color: "var(--color-text-primary)" }}>
            {loading
              ? hints[hintIndex]
              : isDragActive
                ? "Release to upload"
                : "Drop your tax document here, or click to browse"}
          </p>
          <p className="mt-2 font-mono text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {loading ? "\u00a0" : "W-2 · 1099-NEC · 1099-INT · 1042-S · PDF · PNG · JPG"}
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded-xl p-4 text-sm"
          style={{
            background: "rgba(255,59,48,0.06)",
            border: "1px solid rgba(255,59,48,0.2)",
            color: "var(--color-danger)",
          }}
        >
          <span className="mr-2 font-mono">ERROR</span>
          {error}
        </div>
      )}

      {/* Zero-income path shortcut */}
      {onZeroIncome && (
        <button
          onClick={onZeroIncome}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-all disabled:opacity-40"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-secondary)",
            cursor: loading ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (!loading) {
              e.currentTarget.style.borderColor = "var(--color-accent)";
              e.currentTarget.style.color = "var(--color-accent)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--color-border)";
            e.currentTarget.style.color = "var(--color-text-secondary)";
          }}
        >
          <span style={{ color: "var(--color-accent)" }}>⇒</span>
          No income — just need Form 8843
        </button>
      )}

      {/* Privacy feature card */}
      <div
        className="rounded-xl p-5"
        style={{ background: "rgba(52,199,89,0.05)", border: "1px solid rgba(52,199,89,0.15)" }}
      >
        <div className="mb-3 flex items-center gap-3">
          <div
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full"
            style={{ background: "rgba(52,199,89,0.1)", border: "1px solid rgba(52,199,89,0.2)" }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--color-success)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--color-success)" }}>
              {aiKey ? "AI-Enhanced Processing" : "Your Data Stays on Your Computer"}
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {aiKey
                ? "Your document is sent to Gemini for improved accuracy. Key stored in session only."
                : "All tax processing happens locally — nothing is uploaded to any server."}
            </p>
          </div>
        </div>
        <div className="space-y-1.5 pl-12">
          {(aiKey
            ? [
                "OCR extraction runs locally as baseline",
                "Gemini Vision verifies each field value",
                "Disagreements flagged for your review",
              ]
            : [
                "Document text extraction runs on your machine",
                "Tax forms are filled and generated locally",
                "No account, no sign-up, no data stored anywhere",
              ]
          ).map((item) => (
            <div
              key={item}
              className="flex items-center gap-2 text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              <span className="flex-shrink-0" style={{ color: "var(--color-success)" }}>
                ✓
              </span>
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
