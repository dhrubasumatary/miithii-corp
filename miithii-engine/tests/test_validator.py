"""Post-generation validation tests (ADR-004/005 guardrails)."""

import pytest

from app.domain import Action, DraftResult, PolicyDecision
from app.providers.validator import DraftValidationError, validate_draft


def _decision(action: Action) -> PolicyDecision:
    return PolicyDecision(action=action, flags=[])


def test_workflow_hallucination_rejected():
    with pytest.raises(DraftValidationError, match="workflow"):
        validate_draft(
            _decision(Action.HUMAN_REVIEW),
            DraftResult(answer="I have escalated your request to the security team."),
        )


def test_refusal_leaking_escalation_rejected():
    with pytest.raises(DraftValidationError, match="escalation"):
        validate_draft(
            _decision(Action.REFUSE),
            DraftResult(answer="I can't do that. Please contact our support team."),
        )


def test_clean_refusal_passes():
    result = validate_draft(
        _decision(Action.REFUSE),
        DraftResult(answer="I can't provide private credentials or internal-only information."),
    )
    assert result.answer


def test_empty_answer_rejected():
    with pytest.raises(DraftValidationError, match="empty"):
        validate_draft(_decision(Action.ANSWER), DraftResult(answer="  "))


def test_normal_answer_passes():
    result = validate_draft(
        _decision(Action.ANSWER),
        DraftResult(answer="Professional is priced at $39 per user/month."),
    )
    assert result.confidence >= 0.0
