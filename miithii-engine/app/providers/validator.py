"""Post-generation validation (ported from the supportpilot reference).

The policy decision is code; a draft that claims workflow actions happened,
leaks escalation language in a hard refusal, or is empty is rejected and the
pipeline falls back to the deterministic provider.
"""

from app.domain import Action, DraftResult, PolicyDecision


class DraftValidationError(ValueError):
    """Raised when a draft violates policy-derived content rules."""


WORKFLOW_CLAIMS: tuple[str, ...] = (
    "i have escalated",
    "i've escalated",
    "we have escalated",
    "we've escalated",
    "your request has been escalated",
    "your ticket has been escalated",
    "this ticket has been escalated",
    "has been escalated to",
    "has been sent to the security team",
    "has been sent to the support team",
    "the security team has been notified",
    "the support team has been notified",
    "will contact you",
    "has been refunded",
    "has been revoked",
    "has been rotated",
    "ownership has been changed",
)

# A hard REFUSE must not imply review/escalation exists as an option.
REFUSAL_ESCALATION_LANGUAGE: tuple[str, ...] = (
    "requires review",
    "requires human review",
    "human review",
    "security team",
    "support team",
    "escalate",
    "escalated",
)


def validate_draft(decision: PolicyDecision, draft: DraftResult) -> DraftResult:
    answer = draft.answer or ""
    if not answer.strip():
        raise DraftValidationError("empty draft")

    lowered = answer.lower()
    for phrase in WORKFLOW_CLAIMS:
        if phrase in lowered:
            raise DraftValidationError(f"workflow-hallucination claim: {phrase!r}")

    if decision.action == Action.REFUSE:
        for phrase in REFUSAL_ESCALATION_LANGUAGE:
            if phrase in lowered:
                raise DraftValidationError(f"refusal leaks escalation language: {phrase!r}")

    return draft
