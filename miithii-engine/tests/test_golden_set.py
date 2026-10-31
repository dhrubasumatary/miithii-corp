"""Golden-set eval: keyword pre-pass -> PolicyEngine on the 50 CloudDesk tickets.

Deterministic, no network, no DB — runs in CI. This measures the CLASSIFIER
(and policy routing), honestly — unlike supportpilot's benchmark, which fed
labeled tags straight into the policy engine and called it 100%.
The measured baseline is asserted with slack; tighten as the classifier improves.
"""

import json
from pathlib import Path

from app.classifier import KeywordClassifier
from app.policy import PolicyEngine

GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden_set.json"


def test_golden_set_routing_accuracy():
    tickets = json.loads(GOLDEN.read_text())
    assert len(tickets) == 50

    classifier = KeywordClassifier()
    policy = PolicyEngine()
    action_correct = 0
    escalation_correct = 0
    misses = []

    for ticket in tickets:
        result = classifier.classify(ticket["subject"], ticket["message"])
        decision = policy.evaluate(result.tags, {})
        if decision.action.value == ticket["expected_action"]:
            action_correct += 1
        else:
            misses.append((ticket["id"], ticket["expected_action"], decision.action.value))
        if decision.requires_human == ticket["should_escalate"]:
            escalation_correct += 1

    action_accuracy = action_correct / len(tickets)
    escalation_accuracy = escalation_correct / len(tickets)

    print()
    print(f"golden set action accuracy:     {action_correct}/50 ({action_accuracy:.0%})")
    print(f"golden set escalation accuracy: {escalation_correct}/50 ({escalation_accuracy:.0%})")
    print(f"action misses: {misses}")

    assert action_accuracy >= 0.70, f"golden set regression: {misses}"
    assert escalation_accuracy >= 0.80
