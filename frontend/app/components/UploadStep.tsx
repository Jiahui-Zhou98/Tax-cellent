"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument, type OCROutput } from "../lib/api";

const UPLOAD_HINTS = [
  "Extracting text from document…",
  "Running OCR pipeline…",
  "Identifying tax fields…",
];

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

  useEffect(() => {
    if (!loading) return;
    const cycle = setInterval(() => setHintIndex((i) => (i + 1) % UPLOAD_HINTS.length), 2500);
    return () => clearInterval(cycle);
  }, [loading]);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setLoading(true);
      setError(null);
      setHintIndex(0);
      try {
        const ocr = await uploadDocument(files[0]);
        onUploaded(ocr);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [onUploaded]
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
    <div className="space-y-5 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight" style={{ color: "var(--color-text-primary)" }}>
          Upload Tax Document
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Upload your W-2, 1099-NEC, or 1099-INT and we'll extract the fields automatically — then guide you through filing your 1040-NR and Form 8843.
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        aria-label="Upload tax document — drop a file here or click to browse"
        role="button"
        className="relative rounded-2xl cursor-pointer transition-all duration-300 overflow-hidden"
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

        <div className="py-14 px-8 text-center">
          {loading ? (
            <div
              className="inline-block w-10 h-10 mb-5 rounded-full border-2 animate-spin"
              style={{ borderColor: "var(--color-border)", borderTopColor: "var(--color-accent)" }}
            />
          ) : (
            <div
              className="w-12 h-12 mx-auto mb-5 rounded-xl flex items-center justify-center"
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
              ? UPLOAD_HINTS[hintIndex]
              : isDragActive
              ? "Release to upload"
              : "Drop your tax document here, or click to browse"}
          </p>
          <p className="text-xs mt-2 font-mono" style={{ color: "var(--color-text-secondary)" }}>
            {loading ? "\u00a0" : "W-2 · 1099-NEC · 1099-INT · PDF · PNG · JPG"}
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
          <span className="font-mono mr-2">ERROR</span>
          {error}
        </div>
      )}

      {/* Zero-income path shortcut */}
      {onZeroIncome && (
        <button
          onClick={onZeroIncome}
          disabled={loading}
          className="w-full py-3 rounded-xl text-sm font-medium transition-all disabled:opacity-40 flex items-center justify-center gap-2"
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
        <div className="flex items-center gap-3 mb-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
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
            <p className="text-sm font-semibold" style={{ color: "var(--color-success)" }}>Your Data Stays on Your Computer</p>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>All tax processing happens locally — nothing is uploaded to any server.</p>
          </div>
        </div>
        <div className="space-y-1.5 pl-12">
          {[
            "Document text extraction runs on your machine",
            "Tax forms are filled and generated locally",
            "No account, no sign-up, no data stored anywhere",
          ].map((item) => (
            <div key={item} className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              <span className="flex-shrink-0" style={{ color: "var(--color-success)" }}>✓</span>
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
