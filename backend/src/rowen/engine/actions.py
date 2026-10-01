"""Actions: what the player whose turn it is asks to do (ADR 0003).

An action is only a request, for example "play a Sniper in the ranged row".
Nothing happens until ``apply`` checks it against the legal actions and
carries it out.

An action doesn't say which player it comes from: it is always the player whose
turn it is, ``state.current``.
"""

from dataclasses import dataclass

from rowen.engine.cards import Row


@dataclass(frozen=True, kw_only=True)
class PlayUnit:
    """Play a unit from the hand on one of its rows (rules, section 5).

    Attributes:
        card: The id of the unit. All copies of a card are the same, so any
            copy in the hand will do.
        row: The row to play it in, one of the unit's rows.
    """

    card: str
    row: Row


@dataclass(frozen=True)
class Pass:
    """Take no more turns this round (rules, section 4)."""


@dataclass(frozen=True, kw_only=True)
class Redraw:
    """Before round 1, swap a card in the hand for a new one (rules, section 3).

    Attributes:
        card: The id of the card to swap, special cards included. All copies
            of a card are the same, so any copy in the hand will do.
    """

    card: str


@dataclass(frozen=True)
class EndRedraw:
    """Keep the hand as it is and swap no more cards (rules, section 3)."""


# Any action.
type Action = PlayUnit | Pass | Redraw | EndRedraw
