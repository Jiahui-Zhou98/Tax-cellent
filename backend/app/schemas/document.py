from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum


class UserContext(BaseModel):
    visa_type: str = "unknown"
    first_us_entry_date: Optional[str] = None
    current_year_days_in_us: Optional[int] = None
    prior_year_days_in_us: Optional[int] = None
    second_prior_year_days_in_us: Optional[int] = None
    has_1042s: bool = False
    wants_state_estimate: bool = False
    claims_exempt_individual: bool = False


class FormType(str, Enum):
    W2 = "W-2"
    NEC_1099 = "1099-NEC"
    INT_1099 = "1099-INT"
    UNKNOWN = "UNKNOWN"


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
    status: str = "uploaded"
    # status values: uploaded | ocr_done | confirmed | validated | analyzing | complete
