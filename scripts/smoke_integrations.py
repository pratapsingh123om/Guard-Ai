#!/usr/bin/env python3
"""Smoke-test Guard-AI's environment import and read-only verifiers.

Only connector names and sanitized verification metadata are printed. Tokens,
provider credentials, endpoints, and provider response bodies are never shown.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx
from dotenv import dotenv_values


SUPPORTED_LIVE_CHECKS = {"openrouter", "supabase", "sqlite"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--env-file", default=".env.integrations")
    args = parser.parse_args()

    values = dotenv_values(Path(args.env_file))
    token = values.get("GUARD_ADMIN_TOKEN")
    if not token:
        parser.error("GUARD_ADMIN_TOKEN is missing from the environment file")

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=20.0,
        trust_env=False,
    ) as client:
        imported_response = client.post(
            "/api/v1/connections/import-env",
            headers=headers,
        )
        imported_response.raise_for_status()
        imported = imported_response.json()
        print(
            "Import endpoint: PASS "
            f"({len(imported['imported'])} added, "
            f"{len(imported['existing'])} existing)"
        )

        connections_response = client.get("/api/v1/connections", headers=headers)
        connections_response.raise_for_status()
        for connection in connections_response.json():
            if connection["connector"] not in SUPPORTED_LIVE_CHECKS:
                continue
            verified_response = client.post(
                f"/api/v1/connections/{connection['id']}/test",
                headers=headers,
            )
            verified_response.raise_for_status()
            verified = verified_response.json()
            print(
                f"{connection['connector']}: {verified['status'].upper()} "
                f"via {verified['verification_method']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
