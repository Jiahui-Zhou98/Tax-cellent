"use client";

import { useState } from "react";
import {
  type OCROutput,
  type ValidationOutput,
  type TaxReport,
  type AnalysisPreferences,
} from "./lib/api";
import { StepSidebar } from "./components/StepSidebar";
import { StepShell } from "./components/StepShell";
import { UploadStep } from "./components/UploadStep";
import { ContextStep, type ContextValues } from "./components/ContextStep";
import { FieldReviewStep } from "./components/FieldReviewStep";
import { ValidationStep } from "./components/ValidationStep";
import { SettingsStep } from "./components/SettingsStep";
import { AnalysisStep } from "./components/AnalysisStep";
import { CalculationLedgerStep } from "./components/CalculationLedgerStep";
import { DeadlineBanner } from "./components/DeadlineBanner";
import { ZeroIncomeStep } from "./components/ZeroIncomeStep";

// Step indices:
// 0 Upload → 1 Context → 2 Review → 3 Validate → 4 Settings → 5 Analysis → 6 Report
// Zero-income fork: step 0 → zeroIncomePath=true → ZeroIncomeStep (sidebar stays at step 0)

export default function Home() {
  const [step, setStep] = useState(0);
  const [ocr, setOcr] = useState<OCROutput | null>(null);
  const [validation, setValidation] = useState<ValidationOutput | null>(null);
  const [report, setReport] = useState<TaxReport | null>(null);
  const [visaType, setVisaType] = useState<string | undefined>(undefined);
  const [analysisPreferences, setAnalysisPreferences] = useState<AnalysisPreferences>({
    provider: "ollama",
  });
  const [zeroIncomePath, setZeroIncomePath] = useState(false);
  // Full context values — restored when user navigates back to ContextStep
  const [savedContextValues, setSavedContextValues] = useState<ContextValues | null>(null);
  // Institution fields captured in ContextStep — pre-populated into ZeroIncomeStep
  const [institutionPrefill, setInstitutionPrefill] = useState<{
    visaType?: string;
    entryYear?: string;
    institutionName?: string;
    institutionCity?: string;
    institutionState?: string;
  }>({});
  // FieldReviewStep state — restored when user navigates back to that step
  type FieldState = Record<string, { value: string; source: string; confidence: number }>;
  const [savedFieldReviewFields, setSavedFieldReviewFields] = useState<FieldState | null>(null);
  const [savedFieldReviewUnresolved, setSavedFieldReviewUnresolved] = useState<string[] | null>(
    null
  );

  // Sidebar always shows step 0 on zero-income path
  const sidebarCurrent = zeroIncomePath ? 0 : step;

  function renderContent() {
    if (zeroIncomePath) {
      return (
        <StepShell step={0}>
          <ZeroIncomeStep onBack={() => setZeroIncomePath(false)} prefill={institutionPrefill} />
        </StepShell>
      );
    }

    if (step === 0) {
      return (
        <StepShell step={0}>
          <UploadStep
            onUploaded={(o) => {
              setOcr(o);
              setStep(1);
            }}
            onZeroIncome={() => setZeroIncomePath(true)}
          />
        </StepShell>
      );
    }

    if (step === 1 && ocr) {
      return (
        <StepShell step={1}>
          <ContextStep
            documentId={ocr.document_id}
            formType={ocr.field_candidates["form_type"]?.value ?? undefined}
            initialValues={savedContextValues ?? undefined}
            onConfirm={() => setStep(2)}
            onBack={() => {
              setOcr(null);
              setSavedContextValues(null);
              setSavedFieldReviewFields(null);
              setSavedFieldReviewUnresolved(null);
              setStep(0);
            }}
            onContextSaved={(ctx) => {
              setVisaType(ctx.visaType);
              setSavedContextValues(ctx);
              setInstitutionPrefill({
                visaType: ctx.visaType,
                entryYear: ctx.entryYear,
                institutionName: ctx.institutionName,
                institutionCity: ctx.institutionCity,
                institutionState: ctx.institutionState,
              });
            }}
          />
        </StepShell>
      );
    }

    if (step === 2 && ocr) {
      return (
        <StepShell step={2}>
          <FieldReviewStep
            ocr={ocr}
            onConfirm={(v) => {
              setValidation(v);
              setStep(3);
            }}
            onBack={() => setStep(1)}
            savedFields={savedFieldReviewFields ?? undefined}
            savedUnresolved={savedFieldReviewUnresolved ?? undefined}
            onStateSave={(fields, unresolved) => {
              setSavedFieldReviewFields(fields);
              setSavedFieldReviewUnresolved(unresolved);
            }}
          />
        </StepShell>
      );
    }

    if (step === 3 && validation) {
      return (
        <StepShell step={3}>
          <ValidationStep
            validation={validation}
            onNext={() => setStep(4)}
            onBack={() => setStep(2)}
          />
        </StepShell>
      );
    }

    if (step === 4) {
      return (
        <StepShell step={4}>
          <SettingsStep
            onAnalyze={(prefs) => {
              setAnalysisPreferences(prefs);
              setStep(5);
            }}
            onBack={() => setStep(3)}
          />
        </StepShell>
      );
    }

    if (step === 5 && ocr) {
      return (
        <StepShell step={5}>
          <AnalysisStep
            documentId={ocr.document_id}
            preferences={analysisPreferences}
            onComplete={(r) => {
              setReport(r);
              setStep(6);
            }}
            onBack={() => setStep(4)}
          />
        </StepShell>
      );
    }

    if (step === 6 && report) {
      // Report step: no nav buttons (CalculationLedgerStep handles its own restart)
      return (
        <StepShell step={6}>
          <CalculationLedgerStep report={report} ocr={ocr ?? undefined} />
        </StepShell>
      );
    }

    return null;
  }

  return (
    <div className="animate-fade-in">
      <DeadlineBanner visaType={visaType} hasIncome={!zeroIncomePath} />
      {/* Two-panel layout: sidebar + content. flex-col on mobile (sidebar is top bar),
          flex-row at 480px+ (sidebar is vertical panel on the left). */}
      <div className="app-layout-panels" style={{ minHeight: "calc(100vh - 57px)" }}>
        <StepSidebar current={sidebarCurrent} />
        <main
          className="flex-1 overflow-y-auto p-6 md:p-10"
          style={{ background: "var(--color-bg)" }}
        >
          {renderContent()}
        </main>
      </div>
    </div>
  );
}
