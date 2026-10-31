"""Apply the Supabase migrations in supabase/migrations/ (in order).

Reads the full Postgres connection string from SUPABASE_DB_URL — never from a
committed file and never printed. Requires a pure-Python driver so it works on
machines without psql:

    pip install pg8000
    SUPABASE_DB_URL="postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres" \\
        python scripts/supabase_migrate.py

Exit codes: 0 applied, 2 not configured, 1 failure (the failing file and
error are reported without echoing the connection string).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "supabase" / "migrations"


def parse_db_url(url: str) -> dict:
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ValueError("SUPABASE_DB_URL must start with postgresql://")
    return {
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "host": parts.hostname or "",
        "port": parts.port or 5432,
        "database": (parts.path or "/postgres").lstrip("/") or "postgres",
    }


def connect(params: dict):
    try:
        import pg8000.dbapi as dbapi  # noqa: PLC0415 - optional dependency
    except ImportError:
        print("FAIL: pg8000 is not installed. Run: pip install pg8000")
        return None
    return dbapi.connect(
        user=params["user"],
        password=params["password"],
        host=params["host"],
        port=params["port"],
        database=params["database"],
        ssl_context=True,
    )


def main() -> int:
    url = os.getenv("SUPABASE_DB_URL", "")
    if not url:
        print("FAIL: SUPABASE_DB_URL is not set (see supabase/README.md).")
        return 2
    try:
        params = parse_db_url(url)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        print(f"FAIL: no migrations found in {MIGRATIONS}")
        return 1

    conn = connect(params)
    if conn is None:
        return 1
    conn.autocommit = True
    try:
        cursor = conn.cursor()
        for path in files:
            sql = path.read_text(encoding="utf-8")
            print(f"applying {path.name} …")
            try:
                cursor.execute(sql)
            except Exception as exc:  # noqa: BLE001 - report which file failed
                print(f"FAIL in {path.name}: {exc}")
                return 1
        print(f"OK: applied {len(files)} migration(s) to {params['host']}/{params['database']}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
