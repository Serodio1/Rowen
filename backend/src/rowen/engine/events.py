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


@dataclass(frozen=True, kw_only=True)
class RoundEnded:
    """Both players passed and the round was scored (rules, section 9).

    Attributes:
        scores: Each player's total at the end of the round: ``scores[0]`` is
            player 0's. They are kept here because the board is cleared
            straight after, when the match goes on.
        winner: The index of the player who won the round, or ``None`` for a
            tie, where both players lose a life.
    """

    scores: tuple[int, int]
    winner: int | None


@dataclass(frozen=True, kw_only=True)
class MatchEnded:
    """A player has no lives left, so the match is over (rules, section 10).

    Attributes:
        winner: The index of the player who won the match, or ``None`` for a
            draw, when both players lost their last life in the same round.
    """

    winner: int | None


# Any event.
type Event = UnitPlayed | PlayerPassed | RoundEnded | MatchEnded
