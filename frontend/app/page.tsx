"use client";

import { useState } from "react";
import { type OCROutput, type ValidationOutput, type TaxReport, type AnalysisPreferences } from "./lib/api";
import { StepBar } from "./components/StepBar";
import { UploadStep } from "./components/UploadStep";
import { ContextStep } from "./components/ContextStep";
import { FieldReviewStep } from "./components/FieldReviewStep";
import { ValidationStep } from "./components/ValidationStep";
import { SettingsStep } from "./components/SettingsStep";
import { AnalysisStep } from "./components/AnalysisStep";
import { CalculationLedgerStep } from "./components/CalculationLedgerStep";
import { DeadlineBanner } from "./components/DeadlineBanner";

// Step indices:
// 0 Upload → 1 Context → 2 Review → 3 Validate → 4 Settings → 5 Analysis → 6 Report

export default function Home() {
  const [step, setStep] = useState(0);
  const [ocr, setOcr] = useState<OCROutput | null>(null);
  const [validation, setValidation] = useState<ValidationOutput | null>(null);
  const [report, setReport] = useState<TaxReport | null>(null);
  const [visaType, setVisaType] = useState<string | undefined>(undefined);
  const [analysisPreferences, setAnalysisPreferences] = useState<AnalysisPreferences>({
    provider: "ollama",
  });

  return (
    <div>
      <StepBar current={step} />
      <DeadlineBanner visaType={visaType} />

      {step === 0 && (
        <UploadStep onUploaded={(o) => { setOcr(o); setStep(1); }} />
      )}

      {step === 1 && ocr && (
        <ContextStep
          documentId={ocr.document_id}
          formType={ocr.field_candidates["form_type"]?.value ?? undefined}
          onConfirm={() => setStep(2)}
          onBack={() => { setOcr(null); setStep(0); }}
          onContextSaved={(vt) => setVisaType(vt)}
        />
      )}

      {step === 2 && ocr && (
        <FieldReviewStep
          ocr={ocr}
          onConfirm={(v) => { setValidation(v); setStep(3); }}
          onBack={() => setStep(1)}
        />
      )}

      {step === 3 && validation && (
        <ValidationStep
          validation={validation}
          onNext={() => setStep(4)}
          onBack={() => setStep(2)}
        />
      )}

      {step === 4 && (
        <SettingsStep
          onAnalyze={(prefs) => { setAnalysisPreferences(prefs); setStep(5); }}
          onBack={() => setStep(3)}
        />
      )}

      {step === 5 && ocr && (
        <AnalysisStep
          documentId={ocr.document_id}
          preferences={analysisPreferences}
          onComplete={(r) => { setReport(r); setStep(6); }}
          onBack={() => setStep(4)}
        />
      )}

      {step === 6 && report && <CalculationLedgerStep report={report} ocr={ocr ?? undefined} />}
    </div>
  );
}
