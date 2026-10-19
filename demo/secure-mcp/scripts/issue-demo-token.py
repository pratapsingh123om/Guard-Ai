"""Issue a short-lived, certificate-bound JWT for the demo coordinator."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--client-cert", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--issuer", default="https://issuer.guard-ai.demo")
    parser.add_argument("--audience", default="https://guard-ai.demo:8443/mcp")
    parser.add_argument("--subject", default="coordinator-agent")
    parser.add_argument("--scopes", default="mcp:read mcp:write")
    parser.add_argument("--lifetime-seconds", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    certificate = x509.load_pem_x509_certificate(Path(args.client_cert).read_bytes())
    thumbprint = base64.urlsafe_b64encode(
        certificate.fingerprint(hashes.SHA256())
    ).rstrip(b"=").decode("ascii")
    now = datetime.now(timezone.utc)
    claims = {
        "iss": args.issuer,
        "sub": args.subject,
        "client_id": args.subject,
        "aud": args.audience,
        "scope": args.scopes,
        "iat": now,
        "exp": now + timedelta(seconds=args.lifetime_seconds),
        "jti": str(uuid4()),
        "cnf": {"x5t#S256": thumbprint},
    }
    token = jwt.encode(
        claims,
        Path(args.private_key).read_bytes(),
        algorithm="ES256",
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(token + "\n", encoding="utf-8")
    print(f"Issued certificate-bound token valid for {args.lifetime_seconds} seconds: {output}")


if __name__ == "__main__":
    main()
