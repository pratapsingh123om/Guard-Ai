"""Narrow, allowlisted outbound invocation for verified AI connections."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.app.integrations.models import ConnectionStatus
from backend.app.integrations.store import ConnectionRecord


class ProviderInvocationError(RuntimeError):
    """A safe-to-report provider invocation failure."""


def _is_safe_openrouter_endpoint(endpoint: str) -> bool:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == "openrouter.ai"
        and port in {None, 443}
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"/api/v1", "/api/v1/"}
        and not parsed.query
        and not parsed.fragment
    )


async def invoke_ai_connection(
    record: ConnectionRecord,
    *,
    prompt: str,
    data_contexts: list[dict[str, Any]],
) -> str:
    """Invoke a verified OpenRouter connection without enabling model-side tools."""

    if record.status is not ConnectionStatus.VERIFIED:
        raise ProviderInvocationError("Verify the selected AI connection before using it.")
    if record.connector != "openrouter":
        raise ProviderInvocationError(
            "Live generation currently supports verified OpenRouter connections."
        )
    if not _is_safe_openrouter_endpoint(record.endpoint):
        raise ProviderInvocationError("The OpenRouter endpoint is outside the allowlist.")

    model = str(record.settings.get("model") or os.getenv("OPENROUTER_MODEL") or "").strip()
    if not model:
        raise ProviderInvocationError(
            "Set a Model ID on the OpenRouter connection before using live generation."
        )
    api_key = record.credentials.get("api_key", "")
    if not api_key:
        raise ProviderInvocationError("The OpenRouter connection has no API key.")

    context_note = ""
    if data_contexts:
        context_note = (
            "\nA trusted, read-only data connector returned this synthetic summary: "
            f"{data_contexts[0]}. Use it only when relevant."
        )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the response model behind Guard-AI. Follow the user request, "
                    "but do not claim to execute tools or mutate external systems. Guard-AI "
                    "has already screened the request for policy risk."
                    f"{context_note}"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "Guard-AI secure playground",
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=8.0),
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"{record.endpoint.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as exc:
        raise ProviderInvocationError(
            "The selected AI provider could not be reached within the timeout."
        ) from exc

    if response.status_code in {401, 403}:
        raise ProviderInvocationError("The selected AI provider rejected its credential.")
    if response.status_code != 200:
        raise ProviderInvocationError(
            f"The selected AI provider returned HTTP {response.status_code}."
        )
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderInvocationError(
            "The selected AI provider returned an invalid response."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise ProviderInvocationError("The selected AI provider returned an empty response.")
    return content.strip()
