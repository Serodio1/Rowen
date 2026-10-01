"""Events: what happened when an action was applied (ADR 0003).

The new state says how the match *is*; the events say what *happened* to get
there, in order. The frontend uses them to know what to animate, without
comparing the old and the new state.
"""

from dataclasses import dataclass

from rowen.engine.cards import Row


@dataclass(frozen=True, kw_only=True)
class UnitPlayed:
    """A player played a unit from their hand.

    Attributes:
        player: The index of the player who played it.
        card: The id of the unit.
        row: The row it was played in.
    """

    player: int
    card: str
    row: Row


@dataclass(frozen=True, kw_only=True)
class PlayerPassed:
    """A player passed, by choice or because their hand is empty.

    Attributes:
        player: The index of the player who passed.
    """

    player: int


# Any event.
type Event = UnitPlayed | PlayerPassed
