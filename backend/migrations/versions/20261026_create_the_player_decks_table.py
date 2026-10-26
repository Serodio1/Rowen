"""Create the player_decks table.

Each row is a deck a player built (rowen.api.player_decks): its account, its
name, the faction whose cards it holds and how many copies of each card.
Deleting an account deletes its decks. The index lists an owner's decks,
oldest first, without reading the others.

Deleting a deck deletes its row, so the API's own role, rowen_app, may also
delete them (as sessions, in 517136ed7eac). Only where that role exists.

Revision ID: 35aff864c3d9
Revises: 454029c27a5d
Create Date: 2026-10-26 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "35aff864c3d9"
down_revision: str | None = "454029c27a5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_decks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("faction", sa.String(), nullable=False),
        sa.Column("copies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_player_decks_owner",
        "player_decks",
        ["account_id", "created_at", "id"],
        unique=False,
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'rowen_app') THEN
                GRANT DELETE ON player_decks TO rowen_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.drop_index("ix_player_decks_owner", table_name="player_decks")
    op.drop_table("player_decks")
