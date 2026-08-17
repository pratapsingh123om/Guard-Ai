from fastapi import APIRouter
from pydantic import BaseModel

class ChatRequest(BaseModel):
  message:str

router=APIRouter()
@router.post("/chat")
async def chat_endpoint(request:ChatRequest):
  user_message=request.message


  dummy_response=f"Agent says :I recived your message: `{user_message}`"
  return {"response": dummy_response if user_message == "Hi" else "bye"}