"use client";

import { useState } from "react";
import { type AnalysisPreferences } from "../lib/api";
import { inputStyle, glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";
import { ANALYSIS_PROVIDER_OPTIONS } from "../lib/providers";

export function SettingsStep({
  onAnalyze,
  onBack,
}: {
  onAnalyze: (preferences: AnalysisPreferences) => void;
  onBack: () => void;
}) {
  const [provider, setProvider] = useState<AnalysisPreferences["provider"]>("ollama");
  const [model, setModel] = useState("");

  const selectedProvider = ANALYSIS_PROVIDER_OPTIONS.find((o) => o.value === provider) ?? ANALYSIS_PROVIDER_OPTIONS[0];

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">AI Provider Settings</h2>
        <p className="text-slate-500 text-sm mt-1">
          Choose the model that will generate explanations in your tax report.
        </p>
      </div>

      <SectionCard title="AI Explanation Provider" accent="#22d3ee">
        <div className="space-y-3">
          <div>
            <p className="text-xs text-slate-500 mb-1.5">
              Choose the model provider for the report explanations
            </p>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as AnalysisPreferences["provider"])}
              style={inputStyle}
            >
              {ANALYSIS_PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value} style={{ background: "#0d1424" }}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-slate-600">{selectedProvider.hint}</p>
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Optional model override</p>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={selectedProvider.placeholder}
              style={inputStyle}
            />
          </div>
          <p className="text-xs text-slate-700">
            This only changes the AI explanations in the final report. Extraction, validation, and tax math stay on the current pipeline.
          </p>
        </div>
      </SectionCard>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="py-3.5 px-5 rounded-xl text-sm font-semibold transition-all"
          style={{ background: "rgba(71,85,105,0.2)", border: "1px solid rgba(71,85,105,0.3)", color: "#94a3b8" }}
        >
          ← Back
        </button>
        <button
          onClick={() => onAnalyze({ provider, model: model.trim() || undefined })}
          className="flex-1 py-3.5 rounded-xl text-white font-semibold text-sm transition-all"
          style={{ background: "#2563eb", ...glowBtn() }}
        >
          Calculate Tax Outcome →
        </button>
      </div>
    </div>
  );
}
