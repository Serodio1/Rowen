"""Keep a copy of the deck a player built in each match they play with it.

A match played with a deck the player built keeps its name (player_deck_name)
and how many copies of each card (player_copies), as they were when it
started, so it plays again the same way whatever happens to the deck
(ADR 0017). player_deck still holds the faction. Both columns are empty for a
match with the faction's own deck, as are all the matches kept so far.

Revision ID: 1f6485057102
Revises: 35aff864c3d9
Create Date: 2026-10-26 17:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1f6485057102"
down_revision: str | None = "35aff864c3d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("player_deck_name", sa.String(), nullable=True))
    op.add_column(
        "matches",
        sa.Column(
            "player_copies", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.create_check_constraint(
        "player_deck_copy_is_whole",
        "matches",
        "(player_copies IS NULL) = (player_deck_name IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("player_deck_copy_is_whole", "matches", type_="check")
    op.drop_column("matches", "player_copies")
    op.drop_column("matches", "player_deck_name")
