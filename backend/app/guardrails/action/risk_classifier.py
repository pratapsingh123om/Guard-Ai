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

    _destructive_intent_patterns = (
        re.compile(
            r"\b(?:delete|destroy|erase|wipe|purge|drop|truncate|remove)\b"
            r".{0,48}\b(?:all|everything|database|table|files?|records?|accounts?|users?|data)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:delete|destroy|erase|wipe|purge|drop|truncate|remove)\s+everything\b",
            re.IGNORECASE,
        ),
    )
    _financial_intent_pattern = re.compile(
        r"\b(?:pay|transfer|send)\b.{0,40}(?:\$|usd|eur|gbp|inr|money|funds?|payment)",
        re.IGNORECASE,
    )
    
    def __init__(self) -> None:
        policy_path = files("backend.app.policy").joinpath("policies.json")
        self.policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.blocked_patterns = tuple(
            (item["name"], re.compile(item["pattern"], re.IGNORECASE))
            for item in self.policy["blocked_argument_patterns"]
        )

    def check_message_intent(self, message: str) -> GuardrailResult | None:
        """Surface high-impact intent even when no structured tool call was supplied."""

        if any(pattern.search(message) for pattern in self._destructive_intent_patterns):
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=False,
                action=GuardrailAction.REQUIRE_APPROVAL,
                severity=Severity.CRITICAL,
                reason="Destructive natural-language intent requires explicit approval.",
                matched_rules=("destructive_intent",),
                metadata={"risk": "critical", "source": "natural_language"},
            )
        if self._financial_intent_pattern.search(message):
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=False,
                action=GuardrailAction.REQUIRE_APPROVAL,
                severity=Severity.CRITICAL,
                reason="Financial natural-language intent requires explicit approval.",
                matched_rules=("financial_intent",),
                metadata={"risk": "critical", "source": "natural_language"},
            )
        return None

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
