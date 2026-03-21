"""TaxExplanationService — adds plain-English explanations to CalculationStep rows.

This service makes ONE LLM call for all steps at once (batch approach).
It never produces numbers. All arithmetic lives in tax_engine.py.

If the LLM call fails or returns invalid output, every step silently falls
back to a template explanation — the ledger still renders with correct numbers.

AI output validation:
  - Strip any response containing dollar amounts ($N) and use template.
  - If a step_number is missing from the response, use template for that step.
"""

import re
import json
from pathlib import Path
from typing import Optional
from app.schemas.document import AnalysisPreferences, CalculationStep, ConfirmedFields, ValidationOutput, TaxReport, UserContext
from app.services.llm_client import chat_json
from app.services.tax_engine import calculate

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Regex to detect dollar amounts the AI should not produce
_DOLLAR_RE = re.compile(r'\$\s*[\d,]+')


def _template_explanation(step: CalculationStep) -> str:
    if step.is_flag:
        return f"See {step.rule_reference} for the applicable exemption rule."
    return f"See {step.rule_reference} above."


async def run_tax_analysis(
    confirmed: ConfirmedFields,
    validation: ValidationOutput,
    user_context: Optional[UserContext] = None,
    preferences: Optional[AnalysisPreferences] = None,
) -> TaxReport:
    """Run the full analysis pipeline:
    1. TaxCalculationEngine computes deterministic steps (no LLM)
    2. TaxExplanationService adds plain-English explanations (one LLM call)
    3. Returns a TaxReport with all steps annotated
    """
    # Step 1: Deterministic calculation
    steps, outcome, amount = calculate(confirmed, user_context)

    if not steps:
        return TaxReport(
            document_id=confirmed.document_id,
            calculation_steps=[],
            estimated_outcome="unknown",
            estimated_amount=None,
            outcome_explanation="Required fields are missing. Please review the extracted fields and try again.",
            validation_results=validation.issues,
        )

    # Step 2: AI batch explanation (graceful fallback on any failure)
    steps = await _add_explanations(steps, preferences)

    # Build outcome explanation from the last non-flag step
    outcome_step = next((s for s in reversed(steps) if not s.is_flag), None)
    outcome_explanation = outcome_step.explanation if outcome_step and outcome_step.explanation else ""

    return TaxReport(
        document_id=confirmed.document_id,
        calculation_steps=steps,
        estimated_outcome=outcome,
        estimated_amount=amount,
        outcome_explanation=outcome_explanation,
        validation_results=validation.issues,
    )


async def _add_explanations(
    steps: list[CalculationStep],
    preferences: Optional[AnalysisPreferences] = None,
) -> list[CalculationStep]:
    """Call the LLM once to get explanations for all steps.

    Returns steps with .explanation filled.
    Falls back silently to template text on any error.
    """
    system_prompt = (PROMPTS_DIR / "tax_analysis.txt").read_text()
    steps_payload = [
        {
            "step_number": s.step_number,
            "label": s.label,
            "rule_reference": s.rule_reference,
            "input_value": s.input_value,
            "output_value": s.output_value,
            "is_flag": s.is_flag,
        }
        for s in steps
    ]
    user_content = json.dumps(steps_payload, indent=2)

    try:
        data = await chat_json(
            preferences.model if preferences else None,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.0,
            provider=preferences.provider if preferences else "ollama",
        )
    except Exception:
        # LLM unavailable — fall back to templates for all steps
        return [s.model_copy(update={"explanation": _template_explanation(s)}) for s in steps]

    # Validate and merge explanations
    result = []
    for step in steps:
        raw_explanation = data.get(str(step.step_number), "")

        # Strip any response that contains dollar amounts the AI should not produce
        if _DOLLAR_RE.search(raw_explanation):
            raw_explanation = ""

        explanation = raw_explanation.strip() or _template_explanation(step)
        result.append(step.model_copy(update={"explanation": explanation}))

    return result
