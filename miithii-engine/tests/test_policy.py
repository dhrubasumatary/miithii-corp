"""PolicyEngine decision-table tests (ADR-004 semantics)."""

import pytest

from app.policy import PolicyEngine

CASES = [
    (["security_incident"], "escalate", True),
    (["destructive_action"], "human_review", True),
    (["contractual_exception"], "human_review", True),
    (["billing_exception"], "human_review", True),
    (["refund_exception"], "human_review", True),
    (["outage"], "human_review", True),
    (["prompt_injection"], "refuse", False),
    (["secret_request"], "refuse_and_guide", False),
    (["no_passwords"], "refuse_and_guide", False),
    (["secret_protection"], "answer", False),
    (["no_secrets"], "answer", False),
    (["ambiguous"], "clarify", False),
    ([], "answer", False),
]


@pytest.mark.parametrize(("tags", "action", "requires_human"), CASES)
def test_decision_table(tags, action, requires_human):
    decision = PolicyEngine().evaluate(tags, {})
    assert decision.action.value == action
    assert decision.requires_human is requires_human


def test_verification_bypass_hardens_identity():
    decision = PolicyEngine().evaluate(["identity_verification", "verification_bypass"], {})
    assert decision.action.value == "refuse_and_escalate"
    assert decision.requires_human is True


def test_security_incident_beats_other_tags():
    decision = PolicyEngine().evaluate(["billing_exception", "security_incident"], {})
    assert decision.action.value == "escalate"


def test_tenant_override_remaps_action():
    decision = PolicyEngine().evaluate(
        ["outage"], {"tag_actions": {"outage": {"action": "escalate", "requires_human": True}}}
    )
    assert decision.action.value == "escalate"
    assert decision.requires_human is True


def test_override_ignores_unknown_tags():
    decision = PolicyEngine().evaluate(
        ["outage"], {"tag_actions": {"nonsense": {"action": "refuse"}}}
    )
    assert decision.action.value == "human_review"
