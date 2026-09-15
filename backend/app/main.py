from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file immediately
load_dotenv()

from backend.app.api.route_health import router as health_router
from backend.app.api.routes_chat import router as chat_router

app = FastAPI(
    title="Guard-AI Backend",
    description="Provider-neutral runtime guardrails for AI agents.",
    version="0.1.0",
)

# Add CORS middleware to allow the frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
