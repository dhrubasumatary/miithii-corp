"""Zero-cost deterministic provider — safe fallback and eval baseline (ADR-006).

Never touches the network. Its drafts are policy-action-shaped and pass the
validator by construction; used when the LLM provider errors, when validation
rejects an LLM draft, and for the deterministic golden-set eval in CI.
"""

from app.domain import Action, ClassifierResult, DraftContext, DraftResult, PolicyDecision
from app.providers.base import Provider
from app.providers.validator import validate_draft


class DeterministicProvider(Provider):
    async def classify(self, subject: str, body: str) -> ClassifierResult | None:
        return None  # pipeline keeps the keyword pre-pass result

    async def draft(self, context: DraftContext) -> DraftResult:
        action = context.action
        flags = set(context.flags)

        if action == Action.REFUSE_AND_GUIDE:
            if "secret_protection" in flags or "secret_request" in flags or "no_passwords" in flags:
                answer = (
                    "For security reasons we can't provide or retrieve existing passwords "
                    "or private API keys. Please revoke the lost or exposed credential and "
                    "generate a replacement in your account settings."
                )
            else:
                answer = (
                    "I can't fulfill this request directly, but I can guide you through "
                    "the supported process for it."
                )
        elif action == Action.REFUSE:
            answer = (
                "I can't provide private credentials or internal-only information. "
                "I can help with the supported customer-facing process instead."
            )
        elif action in {Action.HUMAN_REVIEW, Action.ESCALATE, Action.REFUSE_AND_ESCALATE}:
            answer = (
                "This request needs to be reviewed by the appropriate team because it "
                "involves a sensitive or exceptional case."
            )
        elif action == Action.CLARIFY:
            answer = (
                "I need a little more information to help with this. Please share the "
                "relevant error code, the affected feature, and any recent changes — "
                "please don't include passwords or private API keys."
            )
        else:
            answer = (
                "Thanks for reaching out. Here's what will help with this request: "
                "the details you've shared point to our standard process, and I've "
                "outlined the relevant steps below once your account context is confirmed."
            )

        result = DraftResult(answer=answer, confidence=1.0)
        return validate_draft(PolicyDecision(action=action, flags=list(flags)), result)
