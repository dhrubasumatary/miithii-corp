"""Deterministic-mode benchmark runner for the supportpilot harness.

Runs the full CloudDesk dataset through the existing TicketAnalyzer in
deterministic mode (DeterministicProvider, no network) and writes the
results file the Gemini benchmark was designed to produce.

Throwaway tooling for the de-risk task (2026-10-31). Caveat carried from
analysis: the eval path retrieves the tickets' LABELED required_sources,
so this measures plumbing (policy routing + validation), not retrieval.

Usage (from anywhere):
    python spike/run_deterministic_benchmark.py
"""

import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_ENGINE = REPO_ROOT / "supportpilot" / "services" / "ai-engine"
sys.path.insert(0, str(AI_ENGINE))

from app.pipeline.analyze_ticket import create_analyzer  # noqa: E402

OUT_FILE = Path(__file__).parent / "results" / "deterministic_benchmark.json"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def main() -> None:
    analyzer = create_analyzer(REPO_ROOT / "supportpilot")
    tickets = analyzer.knowledge_base.load_tickets()

    results = {"mode": "deterministic", "tickets": {}}
    latencies: list[float] = []
    correct = 0
    escalation_correct = 0

    for number, ticket in enumerate(tickets, start=1):
        start = time.perf_counter()
        try:
            result = analyzer.analyze(ticket.id)
            latency = time.perf_counter() - start
            latencies.append(latency)
            action_correct = result.action == ticket.expected_action
            esc_correct = result.requires_human == ticket.should_escalate
            correct += action_correct
            escalation_correct += esc_correct
            results["tickets"][ticket.id] = {
                "status": "success",
                "expected_action": ticket.expected_action.value,
                "actual_action": result.action.value,
                "action_correct": action_correct,
                "escalation_correct": esc_correct,
                "latency_seconds": latency,
                "answer": result.answer,
            }
            print(f"[{number:02d}/50] {ticket.id} PASS {latency:.4f}s")
        except Exception as exc:  # noqa: BLE001 - benchmark records all failures
            latency = time.perf_counter() - start
            results["tickets"][ticket.id] = {
                "status": "error",
                "error": repr(exc),
                "latency_seconds": latency,
            }
            print(f"[{number:02d}/50] {ticket.id} ERROR {exc}")

    n = len(tickets)
    summary = {
        "total_tickets": n,
        "action_accuracy": correct / n if n else 0.0,
        "escalation_accuracy": escalation_correct / n if n else 0.0,
        "avg_latency_seconds": statistics.mean(latencies) if latencies else 0.0,
        "p50_latency_seconds": percentile(latencies, 0.50),
        "p95_latency_seconds": percentile(latencies, 0.95),
    }
    results["summary"] = summary

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(results, indent=2, sort_keys=True))

    print()
    print("=" * 60)
    print("DETERMINISTIC BENCHMARK (no network, no provider key)")
    print("=" * 60)
    print(f"Tickets:              {n}")
    print(f"Action accuracy:      {correct}/{n} ({summary['action_accuracy']:.1%})")
    print(
        f"Escalation accuracy:  {escalation_correct}/{n} "
        f"({summary['escalation_accuracy']:.1%})"
    )
    print(f"Avg latency:          {summary['avg_latency_seconds']*1000:.2f} ms")
    print(f"P50 latency:          {summary['p50_latency_seconds']*1000:.2f} ms")
    print(f"P95 latency:          {summary['p95_latency_seconds']*1000:.2f} ms")
    print(f"Results file:         {OUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
