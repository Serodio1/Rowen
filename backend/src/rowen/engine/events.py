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
class WeatherPlayed:
    """A player played a weather card into the weather area.

    Attributes:
        player: The index of the player who played it.
        card: The id of the weather card.
        row: The row it affects, on both sides of the board. If that row was
            already under weather, nothing changes.
    """

    player: int
    card: str
    row: Row


@dataclass(frozen=True, kw_only=True)
class WeatherCleared:
    """A player played Clear Skies, which cleared every weather card.

    Each weather card went to the discard pile of the player who played it,
    and the Clear Skies to its player's.

    Attributes:
        player: The index of the player who played the Clear Skies.
        card: The id of the Clear Skies.
    """

    player: int
    card: str


@dataclass(frozen=True, kw_only=True)
class HornPlayed:
    """A player played a War Horn into the horn slot of one of their rows.

    Attributes:
        player: The index of the player who played it, on whose side it is.
        card: The id of the War Horn.
        row: The row whose horn slot it went in.
    """

    player: int
    card: str
    row: Row


@dataclass(frozen=True, kw_only=True)
class ScarecrowPlayed:
    """A player swapped a Scarecrow for a unit on their side of the board.

    The Scarecrow stays in the row until the end of the round, and the unit
    went to the end of the player's hand.

    Attributes:
        player: The index of the player who played it, on whose side it is.
        card: The id of the Scarecrow.
        row: The row it went in.
        unit: The id of the unit that went back to the hand.
    """

    player: int
    card: str
    row: Row
    unit: str


@dataclass(frozen=True, kw_only=True)
class WildfirePlayed:
    """A player played Wildfire, which went to their discard pile.

    The units it destroyed come next, each in a ``UnitDestroyed``.

    Attributes:
        player: The index of the player who played it.
        card: The id of the Wildfire.
    """

    player: int
    card: str


@dataclass(frozen=True, kw_only=True)
class UnitDestroyed:
    """A unit was destroyed and went to the discard pile of the side it was on.

    Attributes:
        side: The index of the player whose side of the board it was on.
        row: The row it was in.
        card: The id of the unit. Copies of a unit in the same row always
            have the same strength, so they are destroyed together.
    """

    side: int
    row: Row
    card: str


@dataclass(frozen=True, kw_only=True)
class PlayerPassed:
    """A player passed, by choice or because their hand is empty.

    Attributes:
        player: The index of the player who passed.
    """

    player: int


@dataclass(frozen=True, kw_only=True)
class UnitRevived:
    """A player chose a unit from their discard pile with a Medic and played it.

    Attributes:
        player: The index of the player who revived it.
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
    | UnitRevived
    | UnitMustered
    | CardsDrawn
    | WeatherPlayed
    | WeatherCleared
    | HornPlayed
    | ScarecrowPlayed
    | WildfirePlayed
    | UnitDestroyed
    | PlayerPassed
    | RoundEnded
    | MatchEnded
    | CardRedrawn
    | RedrawEnded
)
