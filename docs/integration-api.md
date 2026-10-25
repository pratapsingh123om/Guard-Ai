# Guard-AI integration management API

The integration API lets each authenticated workspace register AI providers, databases, vector stores, object stores, APIs, and MCP servers. Management endpoints accept an active Supabase session, an expiring personal Guard-AI token, or the legacy operator token through `Authorization: Bearer <token>`. Guest sessions are playground-only.

## Endpoints

| Method | Path | Purpose | Authentication |
|---|---|---|---|
| GET | `/api/v1/connections/catalog` | List supported connector definitions | No |
| GET | `/api/v1/auth/config` | Return browser-safe Supabase bootstrap values | No |
| GET | `/api/v1/auth/me` | Return current tenant identity and scopes | Any session/token |
| POST | `/api/v1/auth/tokens` | Mint an expiring personal API token | Non-anonymous Supabase user |
| GET | `/api/v1/demo/health` | Verify the synthetic service and SQLite database | No |
| GET | `/api/v1/demo/summary` | Read aggregate synthetic demo data | No |
| GET | `/api/v1/demo/customers` | Read bounded synthetic customer records | No |
| GET | `/api/v1/demo/orders` | Read bounded synthetic order records | No |
| GET | `/api/v1/connections` | List configured connections | Yes |
| POST | `/api/v1/connections` | Register a connection and its credentials | Yes |
| POST | `/api/v1/connections/import-env` | Import supported server-side environment integrations | Legacy operator only |
| GET | `/api/v1/connections/{id}` | Read masked connection metadata | Yes |
| POST | `/api/v1/connections/{id}/test` | Validate stored configuration | Yes |
| DELETE | `/api/v1/connections/{id}` | Remove a connection and clear its secrets | Yes |
| GET | `/api/v1/policies` | Read runtime and PQC transport policy | Yes |
| PUT | `/api/v1/policies` | Update runtime guardrail switches | Yes |
| GET | `/api/v1/traces` | List recent security traces | Yes |
| GET | `/api/v1/traces/{id}` | Read a trace without prompt or secret bodies | Yes |

## Register an AI provider

```http
POST /api/v1/connections
Authorization: Bearer <operator-token>
Content-Type: application/json

{
  "name": "Production OpenRouter",
  "category": "ai_provider",
  "connector": "openrouter",
  "settings": {"model": "anthropic/claude-sonnet"},
  "credentials": {"api_key": "<secret>"}
}
```

Credentials are write-only. Responses contain `credential_fields`, never credential values. Secret-like keys are rejected from the ordinary `settings` object, and endpoint URLs containing usernames or passwords are rejected.

For OpenRouter, set `settings.model`, test the connection, and select it as the
playground AI destination. Allowed requests then receive a real provider
response; blocked or approval-required requests never reach the provider.

`POST /connections/import-env` imports OpenRouter, Supabase, and the bundled SQLite demo when their server-side configuration is available. It is idempotent by connection name and never returns environment values. This lets the dashboard discover locally configured services without copying credentials into the browser.

## Register PostgreSQL

```json
{
  "name": "Customer Database",
  "category": "database",
  "connector": "postgresql",
  "endpoint": "postgresql://db.internal.example:5432/customers",
  "settings": {"ssl_mode": "verify-full"},
  "credentials": {
    "username": "guard_ai_reader",
    "password": "<secret>"
  }
}
```

The `/test` endpoint performs real, read-only verification for four connectors:

- Guard-AI Demo Service calls the allowlisted `/api/v1/demo/health` endpoint and verifies both its service identity marker and SQLite readiness.
- OpenRouter calls the provider-owned `GET /api/v1/key` endpoint.
- Supabase calls the project `GET /auth/v1/health` endpoint with the API key in the `apikey` header. Use a publishable key (or legacy anon key) and enforce Row Level Security.
- SQLite opens a database confined to `GUARD_SQLITE_ROOT` in read-only mode and runs `SELECT 1`. See [the SQLite demo](../demo/integration-data/README.md).

Guard-AI Demo Service, OpenRouter, and Supabase destinations are restricted to exact HTTPS host allowlists, redirects are disabled, environment proxies are ignored, and short connection/request timeouts are enforced. Provider response bodies are never returned or logged. Other connectors currently return `network_checked: false`, so the frontend must label those **Configured**, not **Connected**.

The demo service endpoint is `https://guard-ai-secure-mcp.vercel.app/api/v1/demo`
in production and `http://127.0.0.1:8080/api/v1/demo` locally. Add preview or
custom production hosts explicitly through the comma-separated
`GUARD_DEMO_ALLOWED_HOSTS` environment variable; arbitrary destinations are
rejected before any network request is made.

## Associate connections with a guarded request

```json
{
  "message": "Summarize recent customer activity",
  "ai_connection_id": "<ai-connection-uuid>",
  "data_connection_ids": ["<database-connection-uuid>"]
}
```

When the selected data connection is a verified Guard-AI demo service or bundled
SQLite database, the chat response also includes `data_contexts` and a summary
read with fixed, read-only SQL. The returned `trace_id` can be requested from
`/api/v1/traces/{trace_id}`. Traces contain guardrail decisions, severity, and
connection IDs but deliberately omit raw prompts, retrieved documents, model
responses, and credentials.

## Storage limitation

The included registry is a bounded, tenant-isolated in-memory implementation for the demonstration. Connections, policies, traces, and guest counters are not durable across process restarts or serverless instances. Personal tokens are stateless and remain valid until expiry unless `GUARD_API_TOKEN_SECRET` is rotated; there is no per-token revocation store yet. Before production use, replace the registry and counters with durable tenant storage, add token revocation, and store credentials in an external secret manager; do not serialize the internal secret-bearing connection records.
