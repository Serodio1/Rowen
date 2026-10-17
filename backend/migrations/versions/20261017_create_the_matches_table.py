"""Create the matches table.

Each match is its two decks, its seed and the actions played so far, from
which the API plays it again (rowen.api.store), and its version.

Revision ID: a398e9df25d3
Revises:
Create Date: 2026-10-17 10:32:49.811546
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a398e9df25d3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_deck", sa.String(), nullable=False),
        sa.Column("ai_deck", sa.String(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("seed >= 0", name="seed_not_negative"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("matches")
