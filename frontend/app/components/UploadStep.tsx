"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument, type OCROutput } from "../lib/api";
import { card, inputStyle } from "../styles";

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
    const saved = sessionStorage.getItem(AI_KEY_STORAGE)
      || sessionStorage.getItem(SETTINGS_KEY_STORAGE);
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
          aiKey.trim() ? "gemini-2.0-flash" : undefined,
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
    <div className="space-y-5 animate-fade-in">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-white tracking-tight">
          Upload Tax Document
        </h2>
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
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-indigo-400">
              AI-Powered Extraction
            </p>
            <button
              onClick={() => setShowAiBanner(false)}
              className="text-xs text-slate-600 hover:text-slate-400"
            >
              dismiss
            </button>
          </div>
          <p className="text-xs text-slate-500 mb-3">
            Enter your Gemini API key for dramatically more accurate field extraction.
            Your document is sent to Google for processing. Key saved for this session only.
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
              <span className="text-xs text-emerald-500 self-center whitespace-nowrap">
                Saved
              </span>
            )}
          </div>
        </div>
      )}

      {/* Dropzone */}
      <div
        {...getRootProps()}
        aria-label="Upload tax document, drop a file here or click to browse"
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
            ? { ...card, border: "1.5px dashed rgba(100,116,139,0.3)", opacity: 0.7 }
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

        <div className="py-14 px-8 text-center">
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
              ? hints[hintIndex]
              : isDragActive
              ? "Release to upload"
              : "Drop your tax document here, or click to browse"}
          </p>
          <p className="text-slate-600 text-xs mt-2 font-mono">
            {loading ? "\u00a0" : "W-2 \u00b7 1099-NEC \u00b7 1099-INT \u00b7 1042-S \u00b7 PDF \u00b7 PNG"}
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

      {/* Zero-income path shortcut */}
      {onZeroIncome && (
        <button
          onClick={onZeroIncome}
          disabled={loading}
          className="w-full py-3 rounded-xl text-sm font-medium transition-all disabled:opacity-40 flex items-center justify-center gap-2"
          style={{
            background: "rgba(34,211,238,0.05)",
            border: "1px solid rgba(34,211,238,0.2)",
            color: "#94a3b8",
          }}
        >
          <span style={{ color: "#22d3ee" }}>{"\u21D2"}</span>
          No income, just need Form 8843 {"\u2192"}
        </button>
      )}

      {/* Privacy feature card */}
      <div
        className="rounded-xl p-5"
        style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.12)" }}
      >
        <div className="flex items-center gap-3 mb-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#34d399"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-400">
              {aiKey ? "AI-Enhanced Processing" : "100% On-Device Processing"}
            </p>
            <p className="text-xs text-slate-500">
              {aiKey
                ? "Your document is sent to Gemini for improved accuracy. Key stored in session only."
                : "Your tax data never leaves your computer."}
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
                "OCR and field extraction run locally",
                "No document is uploaded to the cloud",
                "AI explanations use the provider you choose",
              ]
          ).map((item) => (
            <div key={item} className="flex items-center gap-2 text-xs text-slate-500">
              <span className="text-emerald-500 flex-shrink-0">{"\u2713"}</span>
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
