"""Index the sessions' end and the matches' results; rowen_app can't move a migration.

Each login deletes the sessions that are over (by ``expires_at``), and
GET /stats counts an owner's matches by deck and outcome: both now read an
index instead of the whole table. ``alembic_version`` says which migration
the database is at: only the owner, who runs the migrations, may change it,
not the API's role, which the default privileges (docs/deploy.md) let add
and change rows in every table.

Revision ID: 74afee7675f8
Revises: 46c10521c574
Create Date: 2026-10-29 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "74afee7675f8"
down_revision: str | None = "46c10521c574"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index(
        "ix_matches_stats",
        "matches",
        ["account_id", "player_deck"],
        postgresql_include=["outcome"],
        postgresql_where=sa.text("outcome IS NOT NULL"),
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'rowen_app') THEN
                REVOKE INSERT, UPDATE ON alembic_version FROM rowen_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'rowen_app') THEN
                GRANT INSERT, UPDATE ON alembic_version TO rowen_app;
            END IF;
        END
        $$
        """
    )
    op.drop_index("ix_matches_stats", table_name="matches")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
