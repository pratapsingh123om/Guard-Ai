"""Policy-backed risk classification for proposed tool calls."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any, Mapping

from backend.app.guardrails.base import Guardrail, GuardrailAction, GuardrailResult, Severity


class ActionRiskGuardrail(Guardrail):
    """
    Classifies tool calls by risk tier.
    """
    name = "risk_classifier_guardrail"
    category = "action"
    
    def __init__(self) -> None:
        policy_path = files("backend.app.policy").joinpath("policies.json")
        self.policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.blocked_patterns = tuple(
            (item["name"], re.compile(item["pattern"], re.IGNORECASE))
            for item in self.policy["blocked_argument_patterns"]
        )

    def check(self, context: Mapping[str, Any]) -> GuardrailResult:
        if not isinstance(context, Mapping):
            raise TypeError("action context must be a mapping")

        tool_name = str(context.get("tool", "")).strip()
        arguments = context.get("arguments", {})
        serialized_arguments = json.dumps(arguments, sort_keys=True, default=str)

        matches = tuple(
            name for name, pattern in self.blocked_patterns if pattern.search(serialized_arguments)
        )
        if matches:
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=False,
                action=GuardrailAction.BLOCK,
                severity=Severity.CRITICAL,
                reason=f"Blocked dangerous arguments for tool '{tool_name}'.",
                matched_rules=matches,
                metadata={"tool": tool_name},
            )

        tool_policy = self.policy["tools"].get(tool_name)
        if tool_policy is None:
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=False,
                action=GuardrailAction.BLOCK,
                severity=Severity.HIGH,
                reason=f"Tool '{tool_name}' is not present in the allowlist.",
                matched_rules=("unknown_tool",),
                metadata={"tool": tool_name, "risk": "unknown"},
            )

        risk = tool_policy["risk"]
        action = GuardrailAction(tool_policy["action"])
        severity = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }.get(risk, Severity.HIGH)

        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=action is GuardrailAction.ALLOW,
            action=action,
            severity=severity,
            reason=(
                f"Tool '{tool_name}' is allowed."
                if action is GuardrailAction.ALLOW
                else f"Tool '{tool_name}' requires approval."
            ),
            metadata={"tool": tool_name, "risk": risk},
        )


RiskClassifierGuardrail = ActionRiskGuardrail
