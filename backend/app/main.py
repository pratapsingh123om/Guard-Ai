import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from mcp.server.transport_security import TransportSecuritySettings

# Load environment variables from .env file immediately
load_dotenv()
load_dotenv(".env.integrations", override=False)

from backend.app.api.route_health import router as health_router
from backend.app.api.routes_connections import router as connections_router
from backend.app.api.routes_demo import router as demo_router
from backend.app.api.routes_chat import router as chat_router
from backend.app.api.routes_policies import router as policies_router
from backend.app.api.routes_traces import router as traces_router
from backend.app.mcp.config import settings as mcp_settings
from backend.app.mcp.identity import TLSAttestationMiddleware
from backend.app.mcp.server import mcp_server


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    max_request_body_size=mcp_settings.max_request_body_size,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(mcp_settings.allowed_hosts),
        allowed_origins=list(mcp_settings.allowed_origins),
    ),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp_server.session_manager.run():
        yield

app = FastAPI(
    title="Guard-AI Backend",
    description="Provider-neutral runtime guardrails for AI agents.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_without_request_values(
    _request, exc: RequestValidationError
) -> JSONResponse:
    """Return useful validation locations without reflecting submitted secrets."""

    safe_errors = []
    for error in exc.errors():
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx"}
        }
        safe_errors.append(safe_error)
    return JSONResponse(status_code=422, content={"detail": safe_errors})

# Add CORS middleware to allow the frontend to connect
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "GUARD_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TLSAttestationMiddleware,
    expected_version=mcp_settings.expected_tls_version,
    expected_group=mcp_settings.expected_tls_group,
    revoked_serials=mcp_settings.revoked_certificate_serials,
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(chat_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(demo_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(traces_router, prefix="/api/v1")
app.mount("/", mcp_app)
