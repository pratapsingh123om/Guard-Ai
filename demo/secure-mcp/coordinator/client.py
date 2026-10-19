"""Coordinator agent for the secure Guard-AI MCP demonstration."""

from __future__ import annotations

import asyncio
import json
import math
import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def request_metadata() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "request_id": str(uuid4()),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=30)).isoformat(),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


async def main() -> None:
    url = os.getenv("GUARD_MCP_URL", "https://guard-ai.demo:8443/mcp")
    token = Path(os.getenv("GUARD_MCP_TOKEN_FILE", "/run/guard-ai/tokens/coordinator.jwt")).read_text(
        encoding="utf-8"
    ).strip()
    ca_file = os.getenv("GUARD_MCP_CA_FILE", "/run/guard-ai/certs/interop/ca.crt")
    cert_file = os.getenv("GUARD_MCP_CLIENT_CERT", "/run/guard-ai/certs/interop/client.crt")
    key_file = os.getenv("GUARD_MCP_CLIENT_KEY", "/run/guard-ai/certs/interop/client.key")
    benchmark_iterations = int(os.getenv("GUARD_MCP_BENCHMARK_ITERATIONS", "25"))
    if benchmark_iterations < 1 or benchmark_iterations > 500:
        raise ValueError("GUARD_MCP_BENCHMARK_ITERATIONS must be between 1 and 500")

    tls = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_file)
    tls.minimum_version = ssl.TLSVersion.TLSv1_3
    tls.maximum_version = ssl.TLSVersion.TLSv1_3
    tls.load_cert_chain(cert_file, key_file)

    async with httpx2.AsyncClient(
        verify=tls,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
        trust_env=False,
    ) as http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with Client(transport) as client:
            listed = await client.list_tools()
            latencies_ms: list[float] = []
            status_results = []
            for _ in range(benchmark_iterations):
                started = perf_counter()
                status_results.append(
                    await client.call_tool(
                        "get_guard_status",
                        {"request": request_metadata()},
                    )
                )
                latencies_ms.append((perf_counter() - started) * 1000)
            approval = await client.call_tool(
                "write_demo_note",
                {
                    "note_id": "demo-note",
                    "content": "This is an ephemeral approval test.",
                    "request": request_metadata(),
                },
            )

    status = status_results[0]
    successful_calls = sum(not result.is_error for result in status_results)
    output = {
        "listed_tools": [tool.name for tool in listed.tools],
        "status_result": status.structured_content,
        "approval_result": approval.structured_content,
        "status_is_error": status.is_error,
        "approval_is_error": approval.is_error,
        "benchmark": {
            "description": "End-to-end get_guard_status MCP calls over hybrid-PQC TLS and mTLS",
            "iterations": benchmark_iterations,
            "successful_calls": successful_calls,
            "success_rate_percent": round(successful_calls / benchmark_iterations * 100, 2),
            "latency_ms": {
                "p50": round(percentile(latencies_ms, 0.50), 3),
                "p95": round(percentile(latencies_ms, 0.95), 3),
                "max": round(max(latencies_ms), 3),
            },
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    asyncio.run(main())
