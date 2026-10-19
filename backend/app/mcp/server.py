"""MCP resource server mounted by the Guard-AI FastAPI application."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings

from backend.app.mcp.auth import BoundJWTTokenVerifier
from backend.app.mcp.config import settings
from backend.app.mcp.tools import register_tools


mcp_server = MCPServer(
    "Guard-AI Secure MCP",
    description="Policy-enforced MCP tools protected by mTLS, scoped tokens, and replay checks.",
    version="0.1.0",
    token_verifier=BoundJWTTokenVerifier(),
    auth=AuthSettings(
        issuer_url=settings.issuer_url,
        resource_server_url=settings.resource_url,
        required_scopes=[],
        validate_token_resource=True,
    ),
)
register_tools(mcp_server)
