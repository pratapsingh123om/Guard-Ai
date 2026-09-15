from backend.app.guardrails.base import Guardrail, GuardrailResult, GuardrailAction, Severity

class PromptInjectionGuardrail(Guardrail):
    """
    Detects potential prompt injection attacks in user input.
    """
    name = "prompt_injection_guardrail"
    category = "input"

    SUSPICIOUS_PATTERNS = [
        "ignore all previous instructions",
        "system prompt",
        "you are now a",
        "bypass",
        "disregard",
        "forget everything"
    ]

    def check(self, context: str) -> GuardrailResult:
        context_lower = context.lower()
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern in context_lower:
                return GuardrailResult(
                    guardrail=self.name,
                    category=self.category,
                    passed=False,
                    action=GuardrailAction.BLOCK,
                    severity=Severity.HIGH,
                    reason=f"Detected suspicious pattern indicative of prompt injection: '{pattern}'",
                    matched_rules=(pattern,)
                )
                
        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=True,
            action=GuardrailAction.ALLOW,
            reason="Input appears safe."
        )
