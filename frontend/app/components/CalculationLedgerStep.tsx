"use client";

import { useState } from "react";
import { type TaxReport, type OCROutput } from "../lib/api";
import { NRA_VISA_TYPES } from "../lib/constants";
import { Form8843Card } from "./Form8843Card";
import { ExportButton } from "./ExportButton";

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
      <p
        className="font-mono text-xs tracking-wide"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {label}
      </p>
      <div
        className={`rounded-lg px-3 py-2 text-sm ${multiline ? "min-h-[3.5rem]" : ""}`}
        style={
          prefilled
            ? {
                background: "rgba(255,159,10,0.08)",
                border: "1px solid rgba(255,159,10,0.25)",
                color: "var(--color-text-primary)",
              }
            : {
                background: "var(--color-bg)",
                border: "1px dashed var(--color-border)",
                color: "var(--color-text-secondary)",
              }
        }
      >
        {prefilled ? (
          <span className="font-mono leading-relaxed">{value}</span>
        ) : (
          <span className="italic">{placeholder ?? "—"}</span>
        )}
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

  const outcomeConfig: Record<
    string,
    { label: string; color: string; bg: string; border: string }
  > = {
    refund: {
      label: "ESTIMATED REFUND",
      color: "var(--color-success)",
      bg: "rgba(52,199,89,0.08)",
      border: "rgba(52,199,89,0.25)",
    },
    owe: {
      label: "ESTIMATED TAX OWED",
      color: "var(--color-danger)",
      bg: "rgba(255,59,48,0.08)",
      border: "rgba(255,59,48,0.25)",
    },
    balanced: {
      label: "BALANCED",
      color: "var(--color-accent)",
      bg: "rgba(0,113,227,0.06)",
      border: "rgba(0,113,227,0.2)",
    },
    unknown: {
      label: "OUTCOME UNKNOWN",
      color: "var(--color-text-secondary)",
      bg: "var(--color-bg)",
      border: "var(--color-border)",
    },
  };

  const cfg = outcomeConfig[report.estimated_outcome] ?? outcomeConfig.unknown;
  const amountStr =
    report.estimated_amount != null
      ? `$${report.estimated_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : null;

  const flagSteps = report.calculation_steps.filter((s) => s.is_flag);
  const w2FlagSteps = flagSteps.filter((s) => !s.source_form || s.source_form === "W-2");
  const necFlagSteps = flagSteps.filter((s) => s.source_form === "1099-NEC");
  const normalSteps = report.calculation_steps.filter((s) => !s.is_flag);

  const stateSteps = normalSteps.filter((s) => s.source_form === "STATE");
  const stateFlagSteps = flagSteps.filter((s) => s.source_form === "STATE");

  const necNormalSteps = normalSteps.filter((s) => s.source_form === "1099-NEC");
  const findNecStep = (label: string) =>
    necNormalSteps.find((s) => s.label.toLowerCase().includes(label.toLowerCase()))?.output_value ??
    null;
  const seNetIncome = findNecStep("Self-Employment Income");
  const seTax = findNecStep("Self-Employment Tax");
  const seDeductible = findNecStep("Deductible Half");
  const hasNecSteps = necNormalSteps.length > 0;

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--color-text-primary)" }}
        >
          Tax Report
        </h2>
        <p className="mt-1 font-mono text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {report.document_id}
        </p>
      </div>

      {/* Outcome banner */}
      <div
        className="rounded-2xl px-6 py-5 text-center"
        style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
      >
        <p className="mb-3 font-mono text-xs tracking-widest" style={{ color: cfg.color }}>
          {cfg.label}
        </p>
        {amountStr && (
          <p className="mb-2 text-5xl font-bold tracking-tight" style={{ color: cfg.color }}>
            {amountStr}
          </p>
        )}
        {report.outcome_explanation && (
          <p
            className="mx-auto mt-3 max-w-md text-sm leading-relaxed"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {report.outcome_explanation}
          </p>
        )}
        <p className="mt-3 text-xs" style={{ color: "var(--color-text-secondary)", opacity: 0.7 }}>
          Estimate only — consult a qualified tax professional before filing.
        </p>
      </div>

      {/* ITIN Guidance Card */}
      {report.needs_itin_guidance && (
        <div
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid rgba(0,113,227,0.25)" }}
        >
          <div
            className="flex items-center gap-2 px-5 py-3"
            style={{
              background: "rgba(0,113,227,0.06)",
              borderBottom: "1px solid rgba(0,113,227,0.12)",
            }}
          >
            <span className="text-sm">🪪</span>
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--color-accent)" }}>
                ITIN Required — Form W-7
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                Individual Taxpayer Identification Number · IRS Publication 1915
              </p>
            </div>
          </div>
          <div className="space-y-3 p-5" style={{ background: "var(--color-surface)" }}>
            <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-primary)" }}>
              No SSN was detected on your document. F-1, J-1, and OPT visa holders who are not
              eligible for a Social Security Number must obtain an{" "}
              <strong style={{ color: "var(--color-accent)" }}>
                Individual Taxpayer Identification Number (ITIN)
              </strong>{" "}
              before filing Form 1040-NR.
            </p>
            <div
              className="space-y-1.5 rounded-lg px-4 py-3"
              style={{
                background: "rgba(0,113,227,0.04)",
                border: "1px solid rgba(0,113,227,0.12)",
              }}
            >
              <p
                className="font-mono text-xs tracking-widest uppercase"
                style={{ color: "var(--color-accent)" }}
              >
                Next Steps
              </p>
              <ol
                className="list-inside list-decimal space-y-1 text-xs leading-relaxed"
                style={{ color: "var(--color-text-secondary)" }}
              >
                <li>
                  Complete <strong style={{ color: "var(--color-text-primary)" }}>Form W-7</strong>{" "}
                  (Application for IRS Individual Taxpayer Identification Number).
                </li>
                <li>
                  Attach original identification documents or certified copies (passport, visa,
                  etc.).
                </li>
                <li>
                  Submit Form W-7 with your tax return or by mail to the IRS ITIN Operations office.
                </li>
              </ol>
            </div>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)", opacity: 0.7 }}>
              Reference: IRC §6109 · IRS Publication 1915 · Form W-7 instructions at irs.gov.
              Processing typically takes 7–11 weeks.
            </p>
          </div>
        </div>
      )}

      {/* Form 8833 Treaty Disclosure Advisory */}
      {report.treaty_exempt_amount != null && report.treaty_exempt_amount > 0 && (
        <div
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid rgba(52,199,89,0.25)" }}
        >
          <div
            className="flex items-center gap-2 px-5 py-3"
            style={{
              background: "rgba(52,199,89,0.06)",
              borderBottom: "1px solid rgba(52,199,89,0.12)",
            }}
          >
            <span className="text-sm">📄</span>
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--color-success)" }}>
                Form 8833 Required — Treaty Disclosure
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                Treaty-Based Return Position Disclosure · IRC §6114
              </p>
            </div>
          </div>
          <div className="space-y-3 p-5" style={{ background: "var(--color-surface)" }}>
            <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-primary)" }}>
              A treaty exemption of{" "}
              <strong style={{ color: "var(--color-success)" }}>
                $
                {report.treaty_exempt_amount.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </strong>
              {report.treaty_country
                ? ` under the US–${report.treaty_country} income tax treaty`
                : " under a US income tax treaty"}{" "}
              was applied to your return. Under{" "}
              <strong style={{ color: "var(--color-text-primary)" }}>IRC §6114</strong>, you are
              required to disclose this treaty-based position by attaching{" "}
              <strong style={{ color: "var(--color-success)" }}>Form 8833</strong> to your tax
              return.
            </p>
            <div
              className="space-y-1.5 rounded-lg px-4 py-3"
              style={{
                background: "rgba(52,199,89,0.04)",
                border: "1px solid rgba(52,199,89,0.15)",
              }}
            >
              <p
                className="font-mono text-xs tracking-widest uppercase"
                style={{ color: "var(--color-success)" }}
              >
                Next Steps
              </p>
              <ol
                className="list-inside list-decimal space-y-1 text-xs leading-relaxed"
                style={{ color: "var(--color-text-secondary)" }}
              >
                <li>
                  Download <strong style={{ color: "var(--color-text-primary)" }}>Form 8833</strong>{" "}
                  from irs.gov.
                </li>
                <li>
                  Complete Part I — identify the treaty country and the treaty article relied upon.
                </li>
                <li>
                  In Part II, describe the treaty-based position and the amount of income excluded.
                </li>
                <li>Attach the completed Form 8833 to your Form 1040-NR when filing.</li>
              </ol>
            </div>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)", opacity: 0.7 }}>
              Failure to disclose can result in a penalty of $1,000 per return (IRC §6712). See IRS
              Publication 901 for treaty details.
            </p>
          </div>
        </div>
      )}

      {/* Form 843 Pre-fill Card — W-2 only */}
      {w2FlagSteps.length > 0 && (
        <div
          id="form-843-printable"
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid rgba(255,159,10,0.25)" }}
        >
          <div
            className="flex items-center justify-between gap-3 px-5 py-3"
            style={{
              background: "rgba(255,159,10,0.06)",
              borderBottom: "1px solid rgba(255,159,10,0.12)",
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-sm" style={{ color: "var(--color-warning)" }}>
                ⚠
              </span>
              <div>
                <p className="text-sm font-semibold" style={{ color: "var(--color-warning)" }}>
                  Form 843 — Pre-fill Draft
                </p>
                <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  Claim for Refund and Request for Abatement · FICA Overcollection
                </p>
              </div>
            </div>
            <button
              id="form-843-print-btn"
              onClick={() => window.print()}
              className="flex flex-shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-all"
              style={{
                background: "rgba(255,159,10,0.1)",
                border: "1px solid rgba(255,159,10,0.3)",
                color: "var(--color-warning)",
              }}
            >
              ↓ Download as PDF
            </button>
          </div>

          <div className="space-y-5 p-5" style={{ background: "var(--color-surface)" }}>
            {(() => {
              const f = (key: string) => ocr?.field_candidates[key]?.value ?? null;
              const empName = f("employee_name");
              const empSSN = f("employee_ssn");
              const empAddr = f("employee_address");
              const taxYear = f("tax_year");
              const emplName = f("employer_name");
              const emplEIN = f("employer_ein");

              return (
                <>
                  <div>
                    <p
                      className="mb-2 font-mono text-xs tracking-widest uppercase"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      Part I — Taxpayer
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Form843Field
                        label="Your full name"
                        value={empName ?? undefined}
                        prefilled={!!empName}
                        placeholder="As shown on your W-2"
                      />
                      <Form843Field
                        label="Calendar year"
                        value={taxYear ?? undefined}
                        prefilled={!!taxYear}
                        placeholder="e.g. 2024"
                      />
                      <Form843Field
                        label="Social Security Number"
                        value={empSSN ?? undefined}
                        prefilled={!!empSSN}
                        placeholder="XXX-XX-XXXX"
                      />
                      <Form843Field
                        label="Current address"
                        value={empAddr ?? undefined}
                        prefilled={!!empAddr}
                        placeholder="Street, City, State, ZIP"
                      />
                    </div>
                  </div>

                  <div>
                    <p
                      className="mb-2 font-mono text-xs tracking-widest uppercase"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      Part II — Employer (from Box b &amp; c of your W-2)
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Form843Field
                        label="Employer name"
                        value={emplName ?? undefined}
                        prefilled={!!emplName}
                        placeholder="From Box c of your W-2"
                      />
                      <Form843Field
                        label="Employer EIN"
                        value={emplEIN ?? undefined}
                        prefilled={!!emplEIN}
                        placeholder="From Box b of your W-2"
                      />
                    </div>
                  </div>

                  {w2FlagSteps.map((step) => {
                    const amountMatch = step.output_value.match(/\$[\d,]+(?:\.\d{2})?/);
                    const refundAmount = amountMatch ? amountMatch[0] : step.output_value;
                    const explanation =
                      step.explanation ||
                      `Exempt nonresident student — FICA taxes incorrectly withheld. Refund claimed under ${step.rule_reference}.`;
                    return (
                      <div key={step.step_number}>
                        <p
                          className="mb-2 font-mono text-xs tracking-widest uppercase"
                          style={{ color: "var(--color-text-secondary)" }}
                        >
                          Part III — Claim (pre-filled from your tax calculation)
                        </p>
                        <div className="space-y-2">
                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            <Form843Field
                              label="Type of tax"
                              value="Social Security and Medicare (FICA)"
                              prefilled
                            />
                            <Form843Field
                              label="Amount of refund requested"
                              value={refundAmount}
                              prefilled
                            />
                          </div>
                          <Form843Field
                            label="IRC basis for refund"
                            value={step.rule_reference}
                            prefilled
                          />
                          <Form843Field
                            label="Explanation"
                            value={explanation}
                            prefilled
                            multiline
                          />
                        </div>
                      </div>
                    );
                  })}

                  <div
                    className="mt-1 space-y-1 pt-3 text-xs leading-relaxed"
                    style={{
                      borderTop: "1px solid rgba(255,159,10,0.12)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    <p>
                      <span className="font-semibold" style={{ color: "var(--color-warning)" }}>
                        Next steps:
                      </span>{" "}
                      Fill in any unfilled fields above. Attach a copy of your W-2 and a written
                      statement from your employer confirming your exempt status. Mail the completed
                      Form 843 to the IRS service center for your area.
                    </p>
                    <p style={{ opacity: 0.7 }}>
                      This is a pre-fill draft, not the official IRS form. Download the official
                      Form 843 at irs.gov. The IRS typically processes refund claims within 6
                      months.
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
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid rgba(255,159,10,0.25)" }}
        >
          <div
            className="flex items-center gap-2 px-5 py-3"
            style={{
              background: "rgba(255,159,10,0.06)",
              borderBottom: "1px solid rgba(255,159,10,0.12)",
            }}
          >
            <span className="text-sm">📋</span>
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--color-warning)" }}>
                Schedule SE — Self-Employment Tax Summary
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                Form 1040, Schedule SE · Self-Employment Tax Calculation
              </p>
            </div>
          </div>

          <div className="space-y-4 p-5" style={{ background: "var(--color-surface)" }}>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Form843Field
                label="Net SE Income (92.35%)"
                value={seNetIncome ?? undefined}
                prefilled={!!seNetIncome}
                placeholder="From Step 3"
              />
              <Form843Field
                label="Self-Employment Tax (15.3%)"
                value={seTax ?? undefined}
                prefilled={!!seTax}
                placeholder="From Step 4"
              />
              <Form843Field
                label="Deductible Half (Line 15)"
                value={seDeductible ?? undefined}
                prefilled={!!seDeductible}
                placeholder="From Step 5"
              />
            </div>

            {necFlagSteps.length > 0 && (
              <div className="space-y-2">
                {necFlagSteps.map((step) => (
                  <div
                    key={step.step_number}
                    className="rounded-lg px-4 py-3 text-sm"
                    style={{
                      background: "rgba(255,159,10,0.06)",
                      border: "1px solid rgba(255,159,10,0.18)",
                    }}
                  >
                    <p
                      className="mb-1 font-mono text-xs font-semibold"
                      style={{ color: "var(--color-warning)" }}
                    >
                      {step.label}
                    </p>
                    <p className="leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                      {step.explanation || `Advisory: ${step.rule_reference}`}
                    </p>
                  </div>
                ))}
              </div>
            )}

            <div
              className="mt-1 pt-3 text-xs leading-relaxed"
              style={{
                borderTop: "1px solid rgba(255,159,10,0.12)",
                color: "var(--color-text-secondary)",
              }}
            >
              <p>
                <span className="font-semibold" style={{ color: "var(--color-warning)" }}>
                  Next steps:
                </span>{" "}
                Report self-employment income on Schedule C (Form 1040). Use the SE tax amount above
                on Schedule SE to calculate your Social Security and Medicare tax. The deductible
                half reduces your adjusted gross income on Form 1040, Line 15.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* State Tax Estimate Card */}
      {(stateSteps.length > 0 || stateFlagSteps.length > 0) && (
        <div
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid rgba(0,113,227,0.2)" }}
        >
          <div
            className="flex items-center gap-2 px-5 py-3"
            style={{
              background: "rgba(0,113,227,0.06)",
              borderBottom: "1px solid rgba(0,113,227,0.12)",
            }}
          >
            <span className="text-sm">🏛</span>
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--color-accent)" }}>
                State Tax Estimate
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                State income tax ledger · 2025 estimate only
              </p>
            </div>
          </div>

          <div className="overflow-hidden" style={{ background: "var(--color-surface)" }}>
            {stateSteps.map((step) => (
              <div
                key={step.step_number}
                className="grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-3 text-sm"
                style={{ borderBottom: "1px solid var(--color-border)" }}
              >
                <span
                  className="pt-0.5 font-mono text-xs"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {step.step_number}
                </span>
                <div>
                  <p style={{ color: "var(--color-text-primary)" }}>{step.label}</p>
                  <p
                    className="mt-0.5 font-mono text-xs"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {step.rule_reference}
                  </p>
                </div>
                <p
                  className="text-right font-mono text-sm whitespace-nowrap"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {step.output_value}
                </p>
              </div>
            ))}
            {stateFlagSteps.map((step) => (
              <div
                key={step.step_number}
                className="mx-4 my-3 rounded-lg px-4 py-3 text-sm"
                style={{
                  background: "rgba(0,113,227,0.06)",
                  border: "1px solid rgba(0,113,227,0.15)",
                }}
              >
                <p
                  className="mb-1 font-mono text-xs font-semibold"
                  style={{ color: "var(--color-accent)" }}
                >
                  {step.label}
                </p>
                <p className="leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                  {step.explanation || step.output_value}
                </p>
              </div>
            ))}
            <div
              className="px-5 py-3 text-xs leading-relaxed"
              style={{
                borderTop: "1px solid var(--color-border)",
                color: "var(--color-text-secondary)",
              }}
            >
              <p>
                <span className="font-semibold" style={{ color: "var(--color-accent)" }}>
                  Note:
                </span>{" "}
                State estimate uses 2025 brackets and does not account for state-specific credits,
                deductions, or withholding. Consult a tax professional for accurate state filing.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Calculation Ledger */}
      {normalSteps.length > 0 && (
        <div
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid var(--color-border)" }}
        >
          <div
            className="grid grid-cols-[2rem_1fr_auto] gap-3 px-4 py-2.5 font-mono text-xs tracking-widest uppercase"
            style={{
              background: "var(--color-bg)",
              borderBottom: "1px solid var(--color-border)",
              color: "var(--color-text-secondary)",
            }}
          >
            <span>#</span>
            <span>Step</span>
            <span>Amount</span>
          </div>

          {normalSteps.map((step) => {
            const isOpen = expanded.has(step.step_number);
            return (
              <div key={step.step_number} style={{ borderBottom: "1px solid var(--color-border)" }}>
                <button
                  onClick={() => toggleRow(step.step_number)}
                  aria-expanded={isOpen}
                  aria-controls={`step-detail-${step.step_number}`}
                  className="grid w-full grid-cols-[2rem_1fr_auto] gap-3 px-4 py-3 text-left transition-colors"
                  style={{ background: "var(--color-surface)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-bg)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "var(--color-surface)")}
                >
                  <span
                    className="pt-0.5 font-mono text-xs"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {step.step_number}
                  </span>
                  <div>
                    <p className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                      {step.label}
                    </p>
                    <p
                      className="mt-0.5 font-mono text-xs"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {step.rule_reference}
                    </p>
                  </div>
                  <div className="text-right">
                    <p
                      className="font-mono text-sm whitespace-nowrap"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {step.output_value}
                    </p>
                    <p className="mt-0.5 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                      {isOpen ? "▲" : "▼"}
                    </p>
                  </div>
                </button>

                {isOpen && (
                  <div
                    id={`step-detail-${step.step_number}`}
                    role="region"
                    className="px-4 py-3 text-sm leading-relaxed"
                    style={{
                      background: "var(--color-bg)",
                      borderTop: "1px solid var(--color-border)",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    <span className="mr-2 font-mono text-xs" style={{ opacity: 0.7 }}>
                      Input:
                    </span>
                    <span className="font-mono">{step.input_value}</span>
                    {step.explanation && <p className="mt-2">{step.explanation}</p>}
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
          className="overflow-hidden rounded-xl"
          style={{ border: "1px solid var(--color-border)" }}
        >
          <div
            className="px-4 py-2.5"
            style={{ background: "var(--color-bg)", borderBottom: "1px solid var(--color-border)" }}
          >
            <span
              className="font-mono text-xs tracking-widest uppercase"
              style={{ color: "var(--color-warning)" }}
            >
              Validation Notes
            </span>
          </div>
          <div className="space-y-2 px-4 py-3" style={{ background: "var(--color-surface)" }}>
            {report.validation_results.map((v, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <span
                  className="mt-0.5 flex-shrink-0 font-mono text-xs"
                  style={{
                    color: v.severity === "error" ? "var(--color-danger)" : "var(--color-warning)",
                  }}
                >
                  {v.severity === "error" ? "ERR" : "WRN"}
                </span>
                <span style={{ color: "var(--color-text-secondary)" }}>{v.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Form 8843 card — shown for NRA visa types when the engine populated form_8843_data */}
      {report.form_8843_data && NRA_VISA_TYPES.includes(report.form_8843_data.visa_type) && (
        <Form8843Card data={report.form_8843_data} />
      )}

      {/* Export tax filing package — shown for NRA users with form_8843_data */}
      {report.form_8843_data && NRA_VISA_TYPES.includes(report.form_8843_data.visa_type) && (
        <ExportButton documentId={report.document_id} />
      )}

      <button
        onClick={() => window.location.reload()}
        className="w-full rounded-xl py-3 text-sm font-medium transition-all"
        style={{
          border: "1px solid var(--color-border)",
          color: "var(--color-text-secondary)",
          background: "transparent",
          cursor: "pointer",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-text-primary)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
      >
        Review Another Document
      </button>
    </div>
  );
}
