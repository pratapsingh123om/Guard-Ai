"""Synthetic, read-only data service used by the Guard-AI integration demo."""

from backend.app.demo.database import (
    DEMO_DATABASE_NAME,
    demo_database_path,
    demo_database_root,
    ensure_demo_database,
    read_demo_summary,
)

__all__ = [
    "DEMO_DATABASE_NAME",
    "demo_database_path",
    "demo_database_root",
    "ensure_demo_database",
    "read_demo_summary",
]
