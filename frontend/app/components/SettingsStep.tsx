"use client";

import { useState, useEffect } from "react";
import {
  checkHealth,
  getProviderModels,
  type AnalysisPreferences,
  type HealthStatus,
} from "../lib/api";
import { inputStyle } from "../styles";
import { SectionCard } from "./SectionCard";

// Fallback model lists — used if the backend endpoint is unreachable.
// The backend is the single source of truth (app/constants/models.py).
// These fallbacks prevent a blank picker when the backend is temporarily down.
const FALLBACK_PROVIDER_MODELS: Record<string, string[]> = {
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

const SESSION_KEY = (provider: string) => `tax_api_key_${provider}`;

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
  const [remember, setRemember] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [providerModels, setProviderModels] =
    useState<Record<string, string[]>>(FALLBACK_PROVIDER_MODELS);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => {});
    getProviderModels().then((models) => {
      if (models) setProviderModels(models);
    });
  }, []);

  function handleProviderChange(next: AnalysisPreferences["provider"]) {
    setProvider(next);
    setModel("");
    const stored =
      next !== "ollama"
        ? typeof sessionStorage !== "undefined"
          ? sessionStorage.getItem(SESSION_KEY(next))
          : null
        : null;
    setApiKey(stored ?? "");
    setRemember(!!stored);
  }

  function handleAnalyze() {
    if (provider !== "ollama") {
      try {
        if (remember && apiKey) {
          sessionStorage.setItem(SESSION_KEY(provider), apiKey);
        } else {
          sessionStorage.removeItem(SESSION_KEY(provider));
        }
      } catch {
        // sessionStorage unavailable (private browsing, storage quota) — proceed without saving
      }
    }
    onAnalyze({
      provider,
      model: model || undefined,
      api_key: apiKey || undefined,
    });
  }

  const isCloud = provider !== "ollama";
  const modelList = providerModels[provider] ?? [];
  const providerStatus = health?.providers[provider];
  const isConfigured = provider === "ollama" ? providerStatus?.running : providerStatus?.configured;
  const canSubmit = !isCloud || isConfigured || !!apiKey;

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--color-text-primary)" }}
        >
          AI Provider Settings
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Choose the model that will generate explanations in your tax report.
        </p>
      </div>

      <SectionCard title="AI Explanation Provider" variant="default">
        <div className="space-y-4">
          {/* Provider selector */}
          <div>
            <label
              htmlFor="provider-select"
              className="mb-1.5 block text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Provider
            </label>
            <select
              id="provider-select"
              value={provider}
              onChange={(e) =>
                handleProviderChange(e.target.value as AnalysisPreferences["provider"])
              }
              style={inputStyle}
            >
              {(["ollama", "openai", "anthropic", "gemini"] as const).map((p) => {
                const st = health?.providers[p];
                const ok = p === "ollama" ? st?.running : st?.configured;
                const badge = health ? (ok ? " ✓" : " ✗") : "";
                return (
                  <option key={p} value={p}>
                    {PROVIDER_INFO[p].label}
                    {badge}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Configured status badge */}
          {health && (
            <div
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
              style={
                isConfigured
                  ? {
                      background: "rgba(52,199,89,0.08)",
                      color: "var(--color-success)",
                      border: "1px solid rgba(52,199,89,0.25)",
                    }
                  : {
                      background: "rgba(255,59,48,0.06)",
                      color: "var(--color-danger)",
                      border: "1px solid rgba(255,59,48,0.2)",
                    }
              }
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
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {PROVIDER_INFO[provider].note}
          </p>

          {/* API key input — cloud providers only */}
          {isCloud && (
            <div className="space-y-2">
              <label
                htmlFor="api-key-input"
                className="mb-1.5 block text-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                API Key{" "}
                <span style={{ opacity: 0.7 }}>(session-only, never stored server-side)</span>
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
                <p className="text-xs" style={{ color: "var(--color-warning)" }}>
                  No key found in backend — enter one above to continue.
                </p>
              )}
              {/* Session persistence opt-in */}
              <label className="flex cursor-pointer items-center gap-2 select-none">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  style={{ accentColor: "var(--color-accent)" }}
                  aria-label="Remember API key for this browser session"
                />
                <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  Remember for this session{" "}
                  <span style={{ opacity: 0.7 }}>(clears when tab closes)</span>
                </span>
              </label>
            </div>
          )}

          {/* Model picker: dropdown for cloud, text input for Ollama */}
          <div>
            <label
              htmlFor="model-input"
              className="mb-1.5 block text-xs"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Model
            </label>
            {modelList.length > 0 ? (
              <select
                id="model-input"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={inputStyle}
              >
                <option value="">Default</option>
                {modelList.map((m) => (
                  <option key={m} value={m}>
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

          <p className="text-xs" style={{ color: "var(--color-text-secondary)", opacity: 0.7 }}>
            This only changes the AI explanations in the final report. Extraction, validation, and
            tax math are deterministic.
          </p>
        </div>
      </SectionCard>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="rounded-xl px-5 py-3.5 text-sm font-semibold transition-all"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-primary)",
            cursor: "pointer",
          }}
        >
          ← Back
        </button>
        <button
          onClick={handleAnalyze}
          disabled={!canSubmit}
          className="flex-1 rounded-xl py-3.5 text-sm font-semibold text-white transition-all disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            background: "var(--color-accent)",
            cursor: canSubmit ? "pointer" : "not-allowed",
          }}
        >
          Calculate Tax Outcome →
        </button>
      </div>
    </div>
  );
}
