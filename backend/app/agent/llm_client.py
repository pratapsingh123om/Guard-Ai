import os

import httpx


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


async def generate_response(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant protected by Guard-AI.",
    model: str | None = None,
    response_format: dict[str, str] | None = None,
) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = (
        os.getenv("OPENROUTER_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://openrouter.ai/api/v1"
    ).rstrip("/")
    model = model or os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL")

    if not api_key or api_key == "your_key_here":
        raise ValueError("Missing OPENROUTER_API_KEY environment variable.")
    if not model:
        raise ValueError("Missing OPENROUTER_MODEL environment variable.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if referer := os.getenv("OPENROUTER_HTTP_REFERER"):
        headers["HTTP-Referer"] = referer
    if app_name := os.getenv("OPENROUTER_APP_NAME"):
        headers["X-Title"] = app_name

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as exc:
        raise LLMProviderError("AI policy provider could not be reached.") from exc

    if response.status_code != 200:
        raise LLMProviderError(
            "AI policy provider rejected the request.",
            status_code=response.status_code,
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError(
            "AI policy provider returned an invalid response.",
            status_code=response.status_code,
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError(
            "AI policy provider returned an empty response.",
            status_code=response.status_code,
        )
    return content
