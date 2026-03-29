from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum

from app.schemas.form_8843 import Form8843Data  # noqa: F401 — used in TaxReport


class UserContext(BaseModel):
    visa_type: str = "unknown"
    first_us_entry_date: Optional[str] = None
    current_year_days_in_us: Optional[int] = None
    prior_year_days_in_us: Optional[int] = None
    second_prior_year_days_in_us: Optional[int] = None
    has_1042s: bool = False
    wants_state_estimate: bool = False
    state_code: Optional[str] = None  # 2-letter state code: CA, NY, TX, WA, IL, MA (or None)
    claims_exempt_individual: bool = False
    nec_business_expenses: Optional[float] = None  # Schedule C deductible expenses for 1099-NEC filers
    country_of_origin: Optional[str] = None  # ISO 2-letter code, used for treaty lookup (Exp 2)
    # Academic institution — collected in ContextStep (for NRA visa types) and
    # ZeroIncomeStep; pre-populated in ZeroIncomeStep from page.tsx context state.
    institution_name: Optional[str] = None   # Form 8843 Part I Line 4a
    institution_city: Optional[str] = None   # Form 8843 Part I Line 4b
    institution_state: Optional[str] = None  # Form 8843 Part I Line 4c (2-letter)


class FormType(str, Enum):
    W2 = "W-2"
    NEC_1099 = "1099-NEC"
    INT_1099 = "1099-INT"
    FORM_1042S = "1042-S"
    MISC_1099 = "1099-MISC"
    COMBINED = "COMBINED"
    UNKNOWN = "UNKNOWN"


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class AnalysisPreferences(BaseModel):
    provider: LLMProvider = LLMProvider.OLLAMA
    model: Optional[str] = None
    api_key: Optional[str] = None  # Inline key — takes precedence over env var; never logged


class FieldValue(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0
    source: str = "ocr"  # ocr | user_confirmed | user_edited


class OCROutput(BaseModel):
    document_id: str
    raw_text: str
    field_candidates: dict[str, FieldValue]
    page_count: int


class ConfirmedFields(BaseModel):
    document_id: str
    confirmed_fields: dict[str, FieldValue]
    unresolved_fields: list[str] = []


class ValidationIssue(BaseModel):
    field: str
    type: str  # missing | invalid_format | conflict | suspicious
    message: str
    severity: str = "warning"  # warning | error


class ValidationOutput(BaseModel):
    status: str  # ok | warning | error
    issues: list[ValidationIssue] = []


class CalculationStep(BaseModel):
    """One row in the Calculation Ledger shown on the final report.

    Numbers come from TaxCalculationEngine (deterministic Python).
    The `explanation` field is filled by TaxExplanationService (one LLM call).
    The LLM must never introduce new numeric values — only cite the rule.
    """
    step_number: int
    label: str            # e.g. "Federal Tax Liability"
    rule_reference: str   # e.g. "IRS Rev. Proc. 2024-40, Table 1"
    input_value: str      # e.g. "$37,400 taxable income"
    output_value: str     # e.g. "$4,328 federal tax"
    explanation: str = "" # plain-English, filled by AI after engine runs
    is_flag: bool = False # True for FICA exemption flags and other alerts
    source_form: str = "" # "W-2" | "1099-NEC" | "1099-INT" — used by frontend for per-form card routing


class TaxReport(BaseModel):
    """Final report returned by /api/analyze/{document_id}.

    # Data flow:
    #   ConfirmedFields + UserContext
    #         ↓
    #   TaxCalculationEngine.calculate()    ← pure Python, no LLM
    #         ↓
    #   list[CalculationStep]               ← deterministic, citable
    #         ↓
    #   TaxExplanationService.explain()     ← one LLM call
    #         ↓
    #   CalculationStep.explanation         ← AI plain-English, no numbers
    #         ↓
    #   TaxReport                           ← assembled and returned
    """
    document_id: str
    calculation_steps: list[CalculationStep] = []
    estimated_outcome: str = "unknown"  # refund | owe | balanced | unknown
    estimated_amount: Optional[float] = None
    outcome_explanation: str = ""
    validation_results: list[ValidationIssue] = []
    treaty_exempt_amount: Optional[float] = None  # > 0 triggers Form 8833 advisory (Exp 2)
    treaty_country: Optional[str] = None           # Country name for the 8833 advisory
    treaty_article: Optional[str] = None           # Treaty article citation, e.g. "Art. XXI"
    needs_itin_guidance: bool = False               # True when F-1/J-1/OPT + no SSN detected
    form_8843_data: Optional[Form8843Data] = None   # populated for NRA visa types; triggers Form8843Card
    # 1040NR export fields — populated by compute_report_extras() in tax_engine.py
    wages: Optional[float] = None                  # W-2 Box 1 ONLY (None for NEC filers)
    gross_income: Optional[float] = None           # NEC Box 1 ONLY (None for W-2 filers)
    withholding: Optional[float] = None            # Federal income tax withheld (W-2 Box 2 / NEC Box 4)


class SessionState(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    document_id: str
    filename: str
    file_path: str
    ocr_output: Optional[OCROutput] = None
    user_context: Optional[UserContext] = None
    confirmed_fields: Optional[ConfirmedFields] = None
    validation_output: Optional[ValidationOutput] = None
    tax_report: Optional[TaxReport] = None
    analysis_preferences: Optional[AnalysisPreferences] = None
    status: str = "uploaded"
    # status values: uploaded | ocr_done | confirmed | validated | analyzing | complete


MAX_DOCUMENTS_PER_BUNDLE = 10


class AggregatedFields(BaseModel):
    """Result of merging N confirmed documents into a single ConfirmedFields
    ready for the existing tax engine. bundle_id is stored as the document_id
    sentinel inside confirmed_fields so the existing analyze endpoint is unchanged.
    """
    bundle_id: str
    source_document_ids: list[str]
    confirmed_fields: ConfirmedFields     # merged, ready for tax engine
    aggregation_log: list[str] = []       # human-readable merge steps (debug)


class DocumentBundle(BaseModel):
    """Session-level container holding N documents being processed together.

    documents stores document_ids (not embedded SessionState) to keep bundle
    files small regardless of how many pages each document contains.

    Status state machine:
        uploading → all_confirmed → aggregated → complete
                 ↘ error (from any state)
    """
    bundle_id: str
    document_ids: list[str] = []
    aggregated_fields: Optional[AggregatedFields] = None
    tax_report: Optional[TaxReport] = None
    status: str = "uploading"
    # "primary" document = document_ids[0]; used for non-aggregatable fields
    # (visa_type, employer_state) when a single value must be chosen.
