# Secure MCP threat model

## Protected assets

- MCP tool access and authorization decisions
- agent identity and per-agent permissions
- request confidentiality and integrity in transit
- protection of captured traffic against later quantum decryption
- private keys, access tokens, prompts, and tool arguments

## Threats and controls

| Threat | Demo control |
|---|---|
| Network interception or alteration | TLS 1.3 only |
| Store-now-decrypt-later attack | Mandatory X25519 + ML-KEM-768 hybrid key exchange |
| Unauthenticated agent | Mandatory client certificate |
| Stolen bearer token | JWT thumbprint binding to the mTLS certificate |
| Cross-service token use | Exact issuer and resource audience validation |
| Over-privileged agent | Per-tool scopes and server-side Guard-AI policy |
| Replayed tool request | UUID, timestamps, short lifetime, per-agent replay cache |
| Forged proxy security headers | Gateway overwrites headers; backend uses a private Unix socket |
| Oversized or abusive requests | One-megabyte body limit and per-agent gateway rate limit |
| Dangerous write/delete action | Demo reports policy/approval state and performs no side effect |
| Secret leakage in logs | Structured logs record identity and decisions, not keys or token bodies |

## Trust assumptions

- The container host, Docker daemon, gateway image, and private Unix socket are trusted.
- The demo CA and token issuer keys have not been copied or compromised.
- OpenSSL reports the negotiated group accurately to Nginx as `$ssl_curve`.
- System clocks are sufficiently synchronized for certificate and request expiry checks.

## Deliberate limits

This is a software demo, not a production certificate authority or identity provider. It does not provide HSM-backed keys, automated certificate status checking, a distributed replay cache, durable audit storage, workload attestation, or a human approval service. PQC transport does not prevent prompt injection, malicious tools, compromised endpoints, or misuse by a correctly authorized agent; those still require Guard-AI policy, sandboxing, monitoring, and operational response.
