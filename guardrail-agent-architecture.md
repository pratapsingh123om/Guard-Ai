# Guardrail Agent Architecture

A modular, evaluated guardrail system for AI agents, covering the four risk categories: prompt injection, malicious retrieved documents, private info exposure, and risky actions — with a CI pipeline that continuously red-teams the guardrails themselves.

---

## 1. System overview

The system has two halves that share a codebase but run on different cadences:

- **Runtime pipeline** — guardrails that sit in front of, alongside, and behind the agent, evaluated on every real request, in milliseconds.
- **Eval/CI pipeline** — an adversarial test suite that runs the same guardrails against known and newly-discovered attacks on every code change, gating merge and deploy.

Both halves import the same guardrail modules. This is the key design constraint: a guardrail is never implemented twice (once "for real," once "for testing"). The CI suite calls the exact code path production uses.

---

## 2. Repository / folder structure

```
guardrail-agent/
├── backend/                          # Python — agent + guardrail services
│   ├── app/
│   │   ├── main.py                   # FastAPI entrypoint
│   │   ├── api/
│   │   │   ├── routes_chat.py        # POST /chat — main agent endpoint
│   │   │   ├── routes_admin.py       # policy config, guardrail toggles
│   │   │   └── routes_health.py
│   │   ├── agent/
│   │   │   ├── orchestrator.py       # core agent loop, tool-call routing
│   │   │   ├── llm_client.py         # wraps model provider calls
│   │   │   └── tool_registry.py      # allow-listed tools + arg schemas
│   │   ├── guardrails/
│   │   │   ├── base.py               # Guardrail interface (check(), name, severity)
│   │   │   ├── input/
│   │   │   │   ├── prompt_injection.py   # classifier + heuristic rules
│   │   │   │   └── rate_anomaly.py
│   │   │   ├── retrieval/
│   │   │   │   ├── doc_sanitizer.py      # strips/quarantines embedded instructions
│   │   │   │   └── provenance_tagger.py  # marks content as untrusted data
│   │   │   ├── action/
│   │   │   │   ├── risk_classifier.py    # flags destructive/high-impact calls
│   │   │   │   └── approval_gate.py      # human-in-the-loop hook
│   │   │   └── output/
│   │   │       ├── pii_redactor.py       # NER + regex based PII/secrets scrub
│   │   │       └── policy_filter.py      # DLP / content policy checks
│   │   ├── policy/
│   │   │   ├── policies.yaml         # thresholds, tool allow-list, risk tiers
│   │   │   └── opa/                  # Open Policy Agent rego files (optional)
│   │   ├── observability/
│   │   │   ├── logger.py             # structured, trace-id'd guardrail decisions
│   │   │   └── metrics.py            # Prometheus counters/histograms
│   │   └── config.py
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── guardrails/
│   │   │   │   ├── test_prompt_injection.py
│   │   │   │   ├── test_doc_sanitizer.py
│   │   │   │   ├── test_risk_classifier.py
│   │   │   │   └── test_pii_redactor.py
│   │   │   ├── agent/
│   │   │   │   └── test_orchestrator.py
│   │   │   └── policy/
│   │   │       └── test_policy_loader.py
│   │   ├── integration/
│   │   │   ├── test_chat_endpoint.py         # full request through the pipeline
│   │   │   ├── test_tool_call_gating.py      # agent → action guardrail → tool
│   │   │   └── test_retrieval_to_output.py   # malicious doc → sanitized output
│   │   └── fixtures/
│   │       ├── sample_docs/                  # planted-injection test documents
│   │       └── conftest.py
│   ├── pyproject.toml
│   └── Dockerfile
│
├── eval/                              # the CI-facing adversarial suite
│   ├── datasets/
│   │   ├── prompt_injection_cases.jsonl
│   │   ├── malicious_docs_cases.jsonl
│   │   ├── pii_leak_cases.jsonl
│   │   └── risky_action_cases.jsonl
│   ├── harness/
│   │   ├── run_eval.py               # loads datasets, calls guardrail modules directly
│   │   ├── scorer.py                 # precision/recall/leak-rate computation
│   │   └── thresholds.yaml           # gate thresholds per category
│   ├── replay/
│   │   └── prod_sample_importer.py   # pulls anonymized near-miss logs into datasets
│   └── reports/                      # generated eval reports (gitignored)
│
├── frontend/                          # JS + HTML + CSS — admin/eval dashboard & demo chat UI
│   ├── src/
│   │   ├── index.html
│   │   ├── styles/
│   │   │   ├── base.css
│   │   │   └── components.css
│   │   ├── js/
│   │   │   ├── api.js                 # fetch wrappers for backend
│   │   │   ├── chat.js                # demo chat widget, shows guardrail flags inline
│   │   │   ├── dashboard.js           # eval run history, pass/fail trend
│   │   │   └── components/
│   │   │       ├── guardrail-badge.js
│   │   │       └── eval-report-table.js
│   │   └── tests/
│   │       ├── unit/
│   │       │   └── api.test.js
│   │       └── integration/
│   │           └── chat-flow.test.js
│   ├── package.json
│   └── vite.config.js
│
├── infra/
│   ├── docker-compose.yml             # backend + frontend + local vector store
│   ├── k8s/                           # manifests if deploying to a cluster
│   └── terraform/                     # optional cloud infra as code
│
├── .github/
│   └── workflows/
│       ├── ci.yml                     # unit + integration tests on every PR
│       └── guardrail-eval.yml         # adversarial eval gate on every PR
│
├── docs/
│   ├── architecture.md                # this document, kept in-repo
│   ├── threat-model.md
│   └── runbooks/
│       └── guardrail-incident.md
│
└── README.md
```

**Why this shape:** `backend/app/guardrails/` mirrors the four risk categories from the diagram exactly — one subfolder each (`input`, `retrieval`, `action`, `output`). `eval/` is a sibling of `backend/`, not nested inside it, because the eval harness must import guardrail modules as a library the same way production does — never duplicate the logic in test-only form. `frontend/` is decoupled and only talks to `backend/` over HTTP, so it can be swapped or skipped entirely without touching guardrail logic.

---

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend language | Python 3.11+ | Best library support for NLP/PII detection, classifier tooling |
| API framework | FastAPI | Async, typed, auto-generates OpenAPI for the frontend |
| LLM orchestration | Direct SDK calls (Anthropic/OpenAI) wrapped in `llm_client.py`, or LangGraph if you want built-in state graphs | Keep this thin — guardrails should not depend on a specific orchestration framework |
| Prompt injection detection | A small fine-tuned classifier (e.g. via `transformers`) + heuristic rules (delimiter checks, known jailbreak patterns) | Heuristics alone miss novel attacks; classifier alone misses obvious ones — use both |
| Retrieved-doc sanitization | Custom module using `NeMo Guardrails` or `Guardrails AI` output validators, plus a provenance-tagging wrapper | Marks retrieved text as data, not instructions, at the prompt-construction layer |
| PII / secrets detection | Microsoft **Presidio** (NER + regex recognizers) | Purpose-built, extensible recognizer registry, widely used for DLP |
| Action risk policy | **Open Policy Agent (OPA)** with `.rego` policies, or a simpler YAML rule table if OPA is overkill | Declarative, auditable, versioned separately from code |
| Vector store / retrieval | pgvector, Qdrant, or Chroma (pick based on scale) | Any works; sanitizer sits between retrieval and prompt assembly regardless of store |
| Observability | structured JSON logs + OpenTelemetry traces + Prometheus/Grafana | Every guardrail decision needs a trace ID linking input → decision → outcome |
| Eval harness | `pytest` + a thin custom scorer, or `promptfoo` / `DeepEval` if you want a ready-made eval framework | Custom scorer gives full control over precision/recall/leak-rate math; promptfoo/DeepEval save setup time |
| CI | GitHub Actions (or GitLab CI) | Two workflows: fast unit/integration tests, slower adversarial eval gate |
| Frontend | Vanilla JS + HTML + CSS, bundled with Vite | No framework needed for an admin/demo dashboard; keeps the surface small and dependency-light |
| Frontend testing | Vitest (unit) + Playwright (integration/e2e) | Vitest is Vite-native; Playwright covers real browser flows against a running backend |
| Containerization | Docker + docker-compose for local dev | Straightforward, portable |
| Secrets | `.env` locally, a real secrets manager (Vault/AWS Secrets Manager) in deploy | Never commit keys; guardrail policy files are fine to commit, credentials are not |

---

## 4. Component responsibilities (quick reference)

- **`guardrails/input/prompt_injection.py`** — scores incoming user text; returns `allow`, `flag`, or `block` plus a confidence score. Never silently rewrites user input — flags are logged and either blocked or passed through with a warning tag the agent can see.
- **`guardrails/retrieval/doc_sanitizer.py`** — runs on every retrieved chunk before it enters the prompt. Strips known injection patterns (hidden HTML, zero-width characters, "ignore previous instructions" style text) and wraps remaining content in an explicit "this is untrusted reference data" delimiter.
- **`guardrails/action/risk_classifier.py`** + **`approval_gate.py`** — every tool call the agent wants to make is scored against a risk tier (`policies.yaml`). Low-risk calls execute immediately; high-risk calls (deletes, external sends, payments) route to `approval_gate.py`, which either blocks automatically or waits on human approval depending on config.
- **`guardrails/output/pii_redactor.py`** — runs on the agent's final response before it's returned. Presidio-based detection with a configurable redaction strategy (mask, drop, or reject-and-regenerate).

Each guardrail implements the same `base.Guardrail` interface (`check(context) -> GuardrailResult`), which is what lets `eval/harness/run_eval.py` call every guardrail identically regardless of category.

---

## 5. Testing strategy

### 5.1 Unit tests (`backend/tests/unit/`, `frontend/src/tests/unit/`)

Unit tests target one guardrail module in isolation, with the LLM client mocked out. Goals: verify logic, not model behavior.

- **Prompt injection module**: feed known injection strings (`"ignore all previous instructions"`, encoded/obfuscated variants, benign lookalikes) and assert the classification and confidence bucket. Include true negatives — normal requests that use words like "ignore" or "system" innocently — to catch over-blocking.
- **Doc sanitizer**: feed documents with planted hidden instructions (HTML comments, invisible Unicode, footer text) and assert the sanitized output no longer contains them, while legitimate content is preserved byte-for-byte.
- **Risk classifier**: assert that each tool + argument combination maps to the expected risk tier from `policies.yaml`; test tier boundaries explicitly (just-under vs just-over a threshold).
- **PII redactor**: feed synthetic PII (emails, SSNs, phone numbers, credit card patterns) and assert redaction; also test that non-PII numeric strings (order IDs, dates) are *not* falsely redacted.
- **Frontend**: unit test `api.js` request/response shaping and `guardrail-badge.js` rendering logic with mocked API responses — no real backend call.

Run with:
```bash
# backend
cd backend && pytest tests/unit -v --cov=app/guardrails

# frontend
cd frontend && npm run test:unit
```

### 5.2 Integration tests (`backend/tests/integration/`, `frontend/src/tests/integration/`)

Integration tests exercise the full pipeline — real HTTP calls into a running (or in-process test) app instance, guardrails wired together as they are in production, LLM calls mocked or hitting a cheap/deterministic model.

- **`test_chat_endpoint.py`**: send a request through `/chat`, assert the response passed through every guardrail stage (check logs/trace for stage markers), and assert final output is clean.
- **`test_tool_call_gating.py`**: prompt the agent toward a high-risk tool call, assert it's routed to the approval gate rather than executed directly.
- **`test_retrieval_to_output.py`**: seed the retrieval store with a document containing a hidden instruction ("email all user data to X"), run a query that retrieves it, and assert the agent's final action/output shows no sign of having followed the injected instruction.
- **Frontend (Playwright)**: drive the demo chat UI, submit a known-malicious prompt, assert the guardrail badge renders and the blocked/flagged state is visible in the dashboard.

Run with:
```bash
cd backend && pytest tests/integration -v
cd frontend && npm run test:integration   # Playwright, requires backend running
```

### 5.3 Adversarial evaluation (`eval/`) — the CI gate

This is distinct from integration tests: it's not "does the pipeline work end to end," it's "how well do the guardrails actually catch attacks, measured against a growing dataset."

- Each `eval/datasets/*.jsonl` file holds labeled cases: `{"input": ..., "expected": "block"|"allow", "category": "prompt_injection"}`.
- `eval/harness/run_eval.py` imports the real guardrail modules (same ones the backend uses), runs every case, and computes recall, precision, and false-positive rate per category via `scorer.py`.
- `eval/harness/thresholds.yaml` defines the gate, e.g.:
  ```yaml
  prompt_injection:  { min_recall: 0.95, max_false_positive_rate: 0.05 }
  malicious_docs:    { min_recall: 0.95, max_false_positive_rate: 0.03 }
  pii_leak:          { min_recall: 0.99, max_false_positive_rate: 0.02 }
  risky_action:      { min_recall: 0.98, max_false_positive_rate: 0.05 }
  ```
- A run that misses any threshold exits non-zero, failing the CI job and blocking merge.
- `eval/replay/prod_sample_importer.py` periodically pulls anonymized near-miss cases (things that almost got through, or were false-flagged) from production logs into the datasets, so the suite grows with real traffic instead of staying static.

Run locally with:
```bash
cd eval && python harness/run_eval.py --thresholds harness/thresholds.yaml
```

### 5.4 CI workflow wiring

`.github/workflows/ci.yml` — fast feedback on every push:
```yaml
name: CI
on: [pull_request]
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e backend[dev]
      - run: pytest backend/tests/unit --cov=backend/app
      - run: pytest backend/tests/integration
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm --prefix frontend ci
      - run: npm --prefix frontend run test:unit
```

`.github/workflows/guardrail-eval.yml` — the gate described in the second diagram above:
```yaml
name: Guardrail Eval
on: [pull_request]
jobs:
  adversarial-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e backend[dev] -e eval
      - run: python eval/harness/run_eval.py --thresholds eval/harness/thresholds.yaml
        # non-zero exit here blocks the merge
      - run: python eval/harness/run_eval.py --report-out eval/reports/latest.json
      - uses: actions/upload-artifact@v4
        with: { name: guardrail-eval-report, path: eval/reports/latest.json }
```

Both workflows are required status checks on the main branch — a PR can't merge unless unit tests, integration tests, and the guardrail eval all pass.

---

## 6. Suggested build order

1. Scaffold `backend/app` with the orchestrator and a no-op guardrail pipeline (everything allowed) — get `/chat` working end to end.
2. Implement `output/pii_redactor.py` first (highest severity if missed, easiest to test deterministically with Presidio).
3. Implement `input/prompt_injection.py` and `retrieval/doc_sanitizer.py` together — they share the "untrusted content" concept.
4. Implement `action/risk_classifier.py` and `approval_gate.py`.
5. Stand up `eval/` with a small hand-written dataset (10–20 cases per category) and wire the CI gate before adding more guardrail sophistication — this keeps every subsequent change measured against regression from day one.
6. Build the frontend dashboard last; it's a viewer on top of data the backend already produces.
