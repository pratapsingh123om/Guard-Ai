# PQC operations guide

## Production rollout

Start with the interop profile: TLS 1.3, mandatory hybrid X25519/ML-KEM-768 key exchange, and conventional mTLS certificates. Measure client compatibility and verify the negotiated group in gateway telemetry. Add the strict ML-DSA profile only for clients whose TLS stack and certificate tooling have been tested end to end.

Treat a missing or different negotiated group as a security failure. Do not silently downgrade a route that is designated PQC-required. Keep a separately named classical emergency endpoint only if the organization explicitly accepts that risk and monitors its use.

## Identity and key lifecycle

- Give every agent a separate workload identity and private key.
- Generate keys in an HSM, TPM, platform key store, or workload-identity system when available.
- Use short-lived certificates and tokens; automate renewal before expiry.
- Bind access tokens to the client certificate and rotate both after suspected compromise.
- Publish and enforce revocation through short certificate lifetimes plus OCSP/CRL or an identity-provider status service.
- Never place CA keys, issuer keys, bearer tokens, or private prompts in source control or container images.

The demo uses one-day certificates and five-minute tokens. Its generated material under `demo/secure-mcp/runtime/` is local, ignored, and intentionally disposable.

For an emergency demo-side denial, set `GUARD_MCP_REVOKED_CERTIFICATE_SERIALS` to a comma-separated list of hexadecimal certificate serials and restart the service. This local list is not a substitute for an automated production revocation system.

## Monitoring

Alert when the gateway sees a protocol other than TLS 1.3, a group other than `X25519MLKEM768`, failed client-certificate verification, repeated request IDs, invalid certificate-bound tokens, unexpected scope denials, or use of the strict/interop profile by an unknown client. Retain certificate serial, SPIFFE identity, OAuth subject, request ID, tool name, policy result, TLS version, and group. Do not retain private keys, raw tokens, or sensitive tool arguments.

## Verification cadence

Run the positive and negative handshake tests after every gateway, OpenSSL, Nginx, certificate, or base-image update. Run the Python security test suite on every application change. Periodically inspect the built image for embedded secrets and confirm the backend is not exposed on a network port.

PQC algorithm and library guidance will evolve. Track the applicable platform vendor and standards-body guidance, inventory every TLS client, and test algorithm migrations before changing the fail-closed policy.
