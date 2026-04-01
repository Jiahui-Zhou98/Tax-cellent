"use client";

import { type ValidationOutput } from "../lib/api";

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
    ok: {
      label: "PASS",
      icon: "✓",
      color: "var(--color-success)",
      bg: "rgba(52,199,89,0.08)",
      bd: "rgba(52,199,89,0.25)",
    },
    warning: {
      label: "WARN",
      icon: "!",
      color: "var(--color-warning)",
      bg: "rgba(255,159,10,0.08)",
      bd: "rgba(255,159,10,0.25)",
    },
    error: {
      label: "FAIL",
      icon: "✕",
      color: "var(--color-danger)",
      bg: "rgba(255,59,48,0.08)",
      bd: "rgba(255,59,48,0.25)",
    },
  };
  const cfg = statusCfg[validation.status as keyof typeof statusCfg] ?? statusCfg.warning;

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--color-text-primary)" }}
        >
          Validation Results
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Rule checks passed. Ready to configure your AI provider.
        </p>
      </div>

      {/* Status badge */}
      <div
        className="flex items-center gap-3 rounded-xl px-4 py-3.5"
        style={{ background: cfg.bg, border: `1px solid ${cfg.bd}` }}
      >
        <div
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold"
          style={{ background: cfg.bg, border: `1.5px solid ${cfg.bd}`, color: cfg.color }}
        >
          {cfg.icon}
        </div>
        <div>
          <p className="font-mono text-sm font-bold" style={{ color: cfg.color }}>
            {cfg.label}
          </p>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
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
              className="flex gap-3 rounded-xl px-4 py-3"
              style={
                issue.severity === "error"
                  ? { background: "rgba(255,59,48,0.06)", border: "1px solid rgba(255,59,48,0.15)" }
                  : {
                      background: "rgba(255,159,10,0.06)",
                      border: "1px solid rgba(255,159,10,0.15)",
                    }
              }
            >
              <span
                className="mt-0.5 flex-shrink-0 font-mono text-xs font-bold"
                style={{
                  color:
                    issue.severity === "error" ? "var(--color-danger)" : "var(--color-warning)",
                }}
              >
                {issue.severity === "error" ? "ERR" : "WRN"}
              </span>
              <div>
                <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                  {issue.message}
                </p>
                <p
                  className="mt-0.5 font-mono text-xs"
                  style={{ color: "var(--color-text-secondary)" }}
                >
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
          onClick={onNext}
          className="flex-1 rounded-xl py-3.5 text-sm font-semibold text-white transition-all"
          style={{ background: "var(--color-accent)", cursor: "pointer" }}
        >
          Choose AI Provider →
        </button>
      </div>
    </div>
  );
}
