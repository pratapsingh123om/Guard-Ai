from typing import Dict, Any
from backend.app.guardrails.base import Guardrail, GuardrailResult, GuardrailAction, Severity

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

class PIIGuardrail(Guardrail):
    """
    Redacts PII (Personally Identifiable Information) from the agent's output.
    """
    name = "pii_redactor_guardrail"
    category = "output"
    
    def __init__(self):
        if PRESIDIO_AVAILABLE:
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
            self.anonymizer = AnonymizerEngine()
        else:
            self.analyzer = None
            self.anonymizer = None

    def check(self, context: str) -> GuardrailResult:
        if not PRESIDIO_AVAILABLE:
            return GuardrailResult(
                guardrail=self.name,
                category=self.category,
                passed=True, 
                action=GuardrailAction.ALLOW, 
                reason="Presidio not installed, skipped PII check"
            )

        results = self.analyzer.analyze(
            text=context,
            entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"],
            language='en'
        )

        if not results:
             return GuardrailResult(
                 guardrail=self.name,
                 category=self.category,
                 passed=True,
                 action=GuardrailAction.ALLOW,
                 reason="No PII detected."
             )

        anonymized_result = self.anonymizer.anonymize(
            text=context,
            analyzer_results=results
        )

        return GuardrailResult(
            guardrail=self.name,
            category=self.category,
            passed=False,
            action=GuardrailAction.REDACT,
            severity=Severity.HIGH,
            reason="PII detected and redacted.",
            transformed_content=anonymized_result.text
        )

    def redact(self, context: str) -> str:
        res = self.check(context)
        if res.transformed_content:
            return res.transformed_content
        return context
