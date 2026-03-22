"use client";

import { type ValidationOutput } from "../lib/api";
import { glowBtn } from "../styles";

export function ValidationStep({
  validation,
  onNext,
  onBack,
}: {
  validation: ValidationOutput;
  onNext: () => void;
  onBack: () => void;
}) {
  const statusCfg = {
    ok:      { label: "PASS", icon: "✓", color: "#34d399", bg: "rgba(52,211,153,0.06)", bd: "rgba(52,211,153,0.2)" },
    warning: { label: "WARN", icon: "!", color: "#fbbf24", bg: "rgba(251,191,36,0.06)", bd: "rgba(251,191,36,0.2)" },
    error:   { label: "FAIL", icon: "✕", color: "#f87171", bg: "rgba(248,113,113,0.06)", bd: "rgba(248,113,113,0.2)" },
  };
  const cfg = statusCfg[validation.status as keyof typeof statusCfg] ?? statusCfg.warning;

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Validation Results</h2>
        <p className="text-slate-500 text-sm mt-1">
          Rule checks passed. Ready to configure your AI provider.
        </p>
      </div>

      {/* Status badge */}
      <div
        className="flex items-center gap-3 px-4 py-3.5 rounded-xl"
        style={{ background: cfg.bg, border: `1px solid ${cfg.bd}` }}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
          style={{ background: cfg.bg, border: `1.5px solid ${cfg.bd}`, color: cfg.color }}
        >
          {cfg.icon}
        </div>
        <div>
          <p className="font-mono font-bold text-sm" style={{ color: cfg.color }}>
            {cfg.label}
          </p>
          <p className="text-xs text-slate-500">
            {validation.issues.length === 0
              ? "All checks passed"
              : `${validation.issues.length} issue${validation.issues.length !== 1 ? "s" : ""} found`}
          </p>
        </div>
      </div>

      {/* Issues */}
      {validation.issues.length > 0 && (
        <div className="space-y-2">
          {validation.issues.map((issue, i) => (
            <div
              key={i}
              className="flex gap-3 px-4 py-3 rounded-xl"
              style={
                issue.severity === "error"
                  ? { background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.15)" }
                  : { background: "rgba(120,53,15,0.15)", border: "1px solid rgba(251,191,36,0.15)" }
              }
            >
              <span
                className="font-mono text-xs font-bold flex-shrink-0 mt-0.5"
                style={{ color: issue.severity === "error" ? "#f87171" : "#fbbf24" }}
              >
                {issue.severity === "error" ? "ERR" : "WRN"}
              </span>
              <div>
                <p className="text-sm text-slate-200">{issue.message}</p>
                <p className="text-xs font-mono text-slate-600 mt-0.5">
                  {issue.field} · {issue.type}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="py-3.5 px-5 rounded-xl text-sm font-semibold transition-all"
          style={{ background: "rgba(71,85,105,0.2)", border: "1px solid rgba(71,85,105,0.3)", color: "#94a3b8" }}
        >
          ← Back
        </button>
        <button
          onClick={onNext}
          className="flex-1 py-3.5 rounded-xl text-white font-semibold text-sm transition-all"
          style={{ background: "#2563eb", ...glowBtn() }}
        >
          Choose AI Provider →
        </button>
      </div>
    </div>
  );
}
