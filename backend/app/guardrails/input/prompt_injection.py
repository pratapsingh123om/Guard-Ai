"""Deterministic prompt-injection checks used by runtime and evaluations."""

from __future__ import annotations

import re
import unicodedata

from backend.app.guardrails.base import Guardrail, GuardrailAction, GuardrailResult, Severity

class PromptInjectionGuardrail(Guardrail):
    """
    Detects potential prompt injection attacks in user input.
    """
    name = "prompt_injection_guardrail"
    category = "input"

    BLOCK_PATTERNS = {
        "instruction_override": re.compile(
            r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:the\s+)?"
            r"(?:previous|prior|system)\s+(?:system\s+)?"
            r"(?:instructions?|prompts?|rules?)\b",
            re.IGNORECASE,
        ),
        "prompt_exfiltration": re.compile(
            r"\b(?:reveal|show|print|repeat|expose)\b.{0,60}\b(?:system|developer|hidden)\s+prompt\b",
            re.IGNORECASE,
        ),
        "role_override": re.compile(r"\byou\s+are\s+now\s+(?:a|an|the)\b", re.IGNORECASE),
        "safety_bypass": re.compile(
            r"\b(?:bypass|disable|circumvent|turn\s+off)\b.{0,40}"
            r"\b(?:safety|security|guardrails?|policy|filter)\b",
            re.IGNORECASE,
        ),
    }
    FLAG_PATTERNS = {
        "spoofed_instruction_boundary": re.compile(
            r"^\s*\[(?:system|developer|assistant)\]", re.IGNORECASE
        )
    }

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        return "".join(
            char for char in normalized if unicodedata.category(char) != "Cf"
        )

    def check(self, context: str) -> GuardrailResult:
        if not isinstance(context, str):
            raise TypeError("input context must be a string")

        normalized = self._normalize(context)
        metadata = {"normalized_changed": normalized != context}

        for rule, pattern in self.BLOCK_PATTERNS.items():
            if pattern.search(normalized):
                return GuardrailResult(
                    guardrail=self.name,
                    category=self.category,
                    passed=False,
                    action=GuardrailAction.BLOCK,
                    severity=Severity.HIGH,
                    reason=f"Detected prompt-injection pattern: {rule}.",
                    matched_rules=(rule,),
                    metadata=metadata,
                )

        for rule, pattern in self.FLAG_PATTERNS.items():
            if pattern.search(normalized):
                return GuardrailResult(
                    guardrail=self.name,
                    category=self.category,
                    passed=False,
                    action=GuardrailAction.FLAG,
                    severity=Severity.MEDIUM,
                    reason=f"Flagged suspicious instruction boundary: {rule}.",
                    matched_rules=(rule,),
                    metadata=metadata,
                )

        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=True,
            action=GuardrailAction.ALLOW,
            reason="Input appears safe.",
            metadata=metadata,
        )
