"""Keep the owner and the result of each match.

A match started by a player who is logged in has their account as its owner
(account_id), and once it is over, its result: whether the player won, lost
or drew (outcome), each round's totals (rounds) and when it ended (ended_at).
Matches already kept have no owner and no result: they were all a guest's.

The index lists an owner's matches, newest first, without reading the others.

Revision ID: 454029c27a5d
Revises: 517136ed7eac
Create Date: 2026-10-22 12:39:49.860480
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "454029c27a5d"
down_revision: str | None = "517136ed7eac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.add_column("matches", sa.Column("outcome", sa.String(), nullable=True))
    op.add_column(
        "matches",
        sa.Column("rounds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "matches", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_matches_owner", "matches", ["account_id", "created_at", "id"], unique=False
    )
    op.create_foreign_key(
        "matches_account_id_fkey",
        "matches",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "outcome_is_known", "matches", "outcome IN ('won', 'lost', 'drawn')"
    )
    op.create_check_constraint(
        "result_is_whole",
        "matches",
        "(outcome IS NULL) = (ended_at IS NULL)"
        " AND (rounds IS NULL) = (ended_at IS NULL)",
    )


def downgrade() -> None:
    # Without these columns, a player's match would be anyone's, and a
    # finished one would lose its result. Going down only while no match
    # has an owner or a result.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT FROM matches"
            " WHERE account_id IS NOT NULL OR outcome IS NOT NULL)"
        )
    ):
        raise RuntimeError(
            "Some matches have an owner or a result, which only this migration"
            " keeps: not going down."
        )
    op.drop_constraint("result_is_whole", "matches", type_="check")
    op.drop_constraint("outcome_is_known", "matches", type_="check")
    op.drop_constraint("matches_account_id_fkey", "matches", type_="foreignkey")
    op.drop_index("ix_matches_owner", table_name="matches")
    op.drop_column("matches", "ended_at")
    op.drop_column("matches", "rounds")
    op.drop_column("matches", "outcome")
    op.drop_column("matches", "account_id")
