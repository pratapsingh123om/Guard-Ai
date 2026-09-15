import os
import httpx

async def generate_response(prompt: str, system_prompt: str = "You are a helpful AI assistant protected by Guard-AI.") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("LLM_MODEL", "meta-llama/llama-3-8b-instruct:free")
    
    if not api_key or api_key == "your_key_here":
        raise ValueError("Missing or invalid OPENAI_API_KEY environment variable.")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30.0)
        
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")
            
        data = response.json()
        return data["choices"][0]["message"]["content"]
