"use client";

import { useState } from "react";
import { type TaxReport, type OCROutput } from "../lib/api";

function Form843Field({
  label,
  value,
  placeholder,
  prefilled,
  multiline,
}: {
  label: string;
  value?: string;
  placeholder?: string;
  prefilled?: boolean;
  multiline?: boolean;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-mono tracking-wide" style={{ color: "#64748b" }}>
        {label}
      </p>
      <div
        className={`px-3 py-2 rounded-lg text-sm ${multiline ? "min-h-[3.5rem]" : ""}`}
        style={
          prefilled
            ? { background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.25)", color: "#fde68a" }
            : { background: "rgba(15,23,42,0.4)", border: "1px dashed rgba(71,85,105,0.35)", color: "#475569" }
        }
      >
        {prefilled
          ? <span className="font-mono leading-relaxed">{value}</span>
          : <span className="italic">{placeholder ?? "—"}</span>
        }
      </div>
    </div>
  );
}

export function CalculationLedgerStep({ report, ocr }: { report: TaxReport; ocr?: OCROutput }) {
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
  const w2FlagSteps = flagSteps.filter((s) => !s.source_form || s.source_form === "W-2");
  const necFlagSteps = flagSteps.filter((s) => s.source_form === "1099-NEC");
  const normalSteps = report.calculation_steps.filter((s) => !s.is_flag);

  // Extract state tax steps for the State Tax Estimate card
  const stateSteps = normalSteps.filter((s) => s.source_form === "STATE");
  const stateFlagSteps = flagSteps.filter((s) => s.source_form === "STATE");

  // Extract Schedule SE values from NEC normal steps for the prefill card
  const necNormalSteps = normalSteps.filter((s) => s.source_form === "1099-NEC");
  const findNecStep = (label: string) =>
    necNormalSteps.find((s) => s.label.toLowerCase().includes(label.toLowerCase()))?.output_value ?? null;
  const seNetIncome   = findNecStep("Self-Employment Income");
  const seTax         = findNecStep("Self-Employment Tax");
  const seDeductible  = findNecStep("Deductible Half");
  const hasNecSteps   = necNormalSteps.length > 0;

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

      {/* Form 843 Pre-fill Card — W-2 only */}
      {w2FlagSteps.length > 0 && (
        <div
          id="form-843-printable"
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(251,191,36,0.3)" }}
        >
          {/* Card header */}
          <div
            className="px-5 py-3 flex items-center justify-between gap-3"
            style={{ background: "rgba(251,191,36,0.08)", borderBottom: "1px solid rgba(251,191,36,0.15)" }}
          >
            <div className="flex items-center gap-2">
              <span className="text-amber-400 text-sm">⚠</span>
              <div>
                <p className="text-sm font-semibold text-amber-300">Form 843 — Pre-fill Draft</p>
                <p className="text-xs text-slate-500">Claim for Refund and Request for Abatement · FICA Overcollection</p>
              </div>
            </div>
            <button
              id="form-843-print-btn"
              onClick={() => window.print()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap flex-shrink-0"
              style={{ background: "rgba(251,191,36,0.15)", border: "1px solid rgba(251,191,36,0.4)", color: "#fbbf24" }}
            >
              ↓ Download as PDF
            </button>
          </div>

          {/* Form body */}
          <div className="p-5 space-y-5" style={{ background: "rgba(251,191,36,0.02)" }}>
            {(() => {
              const f = (key: string) => ocr?.field_candidates[key]?.value ?? null;
              const empName   = f("employee_name");
              const empSSN    = f("employee_ssn");
              const empAddr   = f("employee_address");
              const taxYear   = f("tax_year");
              const emplName  = f("employer_name");
              const emplEIN   = f("employer_ein");

              return (
                <>
                  {/* Part I — Taxpayer (rendered once, pre-filled from OCR) */}
                  <div>
                    <p className="text-xs font-mono tracking-widest uppercase mb-2" style={{ color: "#64748b" }}>
                      Part I — Taxpayer
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Form843Field label="Your full name"          value={empName  ?? undefined} prefilled={!!empName}  placeholder="As shown on your W-2" />
                      <Form843Field label="Calendar year"           value={taxYear  ?? undefined} prefilled={!!taxYear}  placeholder="e.g. 2024" />
                      <Form843Field label="Social Security Number"  value={empSSN   ?? undefined} prefilled={!!empSSN}   placeholder="XXX-XX-XXXX" />
                      <Form843Field label="Current address"         value={empAddr  ?? undefined} prefilled={!!empAddr}  placeholder="Street, City, State, ZIP" />
                    </div>
                  </div>

                  {/* Part II — Employer (rendered once, pre-filled from OCR) */}
                  <div>
                    <p className="text-xs font-mono tracking-widest uppercase mb-2" style={{ color: "#64748b" }}>
                      Part II — Employer (from Box b &amp; c of your W-2)
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Form843Field label="Employer name" value={emplName ?? undefined} prefilled={!!emplName} placeholder="From Box c of your W-2" />
                      <Form843Field label="Employer EIN"  value={emplEIN  ?? undefined} prefilled={!!emplEIN}  placeholder="From Box b of your W-2" />
                    </div>
                  </div>

                  {/* Part III — one claim block per W-2 flag step */}
                  {w2FlagSteps.map((step) => {
                    const amountMatch = step.output_value.match(/\$[\d,]+(?:\.\d{2})?/);
                    const refundAmount = amountMatch ? amountMatch[0] : step.output_value;
                    const explanation = step.explanation ||
                      `Exempt nonresident student — FICA taxes incorrectly withheld. Refund claimed under ${step.rule_reference}.`;
                    return (
                      <div key={step.step_number}>
                        <p className="text-xs font-mono tracking-widest uppercase mb-2" style={{ color: "#64748b" }}>
                          Part III — Claim (pre-filled from your tax calculation)
                        </p>
                        <div className="space-y-2">
                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            <Form843Field label="Type of tax" value="Social Security and Medicare (FICA)" prefilled />
                            <Form843Field label="Amount of refund requested" value={refundAmount} prefilled />
                          </div>
                          <Form843Field label="IRC basis for refund" value={step.rule_reference} prefilled />
                          <Form843Field label="Explanation" value={explanation} prefilled multiline />
                        </div>
                      </div>
                    );
                  })}

                  {/* Instructions */}
                  <div
                    className="pt-3 mt-1 text-xs text-slate-500 leading-relaxed space-y-1"
                    style={{ borderTop: "1px solid rgba(251,191,36,0.12)" }}
                  >
                    <p>
                      <span className="text-amber-400 font-semibold">Next steps:</span>{" "}
                      Fill in any grey fields above. Attach a copy of your W-2 and a written statement from your employer confirming your exempt status. Mail the completed Form 843 to the IRS service center for your area.
                    </p>
                    <p className="text-slate-600">
                      This is a pre-fill draft, not the official IRS form. Download the official Form 843 at irs.gov. The IRS typically processes refund claims within 6 months.
                    </p>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* Schedule SE Guidance Card — 1099-NEC only */}
      {(hasNecSteps || necFlagSteps.length > 0) && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(251,191,36,0.3)" }}
        >
          <div
            className="px-5 py-3 flex items-center gap-2"
            style={{ background: "rgba(251,191,36,0.08)", borderBottom: "1px solid rgba(251,191,36,0.15)" }}
          >
            <span className="text-amber-400 text-sm">📋</span>
            <div>
              <p className="text-sm font-semibold text-amber-300">Schedule SE — Self-Employment Tax Summary</p>
              <p className="text-xs text-slate-500">Form 1040, Schedule SE · Self-Employment Tax Calculation</p>
            </div>
          </div>

          <div className="p-5 space-y-4" style={{ background: "rgba(251,191,36,0.02)" }}>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Form843Field label="Net SE Income (92.35%)" value={seNetIncome ?? undefined} prefilled={!!seNetIncome} placeholder="From Step 3" />
              <Form843Field label="Self-Employment Tax (15.3%)" value={seTax ?? undefined} prefilled={!!seTax} placeholder="From Step 4" />
              <Form843Field label="Deductible Half (Line 15)" value={seDeductible ?? undefined} prefilled={!!seDeductible} placeholder="From Step 5" />
            </div>

            {necFlagSteps.length > 0 && (
              <div className="space-y-2">
                {necFlagSteps.map((step) => (
                  <div
                    key={step.step_number}
                    className="rounded-lg px-4 py-3 text-sm"
                    style={{ background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)" }}
                  >
                    <p className="text-amber-300 font-semibold text-xs font-mono mb-1">{step.label}</p>
                    <p className="text-slate-400 leading-relaxed">
                      {step.explanation || `Advisory: ${step.rule_reference}`}
                    </p>
                  </div>
                ))}
              </div>
            )}

            <div
              className="pt-3 mt-1 text-xs text-slate-500 leading-relaxed"
              style={{ borderTop: "1px solid rgba(251,191,36,0.12)" }}
            >
              <p>
                <span className="text-amber-400 font-semibold">Next steps:</span>{" "}
                Report self-employment income on Schedule C (Form 1040). Use the SE tax amount above on Schedule SE to calculate your Social Security and Medicare tax. The deductible half reduces your adjusted gross income on Form 1040, Line 15.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* State Tax Estimate Card */}
      {(stateSteps.length > 0 || stateFlagSteps.length > 0) && (
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(96,165,250,0.3)" }}
        >
          <div
            className="px-5 py-3 flex items-center gap-2"
            style={{ background: "rgba(96,165,250,0.08)", borderBottom: "1px solid rgba(96,165,250,0.15)" }}
          >
            <span className="text-blue-400 text-sm">🏛</span>
            <div>
              <p className="text-sm font-semibold text-blue-300">State Tax Estimate</p>
              <p className="text-xs text-slate-500">State income tax ledger · 2025 estimate only</p>
            </div>
          </div>

          <div className="overflow-hidden" style={{ background: "rgba(96,165,250,0.02)" }}>
            {stateSteps.map((step) => (
              <div
                key={step.step_number}
                className="grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-3 text-sm"
                style={{ borderBottom: "1px solid rgba(96,165,250,0.06)" }}
              >
                <span className="text-xs font-mono text-slate-600 pt-0.5">{step.step_number}</span>
                <div>
                  <p className="text-slate-200">{step.label}</p>
                  <p className="text-xs text-slate-600 font-mono mt-0.5">{step.rule_reference}</p>
                </div>
                <p className="text-sm font-mono text-slate-100 whitespace-nowrap text-right">{step.output_value}</p>
              </div>
            ))}
            {stateFlagSteps.map((step) => (
              <div
                key={step.step_number}
                className="rounded-lg mx-4 my-3 px-4 py-3 text-sm"
                style={{ background: "rgba(96,165,250,0.08)", border: "1px solid rgba(96,165,250,0.2)" }}
              >
                <p className="text-blue-300 font-semibold text-xs font-mono mb-1">{step.label}</p>
                <p className="text-slate-400 leading-relaxed">
                  {step.explanation || step.output_value}
                </p>
              </div>
            ))}
            <div
              className="px-5 py-3 text-xs text-slate-500 leading-relaxed"
              style={{ borderTop: "1px solid rgba(96,165,250,0.08)" }}
            >
              <p>
                <span className="text-blue-400 font-semibold">Note:</span>{" "}
                State estimate uses 2025 brackets and does not account for state-specific credits, deductions, or withholding. Consult a tax professional for accurate state filing.
              </p>
            </div>
          </div>
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
                  aria-expanded={isOpen}
                  aria-controls={`step-detail-${step.step_number}`}
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
                    id={`step-detail-${step.step_number}`}
                    role="region"
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
