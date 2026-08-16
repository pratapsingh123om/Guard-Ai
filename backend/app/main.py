from fastapi import FastAPI
# ```importing code *```
#using decorators
from backend.app.api.route_health import router as health_router
from backend.app.api.routes_chat import router as chat_router
#building app
app=FastAPI(title="Guard-AI Backend")
app.include_router(health_router)

app.include_router(chat_router)