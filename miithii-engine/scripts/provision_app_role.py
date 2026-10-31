"""Create/rotate the miithii_app role (NOBYPASSRLS) and grant table access.

The ENGINE connects as miithii_app — RLS (migration 0001) is the only thing
between tenants. Migrations run as the admin role via DATABASE_URL_ADMIN.

Updates DATABASE_URL in the workspace .env when present (local flow); with
--no-env-write (CI) it only prints the app URL so CI can pass it to pytest.
"""

import argparse
import os
import secrets
import sys
import urllib.parse
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]  # repo root (holds .env)
ENV_FILE = ROOT / ".env"
ROLE = "miithii_app"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def build_app_url(admin_url: str, password: str) -> str:
    parsed = urllib.parse.urlparse(admin_url)
    netloc = f"{ROLE}.{parsed.username.split('.', 1)[1] if '.' in (parsed.username or '') else parsed.username}:{urllib.parse.quote(password, safe='')}"
    # Supabase pooler usernames are "role.projectref"; direct hosts are plain "role".
    if "." in (parsed.username or ""):
        netloc = f"{ROLE}.{parsed.username.split('.', 1)[1]}:{urllib.parse.quote(password, safe='')}@{parsed.hostname}:{parsed.port}"
    else:
        netloc = f"{ROLE}:{urllib.parse.quote(password, safe='')}@{parsed.hostname}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-env-write", action="store_true", help="CI: don't touch .env")
    args = parser.parse_args()

    env = load_env()
    admin_url = os.getenv("DATABASE_URL_ADMIN") or env.get("DATABASE_URL_ADMIN") or env.get("DATABASE_URL")
    if not admin_url:
        print("ERROR: no admin URL (DATABASE_URL_ADMIN)", file=sys.stderr)
        return 1

    password = secrets.token_urlsafe(18)
    grants = [
        f"GRANT USAGE ON SCHEMA public, extensions TO {ROLE}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROLE}",
    ]

    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)
        ).fetchone()
        if exists:
            conn.execute(f"ALTER ROLE {ROLE} LOGIN PASSWORD '{password}' NOBYPASSRLS")
            print(f"role {ROLE} already existed — password rotated")
        else:
            conn.execute(f"CREATE ROLE {ROLE} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS")
            print(f"role {ROLE} created")
        for stmt in grants:
            conn.execute(stmt)

    app_url = build_app_url(admin_url, password)

    if args.no_env_write:
        print(app_url)
        return 0

    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
        out: list[str] = []
        replaced = False
        for line in lines:
            if line.startswith("DATABASE_URL="):
                out.append(f"DATABASE_URL={app_url}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            out.append(f"DATABASE_URL={app_url}")
        ENV_FILE.write_text("\n".join(out) + "\n")
        print(f".env DATABASE_URL updated to the {ROLE} pooler URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
