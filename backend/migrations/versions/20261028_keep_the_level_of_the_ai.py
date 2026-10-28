"""Keep the level of the AI the player chose for each match.

The AI plays its moves to come at that level (ADR 0018). The matches kept so
far were all played by the baseline AI, which is the easy level, so they get
"easy".

Revision ID: 46c10521c574
Revises: 1f6485057102
Create Date: 2026-10-28 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "46c10521c574"
down_revision: str | None = "1f6485057102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("ai_level", sa.String(), server_default="easy", nullable=False),
    )
    op.create_check_constraint(
        "ai_level_is_known", "matches", "ai_level IN ('easy', 'normal', 'hard')"
    )


def downgrade() -> None:
    # Without the column, a match goes on with the baseline AI, whatever
    # level it was started at: it still plays, only less well.
    op.drop_constraint("ai_level_is_known", "matches", type_="check")
    op.drop_column("matches", "ai_level")
