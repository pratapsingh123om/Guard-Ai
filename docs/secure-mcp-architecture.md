# Secure MCP architecture

## Request path

```text
Coordinator agent
  | TLS 1.3 + X25519MLKEM768 + client certificate
  v
Nginx security gateway (:8443 or :9443)
  | verified TLS facts, overwritten headers, private Unix socket
  v
Guard-AI TLS-attestation middleware
  | certificate identity + SHA-256 thumbprint
  v
MCP resource-server authentication
  | issuer + audience + expiry + certificate-bound JWT
  v
Tool authorization boundary
  | scope + request lifetime + replay cache + Guard-AI policy
  v
MCP tool result (side effects remain unexecuted in the demo)
```

## Components

The Nginx gateway is the TLS trust boundary. It permits only TLS 1.3 and the hybrid `X25519MLKEM768` group, requires a client certificate, disables session tickets, applies request-size and per-agent rate limits, and logs the negotiated TLS facts and peer certificate identity. Client-provided copies of the attestation headers are replaced with values derived from Nginx TLS state.

The FastAPI backend is not exposed on TCP inside the container. Uvicorn listens on `/run/guard-ai/backend.sock`, which limits access to the colocated gateway. This isolation is what makes the forwarded TLS facts trustworthy.

The MCP authentication layer accepts only ES256 demo tokens with the configured issuer and exact resource audience. The token confirmation claim contains the SHA-256 thumbprint of the interop client certificate. A stolen token therefore cannot be used with another TLS identity.

The tool authorization layer is independent of transport authentication. It enforces `mcp:read`, `mcp:write`, or `mcp:admin`, consumes a short-lived unique request ID, runs the Guard-AI action policy, and emits structured security audit events. The in-memory replay cache is suitable for one demo process; a production deployment must use a shared atomic store.

## Cryptographic profiles

The interop profile on port 8443 uses a hybrid classical/PQ key exchange and ECDSA certificates. It protects recorded traffic against future key-recovery attacks while working with application TLS clients that do not yet support ML-DSA certificates.

The strict profile on port 9443 adds ML-DSA-65 server, client, and CA signatures. It is intended for controlled OpenSSL 3.5+ clients. Both profiles fail closed if the requested hybrid key-exchange group is unavailable.
