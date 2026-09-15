from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import our new guardrails
from backend.app.guardrails.input.prompt_injection import PromptInjectionGuardrail
from backend.app.guardrails.input.policy_filter import PolicyFilterGuardrail
from backend.app.guardrails.output.pii_redactor import PIIGuardrail

class ChatRequest(BaseModel):
    message: str

router = APIRouter()

# Instantiate guardrails
input_guard_basic = PromptInjectionGuardrail()
input_guard_llm = PolicyFilterGuardrail()
output_guard = PIIGuardrail()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_message = request.message
    
    # 1A. FAST INPUT GUARDRAIL: Basic heuristic check
    input_check_1 = input_guard_basic.check(user_message)
    if not input_check_1.passed:
        raise HTTPException(status_code=400, detail=input_check_1.reason)
        
    # 1B. SMART INPUT GUARDRAIL: LLM-as-a-judge Policy Filter
    input_check_2 = await input_guard_llm.async_check(user_message)
    if not input_check_2.passed:
        raise HTTPException(status_code=400, detail=input_check_2.reason)
    
    # 2. LLM CALL (Real via OpenRouter/OpenAI API)
    from backend.app.agent.llm_client import generate_response
    
    try:
        raw_llm_response = await generate_response(user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: Please ensure you set OPENAI_API_KEY. Details: {str(e)}")
    
    # 3. OUTPUT GUARDRAIL: Scrub PII
    redacted_response = output_guard.redact(raw_llm_response)
    
    return {
        "user_message": user_message,
        "original_llm_response": raw_llm_response,
        "final_response": redacted_response,
        "guardrail_status": {
            "input_passed": input_check.passed,
            "pii_redacted": redacted_response != raw_llm_response
        }
    }
