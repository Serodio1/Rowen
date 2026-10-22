"""Create the accounts and sessions tables.

Each account is a username and its password's hash, and each session the hash
of its token, its account and when it expires (rowen.api.accounts).

The API's own role, rowen_app, may read, add and change the rows of every
table the migrations make, but not delete them (docs/deploy.md). Logging out
deletes a session, so it may also delete sessions. Only where that role
exists: in Docker Compose and in the tests, the API connects as the owner.

Revision ID: 517136ed7eac
Revises: a398e9df25d3
Create Date: 2026-10-22 09:01:52.461417
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "517136ed7eac"
down_revision: str | None = "a398e9df25d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_sessions_account_id"), "sessions", ["account_id"], unique=False
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'rowen_app') THEN
                GRANT DELETE ON sessions TO rowen_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sessions_account_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("accounts")
