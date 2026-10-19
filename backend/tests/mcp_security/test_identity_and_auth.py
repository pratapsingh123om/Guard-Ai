from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.mcp.auth import BoundJWTTokenVerifier
from backend.app.mcp.config import MCPSettings
from backend.app.mcp.identity import TLSAttestationMiddleware, get_tls_identity


def _certificate() -> tuple[ec.EllipticCurvePrivateKey, str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "coordinator-agent")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://guard-ai.demo/agent/coordinator")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    thumbprint = base64.urlsafe_b64encode(
        certificate.fingerprint(hashes.SHA256())
    ).rstrip(b"=").decode()
    return private_key, pem, thumbprint


def _settings() -> MCPSettings:
    return MCPSettings(
        issuer_url="https://issuer.guard-ai.demo",
        resource_url="https://guard-ai.demo/mcp",
        public_key_file="unused",
        jwt_algorithms=("ES256",),
        allowed_hosts=("testserver",),
        allowed_origins=(),
        expected_tls_version="TLSv1.3",
        expected_tls_group="X25519MLKEM768",
        max_request_body_size=1_048_576,
        request_lifetime_seconds=60,
        clock_skew_seconds=10,
        replay_ttl_seconds=300,
    )


def _build_client(private_key: ec.EllipticCurvePrivateKey, pem: str) -> TestClient:
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    verifier = BoundJWTTokenVerifier(_settings(), public_key=public_key)
    app = FastAPI()

    @app.get("/mcp/check")
    async def check(token: str) -> dict[str, object]:
        verified = await verifier.verify_token(token)
        identity = get_tls_identity()
        return {
            "verified": verified is not None,
            "agent_id": identity.agent_id if identity else None,
        }

    app.add_middleware(
        TLSAttestationMiddleware,
        expected_version="TLSv1.3",
        expected_group="X25519MLKEM768",
    )
    client = TestClient(app)
    client.headers.update(
        {
            "X-Guard-TLS-Verified": "SUCCESS",
            "X-Guard-TLS-Version": "TLSv1.3",
            "X-Guard-TLS-Group": "X25519MLKEM768",
            "X-Guard-Client-Cert": quote(pem),
        }
    )
    return client


def _token(private_key: ec.EllipticCurvePrivateKey, thumbprint: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": "https://issuer.guard-ai.demo",
            "sub": "coordinator-agent",
            "client_id": "coordinator-agent",
            "aud": "https://guard-ai.demo/mcp",
            "scope": "mcp:read mcp:write",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": "token-1",
            "cnf": {"x5t#S256": thumbprint},
        },
        private_key,
        algorithm="ES256",
    )


def test_verified_tls_identity_and_bound_token_are_accepted() -> None:
    private_key, pem, thumbprint = _certificate()
    client = _build_client(private_key, pem)

    response = client.get("/mcp/check", params={"token": _token(private_key, thumbprint)})

    assert response.status_code == 200
    assert response.json() == {
        "verified": True,
        "agent_id": "spiffe://guard-ai.demo/agent/coordinator",
    }


def test_token_bound_to_another_certificate_is_rejected() -> None:
    private_key, pem, _ = _certificate()
    client = _build_client(private_key, pem)

    response = client.get("/mcp/check", params={"token": _token(private_key, "wrong-thumbprint")})

    assert response.status_code == 200
    assert response.json()["verified"] is False


def test_missing_mtls_attestation_is_rejected_before_application() -> None:
    app = FastAPI()
    app.add_middleware(
        TLSAttestationMiddleware,
        expected_version="TLSv1.3",
        expected_group="X25519MLKEM768",
    )

    response = TestClient(app).get("/mcp/check")

    assert response.status_code == 401
    assert response.json()["error"] == "mtls_required"


def test_classical_only_group_is_rejected() -> None:
    _, pem, _ = _certificate()
    app = FastAPI()
    app.add_middleware(
        TLSAttestationMiddleware,
        expected_version="TLSv1.3",
        expected_group="X25519MLKEM768",
    )

    response = TestClient(app).get(
        "/mcp/check",
        headers={
            "X-Guard-TLS-Verified": "SUCCESS",
            "X-Guard-TLS-Version": "TLSv1.3",
            "X-Guard-TLS-Group": "X25519",
            "X-Guard-Client-Cert": quote(pem),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "tls_group_rejected"


def test_revoked_client_certificate_is_rejected() -> None:
    _, pem, _ = _certificate()
    certificate = x509.load_pem_x509_certificate(pem.encode("utf-8"))
    app = FastAPI()
    app.add_middleware(
        TLSAttestationMiddleware,
        expected_version="TLSv1.3",
        expected_group="X25519MLKEM768",
        revoked_serials=(format(certificate.serial_number, "x"),),
    )

    response = TestClient(app).get(
        "/mcp/check",
        headers={
            "X-Guard-TLS-Verified": "SUCCESS",
            "X-Guard-TLS-Version": "TLSv1.3",
            "X-Guard-TLS-Group": "X25519MLKEM768",
            "X-Guard-Client-Cert": quote(pem),
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == "client_certificate_revoked"
