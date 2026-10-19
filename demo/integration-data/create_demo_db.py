"""Create the deterministic SQLite database used by the connection demo."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = DEMO_ROOT / "guard-ai-demo.db"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    try:
        output.relative_to(DEMO_ROOT)
    except ValueError as exc:
        raise SystemExit("Output must remain inside demo/integration-data.") from exc
    if output.suffix.lower() != ".db":
        raise SystemExit("Output filename must use the .db extension.")
    if output.exists():
        if not args.force:
            raise SystemExit(f"Database already exists: {output}. Use --force to replace it.")
        output.unlink()

    schema = (DEMO_ROOT / "seed.sql").read_text(encoding="utf-8")
    connection = sqlite3.connect(output)
    try:
        connection.executescript(schema)
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()

    print(f"Created synthetic Guard-AI demo database: {output}")


if __name__ == "__main__":
    main()
