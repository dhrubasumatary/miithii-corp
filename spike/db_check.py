"""First connectivity + capability check against the Supabase dev project.

Verifies: TCP+auth works, Postgres version, pgvector availability,
enables pgvector in the extensions schema (Supabase convention).
Reads DATABASE_URL from the root .env — password never hard-coded.
"""

import os
import sys
from pathlib import Path

import psycopg

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_database_url() -> str:
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    sys.exit("DATABASE_URL not found in .env")


def main() -> int:
    conn = psycopg.connect(load_database_url(), connect_timeout=20)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT version()")
    print("connected:", cur.fetchone()[0][:80])

    cur.execute("SELECT current_database(), current_user, inet_server_addr()::text, version()")
    row = cur.fetchone()
    print(f"db={row[0]} user={row[1]} host={row[2]}")

    cur.execute(
        "SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'"
    )
    ext = cur.fetchone()
    print(f"pgvector available: default={ext[0] if ext else None} installed={ext[1] if ext else None}")

    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
        conn.commit()
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        print("pgvector enabled, version:", cur.fetchone()[0])
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print("vector enable via extensions schema failed, trying default schema:", exc)
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        print("pgvector enabled (default schema), version:", cur.fetchone()[0])

    conn.close()
    print("DB CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
