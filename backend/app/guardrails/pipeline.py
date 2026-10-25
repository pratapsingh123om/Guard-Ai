"""Runtime coordinator that enforces guardrails in side-effect-safe order."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from backend.app.guardrails.action import ActionRiskGuardrail
from backend.app.guardrails.action.semantic_intent import SemanticIntentGuardrail
from backend.app.guardrails.base import GuardrailAction, GuardrailResult, Severity
from backend.app.guardrails.input import PromptInjectionGuardrail
from backend.app.guardrails.output import SensitiveDataGuardrail
from backend.app.guardrails.retrieval import DocumentSanitizer
from backend.app.policy.runtime import runtime_policy_store


class PipelineStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"


@dataclass(frozen=True)
class PipelineDecision:
    status: PipelineStatus
    results: tuple[GuardrailResult, ...]
    sanitized_documents: tuple[str, ...]


class GuardrailPipeline:
    """A small provider-neutral pipeline that can wrap any agent runtime."""

    def __init__(
        self,
        input_guardrail: PromptInjectionGuardrail | None = None,
        document_guardrail: DocumentSanitizer | None = None,
        action_guardrail: ActionRiskGuardrail | None = None,
        output_guardrail: SensitiveDataGuardrail | None = None,
        semantic_guardrail: SemanticIntentGuardrail | None = None,
    ):
        self.input_guardrail = input_guardrail or PromptInjectionGuardrail()
        self.document_guardrail = document_guardrail or DocumentSanitizer(self.input_guardrail)
        self.action_guardrail = action_guardrail or ActionRiskGuardrail()
        self.output_guardrail = output_guardrail or SensitiveDataGuardrail()
        self.semantic_guardrail = semantic_guardrail or SemanticIntentGuardrail()

    async def inspect_before_agent_async(
        self,
        message: str,
        documents: Sequence[str] = (),
        proposed_actions: Sequence[Mapping[str, Any]] = (),
        owner_id: str = "legacy-admin",
        semantic_fail_closed: bool = True,
    ) -> PipelineDecision:
        """Run deterministic checks, then semantic intent classification."""

        decision = self.inspect_before_agent(
            message=message,
            documents=documents,
            proposed_actions=proposed_actions,
            owner_id=owner_id,
        )
        if decision.status is not PipelineStatus.ALLOWED:
            return decision

        semantic = await self.semantic_guardrail.async_check(message)
        if (
            semantic.action is GuardrailAction.BLOCK
            and semantic.metadata.get("semantic_judge") == "failed_closed"
            and not semantic_fail_closed
        ):
            semantic = replace(
                semantic,
                passed=True,
                action=GuardrailAction.FLAG,
                severity=Severity.MEDIUM,
                reason=(
                    "Semantic judge was unavailable; this guardrail-only simulation "
                    "ran in degraded mode and no external system was invoked."
                ),
                metadata={**semantic.metadata, "degraded_simulation": True},
            )
        results = (*decision.results, semantic)
        if semantic.action is GuardrailAction.BLOCK:
            status = PipelineStatus.BLOCKED
        elif semantic.action is GuardrailAction.REQUIRE_APPROVAL:
            policy = runtime_policy_store.snapshot(owner_id).policy
            if policy.require_approval_for_risky_actions:
                status = PipelineStatus.NEEDS_APPROVAL
            else:
                semantic = replace(
                    semantic,
                    passed=True,
                    action=GuardrailAction.ALLOW,
                    reason="Risk-based approval is disabled by runtime policy.",
                    metadata={**semantic.metadata, "policy_disabled": True},
                )
                results = (*decision.results, semantic)
                status = PipelineStatus.ALLOWED
        else:
            status = PipelineStatus.ALLOWED
        return PipelineDecision(status, results, decision.sanitized_documents)

    def inspect_before_agent(
        self,
        message: str,
        documents: Sequence[str] = (),
        proposed_actions: Sequence[Mapping[str, Any]] = (),
        owner_id: str = "legacy-admin",
    ) -> PipelineDecision:
        """Run all checks that must finish before an agent can cause effects."""

        policy = runtime_policy_store.snapshot(owner_id).policy
        results: list[GuardrailResult] = []
        input_result = (
            self.input_guardrail.check(message)
            if policy.block_prompt_injection
            else GuardrailResult(
                guardrail=self.input_guardrail.name,
                category=self.input_guardrail.category,
                passed=True,
                action=GuardrailAction.ALLOW,
                reason="Prompt-injection blocking is disabled by runtime policy.",
                metadata={"policy_disabled": True},
            )
        )
        results.append(input_result)
        if input_result.action is GuardrailAction.BLOCK:
            return PipelineDecision(PipelineStatus.BLOCKED, tuple(results), ())

        status = PipelineStatus.ALLOWED
        intent_result = self.action_guardrail.check_message_intent(message)
        if intent_result is not None:
            if (
                intent_result.action is GuardrailAction.REQUIRE_APPROVAL
                and not policy.require_approval_for_risky_actions
            ):
                intent_result = replace(
                    intent_result,
                    passed=True,
                    action=GuardrailAction.ALLOW,
                    reason="Risk-based approval is disabled by runtime policy.",
                    metadata={**intent_result.metadata, "policy_disabled": True},
                )
            else:
                status = PipelineStatus.NEEDS_APPROVAL
            results.append(intent_result)

        sanitized_documents: list[str] = []
        for document in documents:
            result = (
                self.document_guardrail.check(document)
                if policy.sanitize_retrieved_content
                else GuardrailResult(
                    guardrail=self.document_guardrail.name,
                    category=self.document_guardrail.category,
                    passed=True,
                    action=GuardrailAction.ALLOW,
                    reason="Retrieval sanitization is disabled by runtime policy.",
                    transformed_content=document,
                    metadata={"policy_disabled": True},
                )
            )
            results.append(result)
            sanitized_documents.append(result.transformed_content or "")

        for action in proposed_actions:
            result = self.action_guardrail.check(action)
            if (
                result.action is GuardrailAction.REQUIRE_APPROVAL
                and not policy.require_approval_for_risky_actions
            ):
                result = replace(
                    result,
                    passed=True,
                    action=GuardrailAction.ALLOW,
                    reason="Risk-based approval is disabled by runtime policy.",
                    metadata={**result.metadata, "policy_disabled": True},
                )
            results.append(result)
            if result.action is GuardrailAction.BLOCK:
                status = PipelineStatus.BLOCKED
            elif result.action is GuardrailAction.REQUIRE_APPROVAL and status is not PipelineStatus.BLOCKED:
                status = PipelineStatus.NEEDS_APPROVAL

        return PipelineDecision(status, tuple(results), tuple(sanitized_documents))

    def inspect_output(
        self,
        response: str,
        *,
        owner_id: str = "legacy-admin",
    ) -> GuardrailResult:
        if runtime_policy_store.snapshot(owner_id).policy.redact_sensitive_output:
            return self.output_guardrail.check(response)
        return GuardrailResult(
            guardrail=self.output_guardrail.name,
            category=self.output_guardrail.category,
            passed=True,
            action=GuardrailAction.ALLOW,
            reason="Sensitive-output redaction is disabled by runtime policy.",
            transformed_content=response,
            metadata={"policy_disabled": True},
        )
