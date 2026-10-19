# Guard-AI secure MCP demo

This demo puts the Guard-AI MCP resource server behind a fail-closed TLS gateway. It demonstrates:

- TLS 1.3 with the hybrid `X25519MLKEM768` key-exchange group;
- mutual TLS with a unique SPIFFE-style agent identity;
- a certificate-bound, five-minute ES256 access token;
- per-tool scopes, request expiry, replay rejection, and Guard-AI policy checks;
- a controlled-client profile using ML-DSA-65 certificates; and
- negative tests for classical-only key exchange, an untrusted certificate, and a missing certificate.

The demo has two TLS profiles:

| Port | Profile | Key exchange | Certificate signatures | Intended use |
|---|---|---|---|---|
| `8443` | Interoperable | X25519 + ML-KEM-768 | ECDSA P-384 | MCP SDK demonstration |
| `9443` | Strict PQC | X25519 + ML-KEM-768 | ML-DSA-65 | Controlled OpenSSL clients |

Both profiles require the hybrid key exchange. Port 8443 deliberately retains classical certificate signatures for wider application-client compatibility; port 9443 proves a fully post-quantum-authenticated handshake for controlled clients.

## Prerequisites

- Docker Desktop with Compose
- OpenSSL 3.5 or newer on the host, with `X25519MLKEM768` and `ML-DSA-65`
- the repository `.venv` with the project dependencies installed

Check algorithm availability with:

```powershell
openssl list -tls1_3 -tls-groups
openssl list -signature-algorithms
```

## Run the complete demo

From the repository root:

```powershell
.\demo\secure-mcp\scripts\setup.ps1 -Force
.\demo\secure-mcp\scripts\verify-handshakes.ps1
.\demo\secure-mcp\scripts\run-negative-tests.ps1
.\demo\secure-mcp\scripts\run-demo.ps1
```

The coordinator output should list the MCP tools, report `TLSv1.3` and `X25519MLKEM768`, and return `approval_required` with `executed: false` for the demo write.
It also reports 25-request end-to-end p50/p95 latency and success rate; the measurement method and résumé-safe wording are documented in [the evaluation report](../../docs/secure-mcp-evaluation.md).

Stop the containers when finished:

```powershell
.\demo\secure-mcp\scripts\stop.ps1
```

## Security properties

The gateway terminates mTLS and overwrites all TLS-attestation headers. The backend is reachable only over a private Unix socket, so a network client cannot forge those headers. The resource server then checks the access token issuer, audience, expiry, scopes, and the `cnf.x5t#S256` binding to the presented client certificate.

Every tool call also carries a UUID request ID plus issued-at and expiry timestamps. Reusing the same ID for an agent is rejected. Write and destructive tools never perform a side effect in this demo; policy returns an approval decision instead.

Generated keys and tokens live under `runtime/`, are ignored by Git and Docker build context, and are valid for demo use only. Do not copy the demo CA or issuer private key into production.

See [the architecture](../../docs/secure-mcp-architecture.md), [threat model](../../docs/secure-mcp-threat-model.md), and [PQC operations guide](../../docs/pqc-operations.md).
