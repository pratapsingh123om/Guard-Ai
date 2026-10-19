"""Public and internal models for Guard-AI integration connections."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class ConnectionCategory(str, Enum):
    AI_PROVIDER = "ai_provider"
    DATABASE = "database"
    VECTOR_STORE = "vector_store"
    OBJECT_STORE = "object_store"
    MCP_SERVER = "mcp_server"
    API = "api"


class ConnectionStatus(str, Enum):
    CONFIGURED = "configured"
    VERIFIED = "verified"
    FAILED = "failed"


class ConnectorDefinition(BaseModel):
    id: str
    label: str
    category: ConnectionCategory
    default_endpoint: str | None = None
    required_credentials: list[str] = Field(default_factory=list)
    network_test_supported: bool = False


CONNECTOR_CATALOG: dict[str, ConnectorDefinition] = {
    definition.id: definition
    for definition in (
        ConnectorDefinition(
            id="guard_demo",
            label="Guard-AI Demo Service",
            category=ConnectionCategory.API,
            network_test_supported=True,
        ),
        ConnectorDefinition(
            id="openai",
            label="OpenAI",
            category=ConnectionCategory.AI_PROVIDER,
            default_endpoint="https://api.openai.com/v1",
            required_credentials=["api_key"],
        ),
        ConnectorDefinition(
            id="openrouter",
            label="OpenRouter",
            category=ConnectionCategory.AI_PROVIDER,
            default_endpoint="https://openrouter.ai/api/v1",
            required_credentials=["api_key"],
            network_test_supported=True,
        ),
        ConnectorDefinition(
            id="anthropic",
            label="Anthropic",
            category=ConnectionCategory.AI_PROVIDER,
            default_endpoint="https://api.anthropic.com/v1",
            required_credentials=["api_key"],
        ),
        ConnectorDefinition(
            id="gemini",
            label="Google Gemini",
            category=ConnectionCategory.AI_PROVIDER,
            default_endpoint="https://generativelanguage.googleapis.com/v1beta",
            required_credentials=["api_key"],
        ),
        ConnectorDefinition(
            id="ollama",
            label="Ollama",
            category=ConnectionCategory.AI_PROVIDER,
            default_endpoint="http://127.0.0.1:11434",
        ),
        ConnectorDefinition(
            id="custom_ai",
            label="Custom OpenAI-compatible API",
            category=ConnectionCategory.AI_PROVIDER,
        ),
        ConnectorDefinition(
            id="sqlite",
            label="SQLite",
            category=ConnectionCategory.DATABASE,
        ),
        ConnectorDefinition(
            id="postgresql",
            label="PostgreSQL",
            category=ConnectionCategory.DATABASE,
            required_credentials=["username", "password"],
        ),
        ConnectorDefinition(
            id="mysql",
            label="MySQL",
            category=ConnectionCategory.DATABASE,
            required_credentials=["username", "password"],
        ),
        ConnectorDefinition(
            id="mongodb",
            label="MongoDB",
            category=ConnectionCategory.DATABASE,
            required_credentials=["username", "password"],
        ),
        ConnectorDefinition(
            id="supabase",
            label="Supabase",
            category=ConnectionCategory.DATABASE,
            required_credentials=["api_key"],
            network_test_supported=True,
        ),
        ConnectorDefinition(
            id="pinecone",
            label="Pinecone",
            category=ConnectionCategory.VECTOR_STORE,
            required_credentials=["api_key"],
        ),
        ConnectorDefinition(
            id="qdrant",
            label="Qdrant",
            category=ConnectionCategory.VECTOR_STORE,
        ),
        ConnectorDefinition(
            id="s3",
            label="Amazon S3",
            category=ConnectionCategory.OBJECT_STORE,
            required_credentials=["access_key_id", "secret_access_key"],
        ),
        ConnectorDefinition(
            id="mcp",
            label="MCP Server",
            category=ConnectionCategory.MCP_SERVER,
        ),
        ConnectorDefinition(
            id="custom_api",
            label="Custom REST API",
            category=ConnectionCategory.API,
        ),
    )
}


_SECRET_KEY = re.compile(r"(?:api[_-]?key|password|secret|token|private[_-]?key)", re.I)
_ALLOWED_SCHEMES = {
    ConnectionCategory.AI_PROVIDER: {"http", "https"},
    ConnectionCategory.DATABASE: {
        "http",
        "https",
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "mongodb+srv",
        "sqlite",
    },
    ConnectionCategory.VECTOR_STORE: {"http", "https"},
    ConnectionCategory.OBJECT_STORE: {"http", "https", "s3"},
    ConnectionCategory.MCP_SERVER: {"http", "https"},
    ConnectionCategory.API: {"http", "https"},
}


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    category: ConnectionCategory
    connector: str = Field(min_length=1, max_length=40)
    endpoint: str | None = Field(default=None, max_length=2048)
    settings: dict[str, str | int | float | bool] = Field(default_factory=dict)
    credentials: dict[str, SecretStr] = Field(default_factory=dict)

    @field_validator("name", "connector")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("settings")
    @classmethod
    def reject_secrets_in_settings(
        cls, value: dict[str, str | int | float | bool]
    ) -> dict[str, str | int | float | bool]:
        if len(value) > 30:
            raise ValueError("at most 30 settings are allowed")
        unsafe = sorted(key for key in value if _SECRET_KEY.search(key))
        if unsafe:
            raise ValueError(
                f"secret-like settings must be supplied in credentials: {', '.join(unsafe)}"
            )
        return value

    @field_validator("credentials")
    @classmethod
    def bound_credentials(cls, value: dict[str, SecretStr]) -> dict[str, SecretStr]:
        if len(value) > 20:
            raise ValueError("at most 20 credentials are allowed")
        for key, secret in value.items():
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", key):
                raise ValueError(f"invalid credential field: {key}")
            length = len(secret.get_secret_value())
            if not 1 <= length <= 8192:
                raise ValueError(f"credential {key} must contain 1 to 8192 characters")
        return value

    @model_validator(mode="after")
    def validate_connector(self) -> "ConnectionCreate":
        definition = CONNECTOR_CATALOG.get(self.connector)
        if definition is None:
            raise ValueError(f"unsupported connector: {self.connector}")
        if definition.category is not self.category:
            raise ValueError(
                f"connector {self.connector} belongs to category {definition.category.value}"
            )

        endpoint = (self.endpoint or definition.default_endpoint or "").strip()
        if not endpoint:
            raise ValueError(f"endpoint is required for connector {self.connector}")
        parsed = urlsplit(endpoint)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES[self.category]:
            raise ValueError(f"unsupported endpoint scheme for {self.category.value}")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint URLs must not contain credentials")
        if not parsed.hostname and parsed.scheme not in {"s3", "sqlite"}:
            raise ValueError("endpoint must contain a hostname")
        if parsed.scheme == "sqlite" and (not parsed.path or parsed.query or parsed.fragment):
            raise ValueError("SQLite endpoint must name one database file without query parameters")
        self.endpoint = endpoint

        missing = [
            field for field in definition.required_credentials if field not in self.credentials
        ]
        if missing:
            raise ValueError(f"missing required credentials: {', '.join(missing)}")
        return self


class ConnectionResponse(BaseModel):
    id: UUID
    name: str
    category: ConnectionCategory
    connector: str
    endpoint: str
    settings: dict[str, Any]
    credential_fields: list[str]
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None = None
    last_error: str | None = None


class ConnectionTestResponse(BaseModel):
    connection_id: UUID
    status: ConnectionStatus
    configuration_valid: bool
    network_checked: bool
    network_reachable: bool | None = None
    verification_method: str
    checked_at: datetime
    message: str
