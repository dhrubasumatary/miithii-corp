"""ADR-004: the policy decision is deterministic code, never the LLM.

Priority-ordered tag rules ported from the supportpilot reference engine.
Per-tenant overrides live in tenants.policy_config (JSONB):
    {"tag_actions": {"outage": {"action": "human_review", "requires_human": true}}}
Unknown/missing tags fall through to ANSWER; `ambiguous` routes to CLARIFY.
"""

from app.domain import Action, PolicyDecision

# (tag, action, requires_human) — first match wins.
_DEFAULT_RULES: list[tuple[str, Action, bool]] = [
    ("security_incident", Action.ESCALATE, True),
    ("destructive_action", Action.HUMAN_REVIEW, True),
    ("contractual_exception", Action.HUMAN_REVIEW, True),
    ("billing_exception", Action.HUMAN_REVIEW, True),
    ("refund_exception", Action.HUMAN_REVIEW, True),
    ("outage", Action.HUMAN_REVIEW, True),
    # prompt injection beats generic secret handling: never follow overrides.
    ("prompt_injection", Action.REFUSE, False),
    ("secret_request", Action.REFUSE_AND_GUIDE, False),
    ("no_passwords", Action.REFUSE_AND_GUIDE, False),
    # constraints on an otherwise answerable request:
    ("secret_protection", Action.ANSWER, False),
    ("no_secrets", Action.ANSWER, False),
    ("ambiguous", Action.CLARIFY, False),
]

# identity_verification has a two-tag split handled explicitly below.


class PolicyEngine:
    def evaluate(self, tags: list[str], tenant_config: dict | None = None) -> PolicyDecision:
        tag_set = {t for t in tags if t}
        overrides = (tenant_config or {}).get("tag_actions", {})

        def _resolve(tag: str, action: Action, requires_human: bool) -> PolicyDecision:
            override = overrides.get(tag)
            if isinstance(override, dict):
                action = Action(override.get("action", action.value))
                requires_human = bool(override.get("requires_human", requires_human))
            return PolicyDecision(action=action, requires_human=requires_human, flags=[tag])

        if "identity_verification" in tag_set:
            if "verification_bypass" in tag_set:
                return PolicyDecision(
                    action=Action.REFUSE_AND_ESCALATE,
                    requires_human=True,
                    flags=["identity_verification", "verification_bypass"],
                )
            return _resolve("identity_verification", Action.HUMAN_REVIEW, True)

        for tag, action, requires_human in _DEFAULT_RULES:
            if tag in tag_set:
                return _resolve(tag, action, requires_human)

        return PolicyDecision(action=Action.ANSWER, requires_human=False, flags=[])
