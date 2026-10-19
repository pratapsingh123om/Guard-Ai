"""Sanitize retrieved content and mark it as untrusted data."""

from __future__ import annotations

import re
from typing import Any

from backend.app.guardrails.base import Guardrail, GuardrailAction, GuardrailResult, Severity


_HIDDEN_HTML = re.compile(r"<!--.*?-->", re.DOTALL)


class DocumentSanitizer(Guardrail):
    """
    Sanitizes retrieved documents before they enter the LLM context window.
    """
    name = "doc_sanitizer_guardrail"
    category = "retrieval"

    def __init__(self, input_guardrail: Any | None = None) -> None:
        self.input_guardrail = input_guardrail
    
    def check(self, context: str) -> GuardrailResult:
        if not isinstance(context, str):
            raise TypeError("document context must be a string")

        visible, removed_hidden_blocks = _HIDDEN_HTML.subn("", context)
        visible = visible.strip()
        sanitized = f"<untrusted_reference>\n{visible}\n</untrusted_reference>"

        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=removed_hidden_blocks == 0,
            action=GuardrailAction.SANITIZE,
            severity=Severity.HIGH if removed_hidden_blocks else Severity.INFO,
            reason=(
                "Removed hidden content and wrapped the remaining document as untrusted data."
                if removed_hidden_blocks
                else "Wrapped retrieved content as untrusted data."
            ),
            matched_rules=("hidden_html_comment",) if removed_hidden_blocks else (),
            transformed_content=sanitized,
            metadata={"removed_hidden_blocks": removed_hidden_blocks},
        )


DocSanitizerGuardrail = DocumentSanitizer
