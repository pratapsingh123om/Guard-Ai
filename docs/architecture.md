# Guard-AI architecture

## Goal

Guard-AI puts enforceable policy boundaries around an AI agent while remaining
independent of the model provider and orchestration framework. Runtime and eval
code import the same guardrail classes so test results describe production logic.

## Request flow

```text
user input -> blocking input tripwire -> retrieved-content sanitizer
           -> per-tool risk/approval gate -> agent/provider adapter
           -> sensitive-output redactor -> response
```

The input and tool checks are blocking because starting model or tool execution
before a tripwire finishes can consume tokens or cause side effects. Retrieved
documents are treated as untrusted even when their source is trusted; provenance
is a property carried into prompt construction, not an assumption about content.

## Result contract

Every guardrail returns `GuardrailResult`: guardrail/category names, pass state,
action, severity, score, matched rules, optional transformed content, and metadata.
The API exposes this data with a trace ID. A later observability slice can persist
the same contract as structured events without changing detectors.

## Current boundary

This first slice uses explainable deterministic detectors. It intentionally has
no LLM/provider dependency and executes no tool calls. The `/api/v1/chat` response
is a placeholder proving all four safety stages are wired into the HTTP path.

## Next slices

1. Add a provider adapter behind the existing pipeline and structured event storage.
2. Add contextual/classifier-backed injection detection and compare it against the baseline.
3. Replace or augment regex PII detection with Presidio and locale-specific recognizers.
4. Add signed approval tokens and a separate post-approval execution service.
5. Expand the adversarial corpus and gate CI on category-specific recall/FPR targets.

## Research basis

- [OWASP Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [OpenAI Agents SDK guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [Microsoft Presidio Analyzer](https://microsoft.github.io/presidio/analyzer/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
