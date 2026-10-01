"""The game state: everything about a match at one moment (ADR 0003).

The state is never changed. Every step of the game builds a new state, usually
with ``dataclasses.replace``, and the old one stays as it was.

Unlike cards and decks, which come from data files, a state is only ever built
by the engine's own functions, so it doesn't check itself when it is created.
Its rules are checked by the tests instead.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from rowen.engine.cards import Card, Row, SpecialCard, UnitCard
from rowen.engine.rng import Rng

# Lives each player starts the match with (rules, section 2).
STARTING_LIVES = 2


@dataclass(frozen=True, kw_only=True)
class RowState:
    """One row on one player's side of the board.

    Attributes:
        units: The units in the row, in the order they were played.
        horn: The War Horn in the row's horn slot, if there is one.
    """

    units: tuple[UnitCard, ...] = ()
    horn: SpecialCard | None = None


def empty_rows() -> Mapping[Row, RowState]:
    """Return one empty row for each ``Row``, as at the start of a round."""
    return {row: RowState() for row in Row}


@dataclass(frozen=True, kw_only=True)
class PlayerState:
    """Everything that belongs to one player.

    ``rows`` is a dict, which Python lets anyone change. Its type,
    ``Mapping``, has no way to change it, so mypy rejects any code that tries:
    a new row means a new dict, ``{**player.rows, row: new_row}``.

    Attributes:
        deck: The cards left to draw, face down; the next card drawn is the
            first one.
        hand: The cards in the player's hand.
        rows: The player's side of the board, one ``RowState`` per ``Row``.
        weather: The weather cards this player has played that are still in
            play. Weather affects both players, but each card is kept on the
            side of whoever played it, because that is the discard pile it
            goes to.
        discard: The discard pile, face up; the last card is the most recent.
        lives: Lives left; a player with none has lost the match.
        passed: Whether the player has passed this round.
        redraws_left: How many more cards the player can swap before round 1
            (rules, section 3). It is 0 once they are done redrawing.
    """

    deck: tuple[Card, ...]
    hand: tuple[Card, ...]
    rows: Mapping[Row, RowState] = field(default_factory=empty_rows)
    weather: tuple[SpecialCard, ...] = ()
    discard: tuple[Card, ...] = ()
    lives: int = STARTING_LIVES
    passed: bool = False
    redraws_left: int = 0


@dataclass(frozen=True, kw_only=True)
class GameState:
    """A match at one moment: with it, the match can go on from there.

    Attributes:
        players: Both players. They are known by their index, 0 or 1, so the
            opponent of player ``i`` is player ``1 - i``.
        current: The index of the player whose turn it is, or who is
            redrawing before round 1.
        round_starter: The index of the player who had the first turn of this
            round. After a tie, they have it again (rules, section 9).
        round: The round being played, from 1 to 3.
        reviving: Whether the player whose turn it is has just played a Medic
            and must choose a unit from their discard pile to revive (rules,
            section 7.2). Their turn only ends after that choice.
        rng: Where the next random choice comes from.
    """

    players: tuple[PlayerState, PlayerState]
    current: int
    round_starter: int
    round: int = 1
    reviving: bool = False
    rng: Rng


def with_player(state: GameState, index: int, player: PlayerState) -> GameState:
    """Return the state with player ``index`` replaced by ``player``."""
    if index == 0:
        return replace(state, players=(player, state.players[1]))
    return replace(state, players=(state.players[0], player))


def with_unit(state: GameState, side: int, row: Row, unit: UnitCard) -> GameState:
    """Return the state with the unit at the end of a row on one side."""
    player = state.players[side]
    units = (*player.rows[row].units, unit)
    rows = {**player.rows, row: replace(player.rows[row], units=units)}
    return with_player(state, side, replace(player, rows=rows))
