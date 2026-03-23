const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface FieldValue {
  value: string | null;
  confidence: number;
  source: string;
}

export interface OCROutput {
  document_id: string;
  raw_text: string;
  field_candidates: Record<string, FieldValue>;
  page_count: number;
}

export interface ValidationIssue {
  field: string;
  type: string;
  message: string;
  severity: string;
}

export interface ValidationOutput {
  status: string;
  issues: ValidationIssue[];
}

export interface UserContext {
  visa_type: string;
  first_us_entry_date?: string;
  current_year_days_in_us?: number;
  prior_year_days_in_us?: number;
  second_prior_year_days_in_us?: number;
  has_1042s: boolean;
  wants_state_estimate: boolean;
  state_code?: string;
  claims_exempt_individual: boolean;
  nec_business_expenses?: number;
}

export interface AnalysisPreferences {
  provider: "ollama" | "openai" | "anthropic" | "gemini";
  model?: string;
}

export interface CalculationStep {
  step_number: number;
  label: string;
  rule_reference: string;
  input_value: string;
  output_value: string;
  explanation: string;
  is_flag: boolean;
  source_form?: string;
}

export interface TaxReport {
  document_id: string;
  calculation_steps: CalculationStep[];
  estimated_outcome: "refund" | "owe" | "balanced" | "unknown";
  estimated_amount: number | null;
  outcome_explanation: string;
  validation_results: ValidationIssue[];
}

export interface SessionState {
  status: string;
}

export async function uploadDocument(file: File): Promise<OCROutput> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function saveContext(
  document_id: string,
  context: UserContext
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/context/${document_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(context),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to save context");
  }
}

export async function confirmFields(
  document_id: string,
  confirmed_fields: Record<string, { value: string | null; source: string; confidence?: number }>,
  unresolved_fields: string[]
): Promise<ValidationOutput> {
  const res = await fetch(`${API_BASE}/api/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id, confirmed_fields, unresolved_fields }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Confirm failed");
  }
  return res.json();
}

export async function analyzeDocument(
  document_id: string,
  preferences: AnalysisPreferences
): Promise<TaxReport> {
  const res = await fetch(`${API_BASE}/api/analyze/${document_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preferences),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}

export async function getSessionStatus(document_id: string): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/api/session/${document_id}`);
    if (!res.ok) return "unknown";
    const data = await res.json();
    return data.status || "unknown";
  } catch {
    return "unknown";
  }
}

export async function checkHealth(): Promise<{ status: string; ollama: string }> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
