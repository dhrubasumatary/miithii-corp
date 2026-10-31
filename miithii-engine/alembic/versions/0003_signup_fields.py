"""signup: owner_email + signup_ip on tenants

Self-provisioning (gap #1): POST /v1/signup creates a tenant with an owner
email. One workspace per email (unique partial index); signup_ip powers the
per-IP rate limit. Both nullable — the demo tenant predates signup.

Revision ID: 0003_signup
Revises: 0002_auth_scope
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_signup"
down_revision: str | None = "0002_auth_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("owner_email", sa.String(320), nullable=True))
    op.add_column("tenants", sa.Column("signup_ip", sa.String(64), nullable=True))
    op.create_index(
        "uq_tenants_owner_email",
        "tenants",
        ["owner_email"],
        unique=True,
        postgresql_where=sa.text("owner_email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenants_owner_email", table_name="tenants")
    op.drop_column("tenants", "signup_ip")
    op.drop_column("tenants", "owner_email")
