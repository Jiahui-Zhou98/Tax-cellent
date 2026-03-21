"""Orchestrate the dual-model review and cross-review pipeline."""
from pathlib import Path
from typing import Optional
from app.schemas.document import (
    ConfirmedFields, ValidationOutput,
    ReviewResult, CrossReviewResult, FinalReport, UserContext,
)
from app.services.llm_client import chat_json
from app.core.config import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _coerce_str_list(raw: list) -> list[str]:
    """Ensure every element is a string — LLMs sometimes return dicts instead."""
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Try common keys first, then fall back to joining all values
            text = (
                item.get("item")
                or item.get("description")
                or item.get("text")
                or "; ".join(str(v) for v in item.values() if v)
            )
            result.append(str(text))
        else:
            result.append(str(item))
    return result


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def _fields_summary(confirmed: ConfirmedFields) -> str:
    lines = [f"Document ID: {confirmed.document_id}"]
    for fname, fval in confirmed.confirmed_fields.items():
        if fval.value:
            lines.append(f"  {fname}: {fval.value} (source: {fval.source})")
    if confirmed.unresolved_fields:
        lines.append(f"  UNRESOLVED: {', '.join(confirmed.unresolved_fields)}")
    return "\n".join(lines)


def _context_summary(ctx: Optional[UserContext]) -> str:
    if not ctx:
        return ""
    lines = ["\nUSER IMMIGRATION/RESIDENCY CONTEXT:"]
    lines.append(f"  Visa type: {ctx.visa_type}")
    if ctx.first_us_entry_date:
        lines.append(f"  First US entry (student/exchange status): {ctx.first_us_entry_date}")
    if ctx.current_year_days_in_us is not None:
        lines.append(f"  Days in US (current tax year): {ctx.current_year_days_in_us}")
    if ctx.prior_year_days_in_us is not None:
        lines.append(f"  Days in US (prior year): {ctx.prior_year_days_in_us}")
    if ctx.second_prior_year_days_in_us is not None:
        lines.append(f"  Days in US (2nd prior year): {ctx.second_prior_year_days_in_us}")
    lines.append(f"  Has Form 1042-S: {ctx.has_1042s}")
    lines.append(f"  Claims exempt individual status: {ctx.claims_exempt_individual}")
    lines.append(f"  Wants state tax estimate: {ctx.wants_state_estimate}")
    return "\n".join(lines)


async def run_independent_review(
    confirmed: ConfirmedFields,
    model_name: str,
    model_label: str,
    user_context: Optional[UserContext] = None,
) -> ReviewResult:
    system_prompt = _load_prompt("independent_review.txt")
    user_content = (
        f"Here are the confirmed tax document fields:\n\n"
        f"{_fields_summary(confirmed)}"
        f"{_context_summary(user_context)}"
    )

    data = await chat_json(model_name, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ])

    return ReviewResult(
        model=model_label,
        summary=data.get("summary", ""),
        agreed_facts=data.get("agreed_facts", []),
        risk_flags=data.get("risk_flags", []),
        uncertain_items=data.get("uncertain_items", []),
        recommendations=data.get("recommendations", []),
    )


async def run_cross_review(
    review_a: ReviewResult,
    review_b: ReviewResult
) -> CrossReviewResult:
    system_prompt = _load_prompt("cross_review.txt")

    review_a_text = (
        f"REVIEWER A ({review_a.model}):\n"
        f"Summary: {review_a.summary}\n"
        f"Risk flags: {review_a.risk_flags}\n"
        f"Uncertain: {review_a.uncertain_items}\n"
        f"Recommendations: {review_a.recommendations}"
    )
    review_b_text = (
        f"REVIEWER B ({review_b.model}):\n"
        f"Summary: {review_b.summary}\n"
        f"Risk flags: {review_b.risk_flags}\n"
        f"Uncertain: {review_b.uncertain_items}\n"
        f"Recommendations: {review_b.recommendations}"
    )

    data = await chat_json(settings.ARBITER_MODEL, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{review_a_text}\n\n{review_b_text}"},
    ])

    return CrossReviewResult(
        agreements=data.get("agreements", []),
        disagreements=data.get("disagreements", []),
        insufficient_evidence=data.get("insufficient_evidence", []),
    )


async def compile_final_report(
    document_id: str,
    confirmed: ConfirmedFields,
    validation: ValidationOutput,
    review_a: ReviewResult,
    review_b: ReviewResult,
    cross_review: CrossReviewResult,
) -> FinalReport:
    system_prompt = _load_prompt("final_arbiter.txt")

    context = (
        f"CONFIRMED FIELDS:\n{_fields_summary(confirmed)}\n\n"
        f"VALIDATION: {validation.status}, issues: {[i.message for i in validation.issues]}\n\n"
        f"MODEL A REVIEW: summary={review_a.summary}, "
        f"risks={review_a.risk_flags}, uncertain={review_a.uncertain_items}\n\n"
        f"MODEL B REVIEW: summary={review_b.summary}, "
        f"risks={review_b.risk_flags}, uncertain={review_b.uncertain_items}\n\n"
        f"CROSS REVIEW: agreements={cross_review.agreements}, "
        f"disagreements={cross_review.disagreements}"
    )

    data = await chat_json(settings.ARBITER_MODEL, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ])

    return FinalReport(
        document_id=document_id,
        confirmed_facts=_coerce_str_list(data.get("confirmed_facts", [])),
        validation_results=validation.issues,
        agreed_conclusions=_coerce_str_list(data.get("agreed_conclusions", [])),
        disputed_items=_coerce_str_list(data.get("disputed_items", [])),
        manual_review_needed=_coerce_str_list(data.get("manual_review_needed", [])),
        model_a_review=review_a,
        model_b_review=review_b,
        cross_review=cross_review,
        estimated_outcome=data.get("estimated_outcome", "unknown"),
        estimated_amount=data.get("estimated_amount"),
        outcome_explanation=data.get("outcome_explanation", ""),
    )
