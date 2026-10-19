"""Trusted TLS-attestation context supplied by the local PQC gateway."""

from __future__ import annotations

import base64
import json
from contextvars import ContextVar, Token
from dataclasses import dataclass
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class TLSIdentity:
    agent_id: str
    certificate_thumbprint: str
    certificate_serial: str
    tls_version: str
    tls_group: str


_tls_identity: ContextVar[TLSIdentity | None] = ContextVar("guard_ai_tls_identity", default=None)


def get_tls_identity() -> TLSIdentity | None:
    return _tls_identity.get()


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def parse_client_certificate(encoded_pem: str) -> tuple[x509.Certificate, str]:
    pem = unquote(encoded_pem).encode("utf-8")
    certificate = x509.load_pem_x509_certificate(pem)
    thumbprint = _b64url(certificate.fingerprint(hashes.SHA256()))
    return certificate, thumbprint


def agent_id_from_certificate(certificate: x509.Certificate) -> str:
    try:
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        uri_names = san.get_values_for_type(x509.UniformResourceIdentifier)
    except x509.ExtensionNotFound:
        uri_names = []
    identities = [value for value in uri_names if value.startswith("spiffe://guard-ai.demo/")]
    if len(identities) != 1:
        raise ValueError("client certificate must contain exactly one Guard-AI SPIFFE URI")
    return identities[0]


async def _json_error(send: Send, status: int, code: str, detail: str) -> None:
    body = json.dumps({"error": code, "detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class TLSAttestationMiddleware:
    """Require gateway-provided proof of a verified PQC TLS client.

    These headers are trustworthy only because the backend listens on a Unix
    socket shared exclusively with the gateway. The gateway must strip any
    client-supplied copies and recreate them from its TLS connection state.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        expected_version: str,
        expected_group: str,
        revoked_serials: tuple[str, ...] = (),
    ) -> None:
        self.app = app
        self.expected_version = expected_version
        self.expected_group = expected_group
        self.revoked_serials = {serial.lower().removeprefix("0x") for serial in revoked_serials}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if headers.get("x-guard-tls-verified") != "SUCCESS":
            await _json_error(send, 401, "mtls_required", "A verified client certificate is required.")
            return
        if headers.get("x-guard-tls-version") != self.expected_version:
            await _json_error(send, 400, "tls_version_rejected", "TLS 1.3 is required.")
            return
        if headers.get("x-guard-tls-group") != self.expected_group:
            await _json_error(
                send,
                400,
                "tls_group_rejected",
                "The required hybrid PQC group was not negotiated.",
            )
            return

        encoded_certificate = headers.get("x-guard-client-cert")
        if not encoded_certificate:
            await _json_error(send, 401, "client_certificate_missing", "Client certificate details are missing.")
            return

        try:
            certificate, thumbprint = parse_client_certificate(encoded_certificate)
            certificate_serial = format(certificate.serial_number, "x")
            if certificate_serial in self.revoked_serials:
                await _json_error(
                    send,
                    401,
                    "client_certificate_revoked",
                    "The client certificate has been revoked.",
                )
                return
            identity = TLSIdentity(
                agent_id=agent_id_from_certificate(certificate),
                certificate_thumbprint=thumbprint,
                certificate_serial=certificate_serial,
                tls_version=self.expected_version,
                tls_group=self.expected_group,
            )
        except ValueError as exc:
            await _json_error(send, 401, "client_identity_invalid", str(exc))
            return

        token: Token[TLSIdentity | None] = _tls_identity.set(identity)
        try:
            await self.app(scope, receive, send)
        finally:
            _tls_identity.reset(token)
