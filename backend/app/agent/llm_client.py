import os

import httpx


async def generate_response(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant protected by Guard-AI.",
) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = (
        os.getenv("OPENROUTER_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://openrouter.ai/api/v1"
    ).rstrip("/")
    model = os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL")

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
        ]
    }

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            raise RuntimeError(f"AI provider returned HTTP {response.status_code}.")

        data = response.json()
        return data["choices"][0]["message"]["content"]
