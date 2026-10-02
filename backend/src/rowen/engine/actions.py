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


@dataclass(frozen=True, kw_only=True)
class PlaySpecial:
    """Play a special card from the hand that needs no choice (rules, section 8).

    That is a weather card or Clear Skies.

    Attributes:
        card: The id of the special card. Any copy in the hand will do.
    """

    card: str


@dataclass(frozen=True, kw_only=True)
class PlayHorn:
    """Play a War Horn from the hand in one of the player's rows (rules, section 8).

    Attributes:
        card: The id of the War Horn. Any copy in the hand will do.
        row: The row whose horn slot it goes in, which must be empty.
    """

    card: str
    row: Row


@dataclass(frozen=True)
class Pass:
    """Take no more turns this round (rules, section 4)."""


@dataclass(frozen=True, kw_only=True)
class Revive:
    """After playing a Medic, play a unit from the discard pile (rules, 7.2).

    Attributes:
        card: The id of the unit, which can't be a Legend. Any copy in the
            discard pile will do.
        row: The row to play it in, one of the unit's rows.
    """

    card: str
    row: Row


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
type Action = PlayUnit | PlaySpecial | PlayHorn | Pass | Revive | Redraw | EndRedraw
