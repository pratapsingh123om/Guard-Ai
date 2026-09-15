from backend.app.guardrails.action import ActionRiskGuardrail
from backend.app.guardrails.base import GuardrailAction


def test_allows_read_only_tool() -> None:
    result = ActionRiskGuardrail().check({"tool": "read_file", "arguments": {"path": "README.md"}})

    assert result.action is GuardrailAction.ALLOW


def test_requires_approval_for_payment() -> None:
    result = ActionRiskGuardrail().check(
        {"tool": "make_payment", "arguments": {"amount": 10, "currency": "USD"}}
    )

    assert result.action is GuardrailAction.REQUIRE_APPROVAL


def test_blocks_unknown_tool() -> None:
    result = ActionRiskGuardrail().check({"tool": "exfiltrate_database", "arguments": {}})

    assert result.action is GuardrailAction.BLOCK


def test_blocks_destructive_arguments_even_for_known_tool() -> None:
    result = ActionRiskGuardrail().check(
        {"tool": "run_command", "arguments": {"command": "rm -rf /important"}}
    )

    assert result.action is GuardrailAction.BLOCK
    assert "recursive_delete" in result.matched_rules


def test_blocks_credentials_in_tool_arguments() -> None:
    result = ActionRiskGuardrail().check(
        {"tool": "send_message", "arguments": {"password": "do-not-send"}}
    )

    assert result.action is GuardrailAction.BLOCK
    assert "credential_in_arguments" in result.matched_rules
