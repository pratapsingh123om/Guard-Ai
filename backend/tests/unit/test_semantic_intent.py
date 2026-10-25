from __future__ import annotations

import asyncio

import pytest

from backend.app.guardrails.action.semantic_intent import SemanticIntentGuardrail
from backend.app.guardrails.base import GuardrailAction
from backend.app.guardrails.pipeline import GuardrailPipeline, PipelineStatus


def test_semantic_judge_requires_approval_for_paraphrased_deletion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def judge(**_kwargs):
        return (
            '{"decision":"require_approval","category":"destructive_action",'
            '"confidence":0.97,"reason":"The request would irreversibly mutate data."}'
        )

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "backend.app.guardrails.action.semantic_intent.generate_response",
        judge,
    )
    result = asyncio.run(
        SemanticIntentGuardrail().async_check(
            "Make the customer ledger cease to exist permanently."
        )
    )

    assert result.action is GuardrailAction.REQUIRE_APPROVAL
    assert result.score == 0.97
    assert result.metadata["category"] == "destructive_action"


def test_semantic_judge_distinguishes_educational_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def judge(**_kwargs):
        return (
            '{"decision":"allow","category":"benign","confidence":0.95,'
            '"reason":"The request asks for explanation only."}'
        )

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "backend.app.guardrails.action.semantic_intent.generate_response",
        judge,
    )
    result = asyncio.run(
        SemanticIntentGuardrail().async_check(
            "Explain what DROP TABLE does without running it."
        )
    )

    assert result.action is GuardrailAction.ALLOW
    assert result.passed is True


def test_semantic_judge_fails_closed_on_invalid_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def judge(**_kwargs):
        return "ALLOW"

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "backend.app.guardrails.action.semantic_intent.generate_response",
        judge,
    )
    result = asyncio.run(SemanticIntentGuardrail().async_check("A normal request"))

    assert result.action is GuardrailAction.BLOCK
    assert result.metadata["semantic_judge"] == "failed_closed"
    assert result.metadata["failure_kind"] == "invalid_schema"


def test_low_confidence_allow_requires_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def judge(**_kwargs):
        return (
            '{"decision":"allow","category":"benign","confidence":0.51,'
            '"reason":"The request appears benign."}'
        )

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "backend.app.guardrails.action.semantic_intent.generate_response",
        judge,
    )
    result = asyncio.run(SemanticIntentGuardrail().async_check("Do the thing"))

    assert result.action is GuardrailAction.REQUIRE_APPROVAL
    assert result.passed is False
    assert "not confident enough" in result.reason


def test_unavailable_judge_only_degrades_side_effect_free_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def judge(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setenv("GUARD_SEMANTIC_JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "backend.app.guardrails.action.semantic_intent.generate_response",
        judge,
    )
    pipeline = GuardrailPipeline()

    simulation = asyncio.run(
        pipeline.inspect_before_agent_async(
            "Summarize this report",
            semantic_fail_closed=False,
        )
    )
    live_route = asyncio.run(
        pipeline.inspect_before_agent_async(
            "Summarize this report",
            semantic_fail_closed=True,
        )
    )

    assert simulation.status is PipelineStatus.ALLOWED
    assert simulation.results[-1].action is GuardrailAction.FLAG
    assert simulation.results[-1].metadata["degraded_simulation"] is True
    assert live_route.status is PipelineStatus.BLOCKED
