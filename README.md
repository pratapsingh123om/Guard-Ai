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
   uvicorn backend.app.main:app --reload
   ```

3. **Run Evaluations**:
   ```bash
   python eval/harness/run_eval.py
   ```

## API Endpoints
- `GET /health` : API status
- `POST /chat` : AI Agent interaction with full guardrails (Prompt Injection check -> LLM -> PII Scrub)

## Future Roadmap
- Integration with Open Policy Agent (OPA) for risk configuration
- Advanced vector database injection attacks (e.g. via `pgvector`)
- React/Vite admin dashboard for monitoring guardrail triggers in real-time.
