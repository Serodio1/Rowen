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
        side: The index of the player whose side of the board it went on:
            the opponent's for a Spy, the player's own for any other unit.
    """

    player: int
    card: str
    row: Row
    side: int


@dataclass(frozen=True, kw_only=True)
class PlayerPassed:
    """A player passed, by choice or because their hand is empty.

    Attributes:
        player: The index of the player who passed.
    """

    player: int


@dataclass(frozen=True, kw_only=True)
class UnitMustered:
    """A Muster called a unit to the board from its player's deck or hand.

    Attributes:
        player: The index of the player whose card and side it is.
        card: The id of the unit.
        row: The row it went in.
        from_hand: Whether it came from the hand; if not, from the deck.
    """

    player: int
    card: str
    row: Row
    from_hand: bool


@dataclass(frozen=True, kw_only=True)
class CardsDrawn:
    """A player drew cards from their deck into their hand.

    Only that player may know which cards they are, so the opponent's view of
    this event must leave them out and keep only how many there are.

    Attributes:
        player: The index of the player who drew them.
        cards: The ids of the cards drawn, in the order they were drawn.
    """

    player: int
    cards: tuple[str, ...]


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


@dataclass(frozen=True, kw_only=True)
class CardRedrawn:
    """A player swapped a card in their hand before round 1.

    Only that player may know which cards they are, so the opponent's view of
    this event must leave them out.

    Attributes:
        player: The index of the player who swapped the card.
        card: The id of the card that went back into the deck.
        drawn: The id of the card drawn in its place.
    """

    player: int
    card: str
    drawn: str


@dataclass(frozen=True, kw_only=True)
class RedrawEnded:
    """A player is done redrawing, by choice or after their last swap.

    Attributes:
        player: The index of the player who is done.
    """

    player: int


# Any event.
type Event = (
    UnitPlayed
    | UnitMustered
    | CardsDrawn
    | PlayerPassed
    | RoundEnded
    | MatchEnded
    | CardRedrawn
    | RedrawEnded
)
