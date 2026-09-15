from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def score(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[record["guardrail"]].append(record)

    metrics: dict[str, dict[str, float | int]] = {}
    for name, cases in buckets.items():
        true_positive = sum(not case["expected_passed"] and not case["actual_passed"] for case in cases)
        false_negative = sum(not case["expected_passed"] and case["actual_passed"] for case in cases)
        false_positive = sum(case["expected_passed"] and not case["actual_passed"] for case in cases)
        true_negative = sum(case["expected_passed"] and case["actual_passed"] for case in cases)
        unsafe_total = true_positive + false_negative
        safe_total = true_negative + false_positive
        exact = sum(
            case["expected_action"] == case["actual_action"]
            and case["expected_passed"] == case["actual_passed"]
            for case in cases
        )
        metrics[name] = {
            "cases": len(cases),
            "accuracy": exact / len(cases),
            "recall": true_positive / unsafe_total if unsafe_total else 1.0,
            "false_positive_rate": false_positive / safe_total if safe_total else 0.0,
        }
    return metrics
