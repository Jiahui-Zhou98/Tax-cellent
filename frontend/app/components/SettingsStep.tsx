"use client";

import { useState, useEffect } from "react";
import { checkHealth, type AnalysisPreferences, type HealthStatus } from "../lib/api";
import { inputStyle, glowBtn } from "../styles";
import { SectionCard } from "./SectionCard";

// SYNC: model lists must match PROVIDER_MODELS in backend/app/api/review.py
const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-5.2"],
  anthropic: ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
  gemini: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
};

const PROVIDER_INFO: Record<string, { label: string; note: string }> = {
  ollama: {
    label: "Local (Ollama)",
    note: "Free & private — runs on your machine. No data leaves your device.",
  },
  openai: {
    label: "ChatGPT / OpenAI",
    note: "Most accurate. Best for complex tax situations. Requires an API key.",
  },
  anthropic: {
    label: "Claude / Anthropic",
    note: "Strong reasoning. Excellent for nuanced explanations. Requires an API key.",
  },
  gemini: {
    label: "Gemini / Google",
    note: "Fast and capable. Good balance of speed and quality. Requires an API key.",
  },
};

export function SettingsStep({
  onAnalyze,
  onBack,
}: {
  onAnalyze: (preferences: AnalysisPreferences) => void;
  onBack: () => void;
}) {
  const [provider, setProvider] = useState<AnalysisPreferences["provider"]>("ollama");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    checkHealth().then(setHealth).catch(() => {});
  }, []);

  const isCloud = provider !== "ollama";
  const modelList = PROVIDER_MODELS[provider] ?? [];
  const providerStatus = health?.providers[provider];
  const isConfigured =
    provider === "ollama" ? providerStatus?.running : providerStatus?.configured;
  const canSubmit = !isCloud || isConfigured || !!apiKey;

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">AI Provider Settings</h2>
        <p className="text-slate-500 text-sm mt-1">
          Choose the model that will generate explanations in your tax report.
        </p>
      </div>

      <SectionCard title="AI Explanation Provider" accent="#22d3ee">
        <div className="space-y-4">
          {/* Provider selector */}
          <div>
            <label htmlFor="provider-select" className="text-xs text-slate-500 mb-1.5 block">
              Provider
            </label>
            <select
              id="provider-select"
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value as AnalysisPreferences["provider"]);
                setModel("");
                setApiKey("");
              }}
              style={inputStyle}
            >
              {(["ollama", "openai", "anthropic", "gemini"] as const).map((p) => {
                const st = health?.providers[p];
                const ok = p === "ollama" ? st?.running : st?.configured;
                const badge = health ? (ok ? " ✓" : " ✗") : "";
                return (
                  <option key={p} value={p} style={{ background: "#0d1424" }}>
                    {PROVIDER_INFO[p].label}{badge}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Configured status badge */}
          {health && (
            <div
              className={`text-xs px-2.5 py-1 rounded-full inline-flex items-center gap-1.5 ${
                isConfigured
                  ? "bg-emerald-900/40 text-emerald-400 border border-emerald-700/40"
                  : "bg-red-900/30 text-red-400 border border-red-700/30"
              }`}
            >
              <span>{isConfigured ? "●" : "○"}</span>
              {isConfigured
                ? provider === "ollama"
                  ? "Ollama running"
                  : "API key configured in backend"
                : provider === "ollama"
                ? "Ollama not running — start Ollama to use local models"
                : "API key not set — enter below or add to backend/.env"}
            </div>
          )}

          {/* Provider capability note */}
          <p className="text-xs text-slate-600">{PROVIDER_INFO[provider].note}</p>

          {/* API key input — cloud providers only */}
          {isCloud && (
            <div>
              <label htmlFor="api-key-input" className="text-xs text-slate-500 mb-1.5 block">
                API Key{" "}
                <span className="text-slate-700">(session-only, never stored)</span>
              </label>
              <input
                id="api-key-input"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  isConfigured
                    ? "Using key from backend/.env — paste here to override"
                    : `Paste your ${PROVIDER_INFO[provider].label} API key`
                }
                style={inputStyle}
                autoComplete="off"
              />
              {!isConfigured && !apiKey && (
                <p className="text-xs text-amber-500/80 mt-1">
                  No key found in backend — enter one above to continue.
                </p>
              )}
            </div>
          )}

          {/* Model picker: dropdown for cloud, text input for Ollama */}
          <div>
            <label htmlFor="model-input" className="text-xs text-slate-500 mb-1.5 block">
              Model
            </label>
            {modelList.length > 0 ? (
              <select
                id="model-input"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={inputStyle}
              >
                <option value="" style={{ background: "#0d1424" }}>
                  Default
                </option>
                {modelList.map((m) => (
                  <option key={m} value={m} style={{ background: "#0d1424" }}>
                    {m}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="model-input"
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="Optional override, e.g. qwen3:8b"
                style={inputStyle}
              />
            )}
          </div>

          <p className="text-xs text-slate-700">
            This only changes the AI explanations in the final report. Extraction,
            validation, and tax math are deterministic.
          </p>
        </div>
      </SectionCard>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="py-3.5 px-5 rounded-xl text-sm font-semibold transition-all"
          style={{
            background: "rgba(71,85,105,0.2)",
            border: "1px solid rgba(71,85,105,0.3)",
            color: "#94a3b8",
          }}
        >
          ← Back
        </button>
        <button
          onClick={() =>
            onAnalyze({
              provider,
              model: model || undefined,
              api_key: apiKey || undefined,
            })
          }
          disabled={!canSubmit}
          className="flex-1 py-3.5 rounded-xl text-white font-semibold text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: "#2563eb", ...glowBtn() }}
        >
          Calculate Tax Outcome →
        </button>
      </div>
    </div>
  );
}
