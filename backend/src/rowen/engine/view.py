"""The player view: what one player may see of a match (rules, section 11).

The state holds everything: the opponent's hand, the order of both decks and
the rng, from which the whole match could be replayed. None of that may reach
a player (ADR 0002), so ``player_view`` builds a view of its own, field by
field. It is an allow list: a new field in the state stays hidden until
someone puts it in the view on purpose.

The view also carries what the rules work out from the board: each unit's
current strength, each row's score and each player's total. So nothing outside
the engine needs the rules to show a match.

The events of an action are seen the same way, through ``player_events``: the
cards the opponent drew or swapped are hidden, and only how many is left.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from rowen.engine.actions import Action
from rowen.engine.cards import Card, Row, SpecialCard, UnitCard
from rowen.engine.events import (
    CardRedrawn,
    CardsDrawn,
    Event,
    HornPlayed,
    MatchEnded,
    PlayerPassed,
    RedrawEnded,
    RoundEnded,
    ScarecrowPlayed,
    UnitDestroyed,
    UnitMustered,
    UnitPlayed,
    UnitRevived,
    WeatherCleared,
    WeatherPlayed,
    WildfirePlayed,
)
from rowen.engine.game import legal_actions, match_over, match_winner
from rowen.engine.scoring import unit_strength, weathered_rows
from rowen.engine.state import GameState, PlayerState, RowState


@dataclass(frozen=True, kw_only=True)
class UnitView:
    """A unit on the board, with its current strength.

    Attributes:
        card: The unit.
        strength: Its strength now, with weather and abilities (rules, section 6).
    """

    card: UnitCard
    strength: int


@dataclass(frozen=True, kw_only=True)
class RowView:
    """One row on one side of the board.

    Attributes:
        units: The units in the row, in order, with their current strength.
        horn: The War Horn in the row's horn slot, if there is one.
        scarecrows: The Scarecrows in the row.
        weathered: Whether the row is under weather.
        score: The row's score: the sum of its units' strength.
    """

    units: tuple[UnitView, ...]
    horn: SpecialCard | None
    scarecrows: tuple[SpecialCard, ...]
    weathered: bool
    score: int


@dataclass(frozen=True, kw_only=True)
class SideView:
    """What both players may see of one player: all but their hand and deck.

    Attributes:
        rows: Their side of the board, one ``RowView`` per ``Row``.
        weather: The weather cards they played that are still in play.
        discard: Their discard pile; the last card is the most recent.
        lives: Their lives left.
        passed: Whether they have passed this round.
        redraws_left: How many more cards they can swap before round 1.
        hand_size: How many cards they hold. Only they see which.
        deck_size: How many cards are left in their deck. Nobody sees the
            order, not even them.
        total: Their total: the sum of their rows' scores.
    """

    rows: Mapping[Row, RowView]
    weather: tuple[SpecialCard, ...]
    discard: tuple[Card, ...]
    lives: int
    passed: bool
    redraws_left: int
    hand_size: int
    deck_size: int
    total: int


@dataclass(frozen=True, kw_only=True)
class PlayerView:
    """What one player may see of a match at one moment.

    Attributes:
        player: The index of the player whose view it is.
        hand: Their hand, the only one they see.
        players: What both players see of each player, by index:
            ``players[player]`` is this player's own side.
        current: The index of the player whose turn it is, or who is
            redrawing before round 1.
        round: The round being played, from 1 to 3.
        reviving: Whether the player whose turn it is must choose a unit to
            revive, after a Medic.
        legal_actions: What this player can do now. It is empty when it
            isn't their turn.
        match_over: Whether a player has no lives left.
        winner: The index of the player who won the match, or ``None`` while
            it goes on or after a draw.
    """

    player: int
    hand: tuple[Card, ...]
    players: tuple[SideView, SideView]
    current: int
    round: int
    reviving: bool
    legal_actions: tuple[Action, ...]
    match_over: bool
    winner: int | None


@dataclass(frozen=True, kw_only=True)
class OpponentDrew:
    """The opponent drew cards: ``CardsDrawn`` as the other player sees it.

    Attributes:
        player: The index of the player who drew them.
        count: How many cards they drew.
    """

    player: int
    count: int


@dataclass(frozen=True, kw_only=True)
class OpponentRedrew:
    """The opponent swapped a card: ``CardRedrawn`` as the other player sees it.

    Attributes:
        player: The index of the player who swapped it.
    """

    player: int


# An event as one player may see it.
type EventView = Event | OpponentDrew | OpponentRedrew


def player_view(state: GameState, player: int) -> PlayerView:
    """Return what ``player`` may see of the match (rules, section 11).

    Args:
        state: The match.
        player: The player's index, 0 or 1.
    """
    weather = weathered_rows(state)
    over = match_over(state)
    return PlayerView(
        player=player,
        hand=state.players[player].hand,
        players=(
            _side_view(state.players[0], weather),
            _side_view(state.players[1], weather),
        ),
        current=state.current,
        round=state.round,
        reviving=state.reviving,
        legal_actions=legal_actions(state) if player == state.current else (),
        match_over=over,
        winner=match_winner(state) if over else None,
    )


def player_events(events: tuple[Event, ...], player: int) -> tuple[EventView, ...]:
    """Return the events of an action as ``player`` may see them, in order.

    The cards the opponent drew or swapped stay hidden: ``CardsDrawn`` and
    ``CardRedrawn`` become ``OpponentDrew`` and ``OpponentRedrew``. Every
    other event is public: the cards it names are, or were, on the board for
    both players to see (rules, section 11).

    Args:
        events: The events, as ``apply`` returned them.
        player: The player's index, 0 or 1.
    """
    return tuple(_event_view(event, player) for event in events)


def _event_view(event: Event, player: int) -> EventView:
    """Return one event as ``player`` may see it.

    Every kind of event is named here, so a new one can't reach the opponent
    before someone decides what they may see of it: mypy reports a missing
    return until the new kind gets its own case or joins the public ones.
    """
    match event:
        case CardsDrawn() if event.player != player:
            return OpponentDrew(player=event.player, count=len(event.cards))
        case CardRedrawn() if event.player != player:
            return OpponentRedrew(player=event.player)
        # One of these always matches, so the match never falls through.
        case (  # pragma: no branch
            CardsDrawn()
            | CardRedrawn()
            | UnitPlayed()
            | UnitRevived()
            | UnitMustered()
            | WeatherPlayed()
            | WeatherCleared()
            | HornPlayed()
            | ScarecrowPlayed()
            | WildfirePlayed()
            | UnitDestroyed()
            | PlayerPassed()
            | RoundEnded()
            | MatchEnded()
            | RedrawEnded()
        ):
            return event


def _side_view(player: PlayerState, weather: frozenset[Row]) -> SideView:
    """Return what both players may see of one player."""
    rows = {row: _row_view(player.rows[row], weathered=row in weather) for row in Row}
    return SideView(
        rows=rows,
        weather=player.weather,
        discard=player.discard,
        lives=player.lives,
        passed=player.passed,
        redraws_left=player.redraws_left,
        hand_size=len(player.hand),
        deck_size=len(player.deck),
        total=sum(row.score for row in rows.values()),
    )


def _row_view(row: RowState, *, weathered: bool) -> RowView:
    """Return a row with the current strength of each unit and its score."""
    units = tuple(
        UnitView(card=unit, strength=unit_strength(unit, row, weathered=weathered))
        for unit in row.units
    )
    return RowView(
        units=units,
        horn=row.horn,
        scarecrows=row.scarecrows,
        weathered=weathered,
        score=sum(unit.strength for unit in units),
    )
