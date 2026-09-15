import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

async def test():
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('LLM_MODEL')
    print("Model:", model)
    async with httpx.AsyncClient() as client:
        res = await client.post(
            'https://openrouter.ai/api/v1/chat/completions', 
            headers={'Authorization': f'Bearer {api_key}'}, 
            json={'model': model, 'messages': [{'role': 'user', 'content': 'hi'}]}
        )
        print("Status:", res.status_code)

asyncio.run(test())
