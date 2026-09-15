from backend.app.guardrails.base import Guardrail, GuardrailResult, GuardrailAction, Severity

class RiskClassifierGuardrail(Guardrail):
    """
    Classifies tool calls by risk tier.
    """
    name = "risk_classifier_guardrail"
    category = "action"
    
    RISK_TIERS = {
        "get_weather": "low",
        "search_docs": "low",
        "send_email": "high",
        "execute_sql": "high",
        "delete_user": "critical"
    }

    def check(self, context: str) -> GuardrailResult:
        tool_name = context.strip()
        risk = self.RISK_TIERS.get(tool_name, "unknown")
        
        if risk in ["high", "critical"]:
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=False,
                action=GuardrailAction.REQUIRE_APPROVAL,
                severity=Severity.CRITICAL if risk == "critical" else Severity.HIGH,
                reason=f"Tool '{tool_name}' is classified as {risk} risk and requires approval."
            )
            
        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=True,
            action=GuardrailAction.ALLOW,
            reason=f"Tool '{tool_name}' is low risk."
        )
