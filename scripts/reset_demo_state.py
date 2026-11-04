"""Reset the demo state so a recording starts from an empty registry.

The schema forbids DELETE on `decisions` (append-only trigger), so a plain
delete is rejected by design. TRUNCATE is the sanctioned admin reset: it is
explicit, it writes a JSON backup first, and it is the only way to get a clean
registry for a demo take.

  python scripts/reset_demo_state.py            # report row counts only
  python scripts/reset_demo_state.py --backup   # report + write JSON backup
  python scripts/reset_demo_state.py --apply    # backup, then truncate

The local counterpart (the mock's JSONL replay log) is not touched here: move
artifacts/store.jsonl aside and restart the API instead.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ["decisions", "items", "analysis_documents", "analyses"]
BACKUP = ROOT / "artifacts" / "db-backup"


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("SUPABASE_DB_URL=") and "SUPABASE_DB_URL" not in os.environ:
            os.environ["SUPABASE_DB_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")


def main() -> int:
    load_env()
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        print("SUPABASE_DB_URL not set")
        return 2
    host = dsn.split("@")[-1].split("/")[0] if "@" in dsn else "?"
    print("host:", host)

    import psycopg2
    from psycopg2.extras import RealDictCursor

    with psycopg2.connect(dsn, connect_timeout=20) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            counts = {}
            for table in TABLES:
                cur.execute(f"select count(*) as n from public.{table}")
                counts[table] = cur.fetchone()["n"]
            print("rows:", counts)

            if "--backup" in sys.argv or "--apply" in sys.argv:
                BACKUP.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                dest = BACKUP / f"supabase-{stamp}.json"
                dump = {}
                for table in TABLES:
                    cur.execute(f"select * from public.{table}")
                    dump[table] = [dict(row) for row in cur.fetchall()]
                dest.write_text(json.dumps(dump, default=str, indent=2), encoding="utf-8")
                print("backup:", dest, "bytes:", dest.stat().st_size)

            if "--apply" in sys.argv:
                # The schema forbids DELETE on decisions (append-only trigger).
                # TRUNCATE is the sanctioned admin reset and does not fire the
                # row-level guard; the JSON backup above is the undo path.
                cur.execute(
                    "truncate table public.decisions, public.items, "
                    "public.analysis_documents, public.analyses restart identity cascade"
                )
                conn.commit()
                print("truncated demo tables")
                for table in TABLES:
                    cur.execute(f"select count(*) as n from public.{table}")
                    print(f"{table} now:", cur.fetchone()["n"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
