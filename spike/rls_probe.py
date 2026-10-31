"""RLS probe: proves tenant isolation under Postgres Row Level Security.

The pattern miithii will use: one app role, per-request tenant binding via
a session setting (`SET app.current_tenant`), a USING policy keyed on it,
and FORCE ROW LEVEL SECURITY so even the table owner can't bypass.

Expected results (fail-to-read as designed):
  - tenant A session sees only tenant A rows
  - tenant B session sees only tenant B rows
  - no tenant set -> zero rows (fail closed)
  - owner sees rows (postgres superuser) -> documented footgun only

Run against a scratch Postgres on localhost:5433. Exits 1 on any failure.
"""

import sys

import psycopg

DSN = "host=localhost port=5433 dbname=postgres user=postgres"

SETUP = """
DROP TABLE IF EXISTS probe_tickets;
DROP ROLE IF EXISTS probe_app;
CREATE TABLE probe_tickets (
    id int PRIMARY KEY,
    tenant text NOT NULL,
    body text
);
INSERT INTO probe_tickets VALUES (1, 'a', 'secret A1'), (2, 'a', 'secret A2'), (3, 'b', 'secret B1');

CREATE ROLE probe_app LOGIN PASSWORD 'probe';
GRANT SELECT, UPDATE, DELETE ON probe_tickets TO probe_app;

ALTER TABLE probe_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE probe_tickets FORCE ROW LEVEL SECURITY;
CREATE POLICY probe_tenant_isolation ON probe_tickets
    USING (tenant = current_setting('app.current_tenant', true));
"""


def rows(conn, tenant: str | None) -> list[int]:
    with conn.cursor() as cur:
        if tenant is None:
            cur.execute("SELECT id FROM probe_tickets")
        else:
            cur.execute("SELECT id FROM probe_tickets", prepare=None) if False else None
            cur.execute("SELECT id FROM probe_tickets")
    return sorted(r[0] for r in cur.fetchall() or [])


def main() -> int:
    admin = psycopg.connect(DSN)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname='probe_app'")
        if cur.fetchone():
            cur.execute("DROP OWNED BY probe_app; DROP ROLE probe_app")
        cur.execute(SETUP)
    admin.close()

    failures: list[str] = []
    conn = psycopg.connect("host=localhost port=5433 dbname=postgres user=probe_app password=probe")

    def as_tenant(t: str | None) -> list[int]:
        with conn.cursor() as cur:
            if t is None:
                cur.execute("RESET app.current_tenant")
            else:
                cur.execute("SELECT set_config('app.current_tenant', %s, false)", (t,))
            cur.execute("SELECT id FROM probe_tickets")
            return sorted(r[0] for r in cur.fetchall())

    checks = [
        ("tenant A sees only A rows", as_tenant("a"), [1, 2]),
        ("tenant B sees only B rows", as_tenant("b"), [3]),
        ("no tenant set -> zero rows (fail closed)", as_tenant(None), []),
    ]
    for name, got, want in checks:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            failures.append(name)
        print(f"  {status}  {name}: got {got}, want {want}")

    # cross-tenant write must not exist: UPDATE can only touch own rows
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_tenant', 'a', false)")
        cur.execute("UPDATE probe_tickets SET body = body WHERE id = 3")
        if cur.rowcount == 0:
            print("  PASS  cross-tenant UPDATE touches 0 rows")
        else:
            failures.append("cross-tenant update")
            print(f"  FAIL  cross-tenant UPDATE touched {cur.rowcount} rows")
    conn.commit()
    conn.close()

    print()
    if failures:
        print("RLS PROBE FAILED:", failures)
        return 1
    print("RLS PROBE PASSED: tenant isolation holds, fail-closed on unset tenant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
