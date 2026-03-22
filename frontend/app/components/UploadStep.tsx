"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument, type OCROutput } from "../lib/api";
import { card } from "../styles";

export function UploadStep({ onUploaded }: { onUploaded: (ocr: OCROutput) => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!files[0]) return;
      setLoading(true);
      setError(null);
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
    <div className="max-w-xl mx-auto space-y-5 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-white tracking-tight">
          Upload Tax Document
        </h2>
        <p className="text-slate-500 text-sm">
          Supported forms: W-2 · 1099-NEC · 1099-INT
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
                background: "rgba(34,211,238,0.05)",
                border: "1.5px dashed rgba(34,211,238,0.7)",
                boxShadow: "0 0 32px rgba(34,211,238,0.12)",
              }
            : loading
            ? { ...card, border: "1.5px dashed rgba(100,116,139,0.3)", opacity: 0.6 }
            : {
                ...card,
                border: "1.5px dashed rgba(100,116,139,0.3)",
              }
        }
      >
        <input {...getInputProps()} aria-label="Select tax document file" />

        {/* Corner accents */}
        {["top-3 left-3 border-t-2 border-l-2 rounded-tl",
          "top-3 right-3 border-t-2 border-r-2 rounded-tr",
          "bottom-3 left-3 border-b-2 border-l-2 rounded-bl",
          "bottom-3 right-3 border-b-2 border-r-2 rounded-br",
        ].map((cls, i) => (
          <div
            key={i}
            className={`absolute w-4 h-4 ${cls}`}
            style={{ borderColor: "rgba(34,211,238,0.3)" }}
          />
        ))}

        <div className="py-16 px-8 text-center">
          {loading ? (
            <div className="inline-block w-10 h-10 mb-5 rounded-full border-2 border-slate-700 border-t-cyan-400 animate-spin" />
          ) : (
            <div
              className="w-12 h-12 mx-auto mb-5 rounded-xl flex items-center justify-center"
              style={{
                background: "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.2)",
              }}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="rgba(34,211,238,0.8)"
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

          <p className="text-slate-300 font-medium">
            {loading
              ? "Extracting text from document…"
              : isDragActive
              ? "Release to upload"
              : "Drop a file here, or click to browse"}
          </p>
          <p className="text-slate-600 text-xs mt-2 font-mono">
            PDF · PNG · JPG · TIFF — MAX 20 MB
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded-xl p-4 text-sm text-red-400"
          style={{
            background: "rgba(127,29,29,0.2)",
            border: "1px solid rgba(239,68,68,0.2)",
          }}
        >
          <span className="font-mono text-red-500 mr-2">ERROR</span>
          {error}
        </div>
      )}

      {/* Privacy note */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl"
        style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.12)" }}
      >
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs flex-shrink-0"
          style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}
        >
          <span className="text-emerald-400">✦</span>
        </div>
        <p className="text-xs text-slate-500">
          <span className="text-emerald-400 font-semibold">Privacy first.</span>{" "}
          OCR and extraction always run locally. AI explanations use the provider you choose — local or cloud.
        </p>
      </div>
    </div>
  );
}
