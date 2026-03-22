"use client";

import { useState } from "react";
import { type TaxReport } from "../lib/api";

export function CalculationLedgerStep({ report }: { report: TaxReport }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggleRow = (n: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });

  const outcomeConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string }> = {
    refund:   { label: "ESTIMATED REFUND",   color: "#34d399", bg: "rgba(52,211,153,0.07)",  border: "rgba(52,211,153,0.25)",  glow: "rgba(52,211,153,0.25)"  },
    owe:      { label: "ESTIMATED TAX OWED", color: "#f87171", bg: "rgba(248,113,113,0.07)", border: "rgba(248,113,113,0.25)", glow: "rgba(248,113,113,0.2)"  },
    balanced: { label: "BALANCED",           color: "#60a5fa", bg: "rgba(96,165,250,0.07)",  border: "rgba(96,165,250,0.25)",  glow: "rgba(96,165,250,0.2)"   },
    unknown:  { label: "OUTCOME UNKNOWN",    color: "#94a3b8", bg: "rgba(100,116,139,0.07)", border: "rgba(100,116,139,0.25)", glow: "rgba(100,116,139,0.1)"  },
  };

  const cfg = outcomeConfig[report.estimated_outcome] ?? outcomeConfig.unknown;
  const amountStr = report.estimated_amount != null
    ? `$${report.estimated_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : null;

  const flagSteps = report.calculation_steps.filter((s) => s.is_flag);
  const normalSteps = report.calculation_steps.filter((s) => !s.is_flag);

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Tax Report</h2>
        <p className="text-xs font-mono text-slate-700 mt-1">{report.document_id}</p>
      </div>

      {/* Outcome banner */}
      <div
        className="rounded-2xl px-6 py-5 text-center"
        style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, boxShadow: `0 0 36px ${cfg.glow}` }}
      >
        <p className="text-xs font-mono tracking-widest mb-3" style={{ color: cfg.color }}>
          {cfg.label}
        </p>
        {amountStr && (
          <p className="text-5xl font-bold tracking-tight mb-2" style={{ color: cfg.color }}>
            {amountStr}
          </p>
        )}
        {report.outcome_explanation && (
          <p className="text-sm text-slate-400 mt-3 leading-relaxed max-w-md mx-auto">
            {report.outcome_explanation}
          </p>
        )}
        <p className="text-xs text-slate-600 mt-3">
          Estimate only — consult a qualified tax professional before filing.
        </p>
      </div>

      {/* FICA Handoff Card — placed between outcome banner and calculation ledger */}
      {flagSteps.length > 0 && (
        <div
          className="rounded-xl p-5 space-y-3"
          style={{ background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.25)" }}
        >
          <div className="flex items-center gap-2">
            <span className="text-base">⚠</span>
            <p className="text-sm font-semibold text-amber-300">Potential FICA Refund Opportunity</p>
          </div>
          {flagSteps.map((step) => (
            <div key={step.step_number} className="space-y-1">
              <p className="text-sm text-amber-200/80">{step.label.replace("⚠ ", "")}</p>
              <p className="text-xs font-mono text-amber-200/50">{step.output_value}</p>
              {step.explanation && (
                <p className="text-xs text-slate-500 leading-relaxed">{step.explanation}</p>
              )}
              <p className="text-xs text-slate-600 font-mono">{step.rule_reference}</p>
            </div>
          ))}
          <p className="text-xs text-slate-500 pt-1">
            File <span className="text-amber-300 font-semibold">Form 843</span> with the IRS to claim a refund of incorrectly withheld FICA taxes. Attach a copy of your W-2 and a statement from your employer.
          </p>
        </div>
      )}

      {/* Calculation Ledger */}
      {normalSteps.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div
            className="grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-2.5 text-xs font-mono tracking-widest uppercase"
            style={{ background: "rgba(15,23,42,0.9)", borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#475569" }}
          >
            <span>#</span>
            <span>Step</span>
            <span>Amount</span>
          </div>

          {normalSteps.map((step) => {
            const isOpen = expanded.has(step.step_number);
            return (
              <div key={step.step_number} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <button
                  onClick={() => toggleRow(step.step_number)}
                  className="w-full grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
                  style={{ background: "rgba(13,20,36,0.5)" }}
                >
                  <span className="text-xs font-mono text-slate-600 pt-0.5">{step.step_number}</span>
                  <div>
                    <p className="text-sm text-slate-200">{step.label}</p>
                    <p className="text-xs text-slate-600 font-mono mt-0.5">{step.rule_reference}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-slate-100 whitespace-nowrap">{step.output_value}</p>
                    <p className="text-xs text-slate-700 mt-0.5">{isOpen ? "▲" : "▼"}</p>
                  </div>
                </button>

                {isOpen && (
                  <div
                    className="px-4 py-3 text-sm text-slate-400 leading-relaxed"
                    style={{ background: "rgba(6,11,20,0.6)", borderTop: "1px solid rgba(255,255,255,0.04)" }}
                  >
                    <span className="text-xs font-mono text-slate-600 mr-2">Input:</span>
                    <span className="font-mono text-slate-500">{step.input_value}</span>
                    {step.explanation && (
                      <p className="mt-2 text-slate-400">{step.explanation}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Validation notes */}
      {report.validation_results.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div
            className="px-4 py-2.5"
            style={{ background: "rgba(15,23,42,0.8)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
          >
            <span className="text-xs font-mono tracking-widest uppercase" style={{ color: "#fb923c" }}>
              Validation Notes
            </span>
          </div>
          <div className="px-4 py-3 space-y-2" style={{ background: "rgba(13,20,36,0.5)" }}>
            {report.validation_results.map((v, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <span className="font-mono text-xs flex-shrink-0 mt-0.5"
                  style={{ color: v.severity === "error" ? "#f87171" : "#fbbf24" }}>
                  {v.severity === "error" ? "ERR" : "WRN"}
                </span>
                <span className="text-slate-400">{v.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => window.location.reload()}
        className="w-full py-3 rounded-xl text-slate-400 hover:text-slate-200 font-medium text-sm transition-all"
        style={{ border: "1px solid rgba(71,85,105,0.4)" }}
      >
        Review Another Document
      </button>
    </div>
  );
}
