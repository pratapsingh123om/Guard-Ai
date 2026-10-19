# Secure MCP evaluation

This file records reproducible demo measurements. Update the measured-results section after running the commands on the target machine; do not present these local figures as production capacity.

## Method

From the repository root, with the demo service running:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\demo\secure-mcp\scripts\verify-handshakes.ps1
.\demo\secure-mcp\scripts\run-negative-tests.ps1
.\demo\secure-mcp\scripts\run-demo.ps1
```

The coordinator runs 25 sequential `get_guard_status` requests by default. The recorded run set `GUARD_MCP_BENCHMARK_ITERATIONS=100`. Each sample includes the MCP client/server exchange, hybrid-PQC TLS transport, mTLS, certificate-bound JWT verification, replay validation, scope authorization, and Guard-AI policy inspection.

## Measured results

Measured on 2026-10-08 using Docker Desktop's Linux/WSL2 runtime, Python 3.13, OpenSSL 3.5.9 in the containers, Nginx 1.28.3, and MCP SDK 2.3.0. Traffic stayed on the local Docker bridge/host loopback. Calls were sequential, not concurrent.

| Evaluation | Result |
|---|---:|
| Automated Python tests | 29/29 passed |
| Required hybrid/PQC handshake profiles | 2/2 passed |
| Classical-only, untrusted-certificate, and missing-certificate cases | 3/3 rejected |
| Authorized live MCP requests | 100/100 succeeded |
| End-to-end request latency | p50 28.309 ms; p95 100.638 ms; max 431.741 ms |
| Unapproved write execution | 0 executed; approval required |

These numbers are a single-machine development measurement, not a production load test or SLA. The test commands above reproduce the security results; the 100-request measurement can be reproduced by setting `$env:GUARD_MCP_BENCHMARK_ITERATIONS='100'` before `run-demo.ps1`.

## Résumé guidance

Defensible wording for this run: “Built a fail-closed MCP security gateway using TLS 1.3 hybrid X25519/ML-KEM-768, mTLS, certificate-bound JWTs, scoped authorization, and replay protection; passed 29/29 automated tests and 5/5 positive/negative TLS scenarios, with 100% success and 28.3 ms p50 / 100.6 ms p95 across 100 local end-to-end MCP requests.”

Do not call the local latency result a production SLA, and do not claim quantum-safe authentication for the port 8443 interop profile: its key exchange is hybrid PQC, while its certificate signatures remain ECDSA. Port 9443 is the controlled-client ML-DSA-65 profile.
