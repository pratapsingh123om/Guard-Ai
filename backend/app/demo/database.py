"""Create and read the deterministic SQLite database used by the public demo API."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
from contextlib import closing
from importlib.resources import files
from pathlib import Path
from typing import Any


DEMO_DATABASE_NAME = "guard-ai-demo.db"
_INITIALIZE_LOCK = threading.Lock()


def demo_database_root() -> Path:
    """Return the only directory from which demo SQLite files may be opened."""

    configured = os.getenv("GUARD_SQLITE_ROOT")
    if configured:
        return Path(configured).resolve()
    if os.getenv("VERCEL"):
        return (Path(tempfile.gettempdir()) / "guard-ai-demo").resolve()
    return Path("demo/integration-data").resolve()


def demo_database_path() -> Path:
    return demo_database_root() / DEMO_DATABASE_NAME


def _auto_seed_allowed() -> bool:
    value = os.getenv("GUARD_DEMO_AUTO_SEED")
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    # An explicit SQLite root is operator-owned. Do not unexpectedly write to it.
    return os.getenv("GUARD_SQLITE_ROOT") is None


def ensure_demo_database() -> Path | None:
    """Materialize the synthetic database once, returning ``None`` when disabled."""

    destination = demo_database_path()
    if destination.is_file():
        return destination
    if not _auto_seed_allowed():
        return None

    with _INITIALIZE_LOCK:
        if destination.is_file():
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        seed = files("backend.app.demo").joinpath("seed.sql").read_text(encoding="utf-8")
        temporary = destination.with_suffix(".tmp.db")
        temporary.unlink(missing_ok=True)
        database = sqlite3.connect(temporary)
        try:
            database.executescript(seed)
            database.commit()
        except Exception:
            database.close()
            temporary.unlink(missing_ok=True)
            raise
        else:
            database.close()
        temporary.replace(destination)
    return destination


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def read_demo_summary(path: Path | None = None) -> dict[str, Any]:
    """Return aggregate demo facts using fixed SQL and a read-only connection."""

    database_path = path or ensure_demo_database()
    if database_path is None:
        raise FileNotFoundError(DEMO_DATABASE_NAME)
    with closing(_read_only_connection(database_path)) as database:
        customers = database.execute("SELECT COUNT(*) AS count FROM customers").fetchone()
        orders = database.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(total_cents), 0) AS total_cents FROM orders"
        ).fetchone()
        review = database.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE status = 'review'"
        ).fetchone()
    return {
        "customer_count": int(customers["count"]),
        "order_count": int(orders["count"]),
        "order_total_cents": int(orders["total_cents"]),
        "orders_in_review": int(review["count"]),
    }


def read_demo_customers(*, limit: int) -> list[dict[str, Any]]:
    path = ensure_demo_database()
    if path is None:
        raise FileNotFoundError(DEMO_DATABASE_NAME)
    with closing(_read_only_connection(path)) as database:
        rows = database.execute(
            """
            SELECT id, organization, region, risk_tier
            FROM customers
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def read_demo_orders(*, limit: int) -> list[dict[str, Any]]:
    path = ensure_demo_database()
    if path is None:
        raise FileNotFoundError(DEMO_DATABASE_NAME)
    with closing(_read_only_connection(path)) as database:
        rows = database.execute(
            """
            SELECT orders.id, orders.customer_id, customers.organization,
                   orders.status, orders.total_cents, orders.created_at
            FROM orders
            JOIN customers ON customers.id = orders.customer_id
            ORDER BY orders.created_at DESC, orders.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
