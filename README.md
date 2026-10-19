# Guard-AI: Enterprise Agent Guardrails

Guard-AI is a comprehensive, evaluated guardrail architecture designed to secure autonomous AI agents in production environments. It sits between the user, the agent, and the outside world to mitigate the four primary categories of LLM risk.

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
   Open `http://127.0.0.1:5173`, unlock it with `GUARD_ADMIN_TOKEN`, and use **Import configured services** to discover supported integrations from `.env.integrations` without copying their credentials into the browser.

4. **Run Evaluations**:
   ```bash
   python eval/harness/run_eval.py
   ```

## API Endpoints
- `GET /health` : API status
- `POST /chat` : Provider-neutral guardrail pipeline and trace generation
- `GET/POST /api/v1/connections` : Register and list masked AI/data connection metadata
- `POST /api/v1/connections/import-env` : Import supported server-side integrations without returning secrets
- `POST /api/v1/connections/{id}/test` : Validate a connection configuration
- `GET/PUT /api/v1/policies` : Inspect or update runtime guardrail policy
- `GET /api/v1/traces` : Inspect secret-safe security traces

Management endpoints require a bearer token supplied through `GUARD_ADMIN_TOKEN`. See [the integration API guide](docs/integration-api.md) for request examples and the current storage limitations.

## Security Control Plane

The responsive Vite dashboard makes the integration boundary visible: operators can register AI providers and databases, run allowlisted read-only connectivity checks, select routes in the guarded playground, inspect secret-safe decision traces, and change runtime enforcement policies. The operator token is held in browser session storage only and connection credentials are write-only.

## Secure MCP + PQC Demo

The repository includes an end-to-end MCP demo with TLS 1.3, hybrid X25519/ML-KEM-768 key exchange, mTLS agent identity, certificate-bound tokens, per-tool authorization, and replay protection. See [demo/secure-mcp/README.md](demo/secure-mcp/README.md) for setup and verification commands.

## Future Roadmap
- Integration with Open Policy Agent (OPA) for risk configuration
- Advanced vector database injection attacks (e.g. via `pgvector`)
- Encrypted persistent connection metadata backed by an external secret manager
