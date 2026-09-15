"""Dependency-light redaction for common PII and secret formats."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailResult,
    Severity,
)


@dataclass(frozen=True)
class _EntityPattern:
    name: str
    pattern: re.Pattern[str]
    replacement: str


_PATTERNS = (
    _EntityPattern(
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    _EntityPattern(
        "api_key",
        re.compile(
            r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
            r"AKIA[0-9A-Z]{16})\b"
        ),
        "[REDACTED_API_KEY]",
    ),
    _EntityPattern(
        "email",
        re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
        "[REDACTED_EMAIL]",
    ),
    _EntityPattern(
        "ssn",
        re.compile(r"(?<!\d)(?!000|666|9\d\d)\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}(?!\d)"),
        "[REDACTED_SSN]",
    ),
    _EntityPattern(
        "phone",
        re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{2,4}\)|\d{2,4})[ .-]\d{3,4}[ .-]\d{4}(?!\w)"),
        "[REDACTED_PHONE]",
    ),
)

_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _passes_luhn(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


class SensitiveDataGuardrail(Guardrail):
    name = "sensitive_data"
    category = "output"

    def check(self, context: str) -> GuardrailResult:
        if not isinstance(context, str):
            raise TypeError("output context must be a string")

        counts: dict[str, int] = {}

        def redact_card(match: re.Match[str]) -> str:
            value = match.group(0)
            if _passes_luhn(value):
                counts["credit_card"] = counts.get("credit_card", 0) + 1
                return "[REDACTED_CREDIT_CARD]"
            return value

        # Cards must be handled before phone numbers because their grouped digit
        # formats overlap. Luhn validation keeps ordinary long IDs untouched.
        transformed = _CARD_CANDIDATE.sub(redact_card, context)
        for entity in _PATTERNS:
            transformed, count = entity.pattern.subn(entity.replacement, transformed)
            if count:
                counts[entity.name] = count
        detected = bool(counts)

        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=not detected,
            action=GuardrailAction.REDACT if detected else GuardrailAction.ALLOW,
            reason=(
                "Redacted sensitive data before returning the response."
                if detected
                else "No supported sensitive-data pattern was detected."
            ),
            severity=Severity.CRITICAL if {"private_key", "api_key"} & counts.keys() else (
                Severity.HIGH if detected else Severity.INFO
            ),
            score=1.0 if detected else 0.0,
            matched_rules=tuple(sorted(counts)),
            transformed_content=transformed,
            metadata={"entity_counts": counts},
        )
