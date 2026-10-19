"""Run the deterministic Guard-AI baseline and enforce release thresholds."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.guardrails.action import ActionRiskGuardrail
from backend.app.guardrails.input import PromptInjectionGuardrail
from backend.app.guardrails.output import SensitiveDataGuardrail
from backend.app.guardrails.retrieval import DocumentSanitizer
from eval.harness.scorer import score


DATASET_PATH = ROOT / "eval" / "datasets" / "baseline_cases.jsonl"
THRESHOLDS_PATH = ROOT / "eval" / "harness" / "thresholds.json"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_evals() -> int:
    guardrails = {
        "prompt_injection": PromptInjectionGuardrail(),
        "document_sanitizer": DocumentSanitizer(),
        "action_risk": ActionRiskGuardrail(),
        "sensitive_data": SensitiveDataGuardrail(),
    }
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for case in _load_jsonl(DATASET_PATH):
        result = guardrails[case["guardrail"]].check(case["context"])
        record = {
            **case,
            "actual_action": result.action.value,
            "actual_passed": result.passed,
        }
        records.append(record)
        if (
            record["actual_action"] != record["expected_action"]
            or record["actual_passed"] != record["expected_passed"]
        ):
            failures.append(
                f"{case['id']}: expected {case['expected_action']}/"
                f"{case['expected_passed']}, got {result.action.value}/{result.passed}"
            )

    metrics = score(records)
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    print("Guardrail              Cases  Accuracy  Recall  False-positive rate")
    print("---------------------  -----  --------  ------  -------------------")
    for name, values in metrics.items():
        print(
            f"{name:<21}  {values['cases']:>5}  {values['accuracy']:>8.1%}  "
            f"{values['recall']:>6.1%}  {values['false_positive_rate']:>19.1%}"
        )
        limits = thresholds[name]
        if values["recall"] < limits["min_recall"]:
            failures.append(
                f"{name}: recall {values['recall']:.1%} is below "
                f"{limits['min_recall']:.1%}"
            )
        if values["false_positive_rate"] > limits["max_false_positive_rate"]:
            failures.append(
                f"{name}: false-positive rate {values['false_positive_rate']:.1%} exceeds "
                f"{limits['max_false_positive_rate']:.1%}"
            )

    if failures:
        print("\nFAILED: release gate did not pass.")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"\nSUCCESS: all {len(records)} baseline cases passed their release thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_evals())
