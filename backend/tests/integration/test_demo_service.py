from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.demo.database import DEMO_DATABASE_NAME
from backend.app.main import app


client = TestClient(app)


@pytest.fixture
def isolated_demo_database(monkeypatch: pytest.MonkeyPatch):
    demo_root = Path("backend/tests/fixtures") / f"demo-{uuid4().hex}"
    demo_root.mkdir(parents=True)
    monkeypatch.setenv("GUARD_SQLITE_ROOT", str(demo_root))
    monkeypatch.setenv("GUARD_DEMO_AUTO_SEED", "true")
    database_path = demo_root / DEMO_DATABASE_NAME
    yield database_path
    database_path.unlink(missing_ok=True)
    demo_root.rmdir()


def test_demo_health_materializes_seeded_sqlite_database(isolated_demo_database) -> None:
    response = client.get("/api/v1/demo/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "guard-ai-demo",
        "status": "healthy",
        "database": "ready",
        "records": 7,
    }
    assert isolated_demo_database.is_file()


def test_demo_service_returns_real_seeded_records(isolated_demo_database) -> None:
    customers = client.get("/api/v1/demo/customers?limit=2")
    orders = client.get("/api/v1/demo/orders")
    summary = client.get("/api/v1/demo/summary")

    assert customers.status_code == 200
    assert customers.json()["count"] == 2
    assert customers.json()["items"][0]["organization"] == "Northstar Labs"
    assert orders.status_code == 200
    assert orders.json()["count"] == 4
    assert orders.json()["items"][0]["organization"] == "Fabrikam Systems"
    assert summary.json()["data"] == {
        "customer_count": 3,
        "order_count": 4,
        "order_total_cents": 513300,
        "orders_in_review": 1,
    }

    with closing(sqlite3.connect(isolated_demo_database)) as database:
        assert database.execute("SELECT COUNT(*) FROM customers").fetchone() == (3,)


def test_demo_list_limits_are_bounded(isolated_demo_database) -> None:
    response = client.get("/api/v1/demo/orders?limit=101")
    assert response.status_code == 422
