"""named users: analyses.user_id + users rows are the seat (gap #2)

Revision ID: 0004_named_users
Revises: 0003_signup
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_named_users"
down_revision: str | None = "0003_signup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_analyses_user_id", table_name="analyses")
    op.drop_column("analyses", "user_id")
