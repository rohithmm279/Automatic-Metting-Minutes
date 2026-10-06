"""Evaluate the two-pass product pipeline on a compact meeting-archetype set.

Run from the repository root:
    python eval_archetypes.py

The evaluator uses tests/fixtures/archetype_eval.json and requires Ollama with
qwen2.5:3b running locally. It reports per-case category F1 and intent leakage.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from backend.ai.orchestrator import MeetingOrchestrator

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tests" / "fixtures" / "archetype_eval.json"


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.lower()))


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _strings(output, field: str) -> list[str]:
    values = getattr(output, field)
    if field == "action_items":
        return [item.task for item in values]
    if field == "decisions":
        return [item.decision for item in values]
    return [item.issue for item in values]


def _matches(predicted: list[str], expected: list[str], threshold: float = 0.45) -> int:
    remaining = list(expected)
    count = 0
    for item in predicted:
        best = max(remaining, key=lambda ref: _similarity(item, ref), default=None)
        if best is not None and _similarity(item, best) >= threshold:
            remaining.remove(best)
            count += 1
    return count


def _f1(matches: int, predicted: int, expected: int) -> float:
    precision = matches / predicted if predicted else 0.0
    recall = matches / expected if expected else 0.0
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate two-pass meeting archetypes")
    parser.add_argument("--ids", nargs="*", help="Optional fixture IDs to run")
    args = parser.parse_args()

    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]
    orchestrator = MeetingOrchestrator(two_pass=True)
    results = []

    for case in cases:
        output = orchestrator.analyze(case["transcript"])
        scores = {}
        for field in ("action_items", "decisions", "unresolved_issues"):
            predicted = _strings(output, field)
            expected = case["ground_truth"][field]
            matches = _matches(predicted, expected)
            scores[field] = _f1(matches, len(predicted), len(expected))

        decisions = _strings(output, "decisions")
        issues = _strings(output, "unresolved_issues")
        leakage = sum(
            1 for decision in decisions
            if any(_similarity(decision, issue) >= 0.45 for issue in issues)
        )
        results.append({
            "id": case["id"],
            "expected_archetype": case["archetype"],
            "predicted_archetype": orchestrator.last_archetype,
            "archetype_correct": orchestrator.last_archetype == case["archetype"],
            "f1": scores,
            "decision_issue_leakage": leakage,
        })

    print(json.dumps({"cases": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
