from backend.app.guardrails.base import Guardrail, GuardrailResult, GuardrailAction, Severity

class DocSanitizerGuardrail(Guardrail):
    """
    Sanitizes retrieved documents before they enter the LLM context window.
    """
    name = "doc_sanitizer_guardrail"
    category = "retrieval"
    
    def check(self, context: str) -> GuardrailResult:
        sanitized = f"--- START UNTRUSTED DATA ---\n{context}\n--- END UNTRUSTED DATA ---"
        
        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=True,
            action=GuardrailAction.SANITIZE,
            reason="Sanitized untrusted data",
            transformed_content=sanitized
        )
