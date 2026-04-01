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
  country_of_origin?: string;
  institution_name?: string;
  institution_city?: string;
  institution_state?: string;
}

export interface Form8843Data {
  first_name: string;
  last_name: string;
  tin_status: "ssn" | "itin" | "applied_for" | "none";
  tin_value?: string | null;
  visa_type: string;
  first_us_entry_date?: string | null;
  days_in_us_current_year?: number | null;
  role: "student" | "teacher_researcher";
  institution_name?: string | null;
  institution_city?: string | null;
  institution_state?: string | null;
  exempt_prior_years: number[];
  status_change_applied: boolean;
  exchange_program_name?: string | null;
  sponsor_name?: string | null;
  sponsor_address?: string | null;
  years_claimed_exemption?: number | null;
  claimed_in_prior_6_years?: boolean | null;
  has_income: boolean;
  tax_year: number;
  catch_up_years: number[];
}

export interface AnalysisPreferences {
  provider: "ollama" | "openai" | "anthropic" | "gemini";
  model?: string;
  api_key?: string; // Session-only; never persisted
}

export interface ProviderStatus {
  configured: boolean;
  running?: boolean; // Ollama only
}

export interface HealthStatus {
  status: string;
  ollama: string;
  providers: {
    ollama: ProviderStatus;
    openai: ProviderStatus;
    anthropic: ProviderStatus;
    gemini: ProviderStatus;
  };
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
  treaty_exempt_amount?: number | null;
  treaty_country?: string | null;
  needs_itin_guidance?: boolean;
  form_8843_data?: Form8843Data | null;
}

export interface SessionState {
  status: string;
}

export async function uploadDocument(
  file: File,
  aiApiKey?: string,
  aiModel?: string
): Promise<OCROutput> {
  const form = new FormData();
  form.append("file", file);
  if (aiApiKey) form.append("ai_api_key", aiApiKey);
  if (aiModel) form.append("ai_model", aiModel);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function saveContext(document_id: string, context: UserContext): Promise<void> {
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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60_000);
  try {
    const res = await fetch(`${API_BASE}/api/analyze/${document_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(preferences),
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Analysis failed");
    }
    return res.json();
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Analysis timed out after 60 seconds. Check your API key and try again.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
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

export async function checkHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

/**
 * Generate a single filled IRS Form 8843 PDF.
 * Returns a Blob ready for download.
 */
export async function generate8843(data: Form8843Data, year?: number): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/forms/8843/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data, year }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Form generation failed");
  }
  return res.blob();
}

/**
 * Bundle one Form 8843 per year (catch-up filing).
 * Returns a Blob containing a multi-page PDF with cover sheet.
 */
export async function bundleForms(
  baseData: Form8843Data,
  years: number[],
  includecover?: boolean
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/forms/bundle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      base_data: baseData,
      years,
      data_per_year: [],
      include_cover_sheet: includecover ?? true,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Bundle generation failed");
  }
  return res.blob();
}

/**
 * Download a complete tax filing package (cover + 1040NR + optional 8843).
 * Returns a Blob containing the bundled PDF.
 */
export async function downloadTaxPackage(documentId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/forms/package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: documentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Tax package generation failed");
  }
  return res.blob();
}

/**
 * Fetch per-provider model allow-lists from the backend.
 * Single source of truth — both validation and the SettingsStep picker
 * read from the same backend constant.
 * Returns null on network error so callers can fall back gracefully.
 */
export async function getProviderModels(): Promise<Record<string, string[]> | null> {
  try {
    const res = await fetch(`${API_BASE}/api/providers/models`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
