"""api_keys is an AUTH table — readable before any tenant is bound.

RLS chicken-and-egg: the engine authenticates by looking up key_hash to learn
WHICH tenant is calling, but api_keys rows are tenant-scoped — with RLS on,
an unbound session sees zero keys and nobody can ever authenticate.
api_keys therefore sits OUTSIDE RLS (its only secret material is a one-way
SHA-256 hash). After lookup, app.current_tenant is bound and everything
downstream remains RLS-enforced.

Revision ID: 0002_auth_scope
Revises: 5faeea006b4b
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_auth_scope"
down_revision: str | None = "5faeea006b4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys")
    op.execute("ALTER TABLE api_keys NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_api_keys ON api_keys "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')::uuid) "
        "WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), '')::uuid)"
    )
