# Guard-AI: Enterprise Agent Guardrails

Guard-AI is an evaluated security-gateway prototype for AI agents. It sits between the user, the model, data connectors, and tool calls so each boundary can be authenticated, authorized, inspected, and traced. The included in-memory registry is a demonstration component, not production secret storage.

## Core Security Features

- 🛡️ **Input Guardrails (Prompt Injection)**: Real-time classification and heuristic analysis to intercept jailbreak attempts and malicious user inputs before they reach the LLM.
- 📂 **Retrieval Sanitization (RAG Security)**: Quarantines embedded instructions in retrieved documents, ensuring the agent treats context as untrusted data rather than executable commands.
- ⚙️ **Action Policy Engine (Tool Execution)**: A risk-tiered classification system for agent tool calls. High-risk actions (e.g., database deletions, external API calls) are automatically routed to a Human-in-the-Loop approval gate.
- 🕵️ **Output Redaction (DLP)**: Utilizes Microsoft Presidio for continuous Named Entity Recognition (NER) to scrub Personally Identifiable Information (PII) and secrets from the agent's final output.

## Architecture

The system is split into two tightly integrated pipelines:
1. **Runtime Pipeline**: An async FastAPI backend that intercepts requests in milliseconds, evaluating inputs, RAG context, agent tool decisions, and final outputs.
2. **Adversarial CI Pipeline**: An automated red-teaming harness that bombards the guardrails with known injection and leakage attacks on every code change, gating merges based on strict precision and recall thresholds.

## Getting Started

1. **Install Dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or .\venv\Scripts\Activate.ps1 on Windows
   pip install fastapi "uvicorn[standard]" presidio-analyzer presidio-anonymizer pydantic spacy
   python -m spacy download en_core_web_lg
   ```

2. **Run the API**:
   ```bash
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload
   ```

3. **Run the dashboard**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://127.0.0.1:5173`. Sign in with Google for an isolated workspace, use the limited guest playground, or open the legacy operator recovery section. Google and guest sessions are issued by Supabase Auth.

4. **Run Evaluations**:
   ```bash
   python eval/harness/run_eval.py
   python eval/harness/run_semantic_intent_eval.py
   ```

## API Endpoints
- `GET /health` : API status
- `GET /api/v1/auth/config|me` : Browser auth bootstrap and current identity
- `POST /api/v1/auth/tokens` : Mint an expiring personal Guard-AI bearer token
- `GET /api/v1/demo/health` : Live demo-service and SQLite readiness check
- `GET /api/v1/demo/summary|customers|orders` : Read-only synthetic demo data
- `POST /api/v1/chat` : Authenticated guardrail pipeline, optional live OpenRouter generation, and trace creation
- `GET/POST /api/v1/connections` : Register and list masked AI/data connection metadata
- `POST /api/v1/connections/import-env` : Import supported server-side integrations without returning secrets
- `POST /api/v1/connections/{id}/test` : Validate a connection configuration
- `GET/PUT /api/v1/policies` : Inspect or update runtime guardrail policy
- `GET /api/v1/traces` : Inspect secret-safe security traces

Management endpoints accept an active Supabase user session, a personal `gai_` token, or the legacy `GUARD_ADMIN_TOKEN`. Anonymous sessions are restricted to a bounded playground trial. See [the integration API guide](docs/integration-api.md) for request examples and current storage limitations.

See [authentication setup](docs/auth-setup.md) for the required Google,
Supabase, redirect, and Vercel settings.

## Test a real service and database

The deployment includes a synthetic customer/order service backed by a real,
read-only SQLite database. In the dashboard, unlock the console, choose **Add
connection**, and select **Guard-AI Demo Service**. The endpoint is filled from
the current site origin; saving it runs an allowlisted live health check against
the API and its database. Add **SQLite** with
`sqlite:///guard-ai-demo.db` to verify the database directly in read-only mode.

After either connection is verified, select it under **Data context** in the
playground and submit a safe prompt such as “Give me the connected data
summary.” The response includes aggregate values read from the seeded database,
and the activity trace records which connection crossed the guardrail boundary.
All demo records are synthetic.

### Vercel deployment

The repository deploys the Vite dashboard and FastAPI service together on one
Vercel origin. The checked-in `vercel.json` builds the frontend with Vercel's
static builder and routes API traffic through the root `app.py` entrypoint.
Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (or the legacy
`SUPABASE_ANON_KEY`), and a separate `GUARD_API_TOKEN_SECRET` in Vercel for
Google/guest access and personal tokens. Add `OPENROUTER_API_KEY` and a paid or
adequately rate-limited `GUARD_JUDGE_MODEL` for semantic enforcement. The
semantic judge fails closed before live provider/data invocation; a
guardrail-only simulation is explicitly marked degraded when the judge is
unavailable. `GUARD_ADMIN_TOKEN` remains an optional recovery identity and is
the only identity allowed to import server-owned environment secrets.

## Security Control Plane

The responsive Vite dashboard makes the integration boundary visible: authenticated users can register their own AI providers and databases, run allowlisted read-only connectivity checks, select routes in the guarded playground, inspect secret-safe decision traces, create expiring API tokens, and change their own runtime policy. Tenant ownership is enforced by the backend; credentials are write-only.

## Secure MCP + PQC Demo

The repository includes an end-to-end MCP demo with TLS 1.3, hybrid X25519/ML-KEM-768 key exchange, mTLS agent identity, certificate-bound tokens, per-tool authorization, and replay protection. See [demo/secure-mcp/README.md](demo/secure-mcp/README.md) for setup and verification commands.

## Future Roadmap
- Integration with Open Policy Agent (OPA) for risk configuration
- Advanced vector database injection attacks (e.g. via `pgvector`)
- Encrypted persistent connection metadata backed by an external secret manager
