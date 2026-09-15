from backend.app.guardrails.base import GuardrailAction
from backend.app.guardrails.output import SensitiveDataGuardrail


def test_redacts_common_pii_and_valid_payment_card() -> None:
    text = "Email ava@example.com or use card 4111 1111 1111 1111."

    result = SensitiveDataGuardrail().check(text)

    assert result.action is GuardrailAction.REDACT
    assert "ava@example.com" not in (result.transformed_content or "")
    assert "4111 1111 1111 1111" not in (result.transformed_content or "")


def test_does_not_redact_an_order_identifier() -> None:
    text = "The order identifier is 202609120042."

    result = SensitiveDataGuardrail().check(text)

    assert result.action is GuardrailAction.ALLOW
    assert result.transformed_content == text


def test_redacts_api_key() -> None:
    result = SensitiveDataGuardrail().check("Token: sk-proj-abcdefghijklmnopqrstuvwxyz123456")

    assert result.action is GuardrailAction.REDACT
    assert result.severity.value == "critical"
