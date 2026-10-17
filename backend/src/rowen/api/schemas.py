"""What the web API sends and receives as JSON, in shapes of its own.

Each class here is a Pydantic model: a mould for one part of a request or a
response. In a response, what isn't in a model isn't sent. ``from_view`` fills
the models of the player view field by field from the engine's, so they are an
allow list on top of the view's own: nothing the view hides can reach a
response (ADR 0002), and a field the engine adds stays out of the API until
someone adds it here on purpose. In a request, a field that is missing, of the
wrong type or unknown turns the request down before any endpoint sees it.

The shapes and names follow the engine's player view and events, so the types
of the browser read like the engine's. Players are known by their index, 0 or
1, as in the engine: in ``PlayerView``, ``player`` is the index of the player
whose view it is, and in an event, of the player it is about.

``from_events`` does the same as ``from_view`` for the events of an action. It
calls ``player_events`` itself, so the cards the opponent drew or swapped stay
hidden: an endpoint gives it the events as ``apply`` returned them.

Each kind of card, of action and of event carries a ``type``, such as
``"pass"``: that is how the browser tells them apart, since ``Pass`` and
``EndRedraw`` have no other field.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rowen.engine import public as engine

# A row, an ability and a kind of special card are strings, so the API sends
# the engine's own values.
from rowen.engine.public import Ability, Row, SpecialKind


class Schema(BaseModel):
    """What every model here has in common.

    A model can't change once made, and a request with a field it doesn't know
    is turned down, instead of the field being left out in silence: sending
    ``{"deck": "humans", "seed": 1}`` is an error, so nobody thinks they chose
    the seed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class UnitCard(Schema):
    """A unit, as ``engine.UnitCard`` describes it."""

    type: Literal["unit"]
    id: str
    name: str
    rows: tuple[Row, ...]
    strength: int
    ability: Ability | None
    group: str | None
    legend: bool


class SpecialCard(Schema):
    """A special card, as ``engine.SpecialCard`` describes it.

    ``weather_row`` is the row a weather card hits, on both sides of the board,
    or null for any other special card. It is a rule, so the API says it: the
    page doesn't know the rules (ADR 0002).
    """

    type: Literal["special"]
    id: str
    name: str
    kind: SpecialKind
    weather_row: Row | None


# Any card, unit or special. Its "type" says which.
type Card = Annotated[UnitCard | SpecialCard, Field(discriminator="type")]


class PlayUnit(Schema):
    """Play a unit from the hand: ``engine.PlayUnit``."""

    type: Literal["play_unit"]
    card: str
    row: Row


class PlaySpecial(Schema):
    """Play a special card that needs no choice: ``engine.PlaySpecial``."""

    type: Literal["play_special"]
    card: str


class PlayHorn(Schema):
    """Play a War Horn: ``engine.PlayHorn``."""

    type: Literal["play_horn"]
    card: str
    row: Row


class PlayScarecrow(Schema):
    """Play a Scarecrow in place of a unit: ``engine.PlayScarecrow``."""

    type: Literal["play_scarecrow"]
    card: str
    row: Row
    unit: str


class Pass(Schema):
    """Take no more turns this round: ``engine.Pass``."""

    type: Literal["pass"]


class Revive(Schema):
    """Revive a unit after a Medic: ``engine.Revive``."""

    type: Literal["revive"]
    card: str
    row: Row


class Redraw(Schema):
    """Swap a card before round 1: ``engine.Redraw``."""

    type: Literal["redraw"]
    card: str


class EndRedraw(Schema):
    """Swap no more cards: ``engine.EndRedraw``."""

    type: Literal["end_redraw"]


# Any action. Its "type" says which.
type Action = Annotated[
    PlayUnit
    | PlaySpecial
    | PlayHorn
    | PlayScarecrow
    | Pass
    | Revive
    | Redraw
    | EndRedraw,
    Field(discriminator="type"),
]


class UnitPlayed(Schema):
    """A player played a unit from their hand: ``engine.UnitPlayed``."""

    type: Literal["unit_played"]
    player: int
    card: str
    row: Row
    side: int


class UnitRevived(Schema):
    """A player revived a unit with a Medic: ``engine.UnitRevived``."""

    type: Literal["unit_revived"]
    player: int
    card: str
    row: Row
    side: int


class UnitMustered(Schema):
    """A Muster called a unit from the deck or hand: ``engine.UnitMustered``."""

    type: Literal["unit_mustered"]
    player: int
    card: str
    row: Row
    from_hand: bool


class CardsDrawn(Schema):
    """The player drew cards: ``engine.CardsDrawn``.

    The player only gets this for their own cards. For the opponent's, they get
    ``OpponentDrew``.
    """

    type: Literal["cards_drawn"]
    player: int
    cards: tuple[str, ...]


class WeatherPlayed(Schema):
    """A player played a weather card: ``engine.WeatherPlayed``."""

    type: Literal["weather_played"]
    player: int
    card: str
    row: Row


class WeatherCleared(Schema):
    """A player played Clear Skies: ``engine.WeatherCleared``."""

    type: Literal["weather_cleared"]
    player: int
    card: str


class HornPlayed(Schema):
    """A player played a War Horn: ``engine.HornPlayed``."""

    type: Literal["horn_played"]
    player: int
    card: str
    row: Row


class ScarecrowPlayed(Schema):
    """A player swapped a Scarecrow for a unit: ``engine.ScarecrowPlayed``."""

    type: Literal["scarecrow_played"]
    player: int
    card: str
    row: Row
    unit: str


class WildfirePlayed(Schema):
    """A player played Wildfire: ``engine.WildfirePlayed``."""

    type: Literal["wildfire_played"]
    player: int
    card: str


class UnitDestroyed(Schema):
    """A unit was destroyed: ``engine.UnitDestroyed``."""

    type: Literal["unit_destroyed"]
    side: int
    row: Row
    card: str


class PlayerPassed(Schema):
    """A player passed: ``engine.PlayerPassed``."""

    type: Literal["player_passed"]
    player: int


class RoundEnded(Schema):
    """Both players passed and the round was scored: ``engine.RoundEnded``."""

    type: Literal["round_ended"]
    scores: tuple[int, int]
    winner: int | None


class MatchEnded(Schema):
    """A player has no lives left: ``engine.MatchEnded``."""

    type: Literal["match_ended"]
    winner: int | None


class CardRedrawn(Schema):
    """The player swapped a card before round 1: ``engine.CardRedrawn``.

    The player only gets this for their own cards. For the opponent's, they get
    ``OpponentRedrew``.
    """

    type: Literal["card_redrawn"]
    player: int
    card: str
    drawn: str


class RedrawEnded(Schema):
    """A player is done redrawing: ``engine.RedrawEnded``."""

    type: Literal["redraw_ended"]
    player: int


class OpponentDrew(Schema):
    """The opponent drew cards, but not which: ``engine.OpponentDrew``."""

    type: Literal["opponent_drew"]
    player: int
    count: int


class OpponentRedrew(Schema):
    """The opponent swapped a card, but not which: ``engine.OpponentRedrew``."""

    type: Literal["opponent_redrew"]
    player: int


# Any event, as the player may see it. Its "type" says which.
type EventView = Annotated[
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
    | OpponentDrew
    | OpponentRedrew,
    Field(discriminator="type"),
]


class UnitView(Schema):
    """A unit on the board, as ``engine.UnitView`` describes it."""

    card: UnitCard
    strength: int


class RowView(Schema):
    """One row on one side of the board, as ``engine.RowView`` describes it."""

    units: tuple[UnitView, ...]
    horn: SpecialCard | None
    scarecrows: tuple[SpecialCard, ...]
    weathered: bool
    score: int


class RowsView(Schema):
    """One side of the board: its three rows, by name.

    The engine keeps them in a mapping from each ``Row``. Here each row has a
    field of its own, so the JSON is the same, but the JSON schema says that
    all three are always there.
    """

    melee: RowView
    ranged: RowView
    siege: RowView


class SideView(Schema):
    """What both players see of one player, as ``engine.SideView`` describes it."""

    rows: RowsView
    weather: tuple[SpecialCard, ...]
    discard: tuple[Card, ...]
    lives: int
    passed: bool
    redraws_left: int
    hand_size: int
    deck_size: int
    total: int


class PlayerView(Schema):
    """What one player may see of a match, as ``engine.PlayerView`` describes it."""

    player: int
    hand: tuple[Card, ...]
    players: tuple[SideView, SideView]
    current: int
    round: int
    reviving: bool
    legal_actions: tuple[Action, ...]
    match_over: bool
    winner: int | None


class DeckSummary(Schema):
    """A deck the player can choose: its id, to start a match, and its name."""

    id: str
    name: str


class Decks(Schema):
    """The decks a player can choose from, in alphabetical order of their ids.

    The answer is an object with a list in it, not a bare list, like every
    other answer of the API, so it can get more fields later.
    """

    decks: tuple[DeckSummary, ...]


class NewMatch(Schema):
    """What the player sends to start a match: the id of their deck."""

    deck: str


class Match(Schema):
    """A match as the player may see it: its id, its version and the view.

    The id is all it takes to see and play the match, so only its player gets
    it. The version goes up each time the match changes: a move sends back the
    version of the view it was chosen from.
    """

    id: UUID
    version: int
    view: PlayerView


class Played(Match):
    """A match after moves were played in it, and what happened.

    ``events`` holds the events of those moves, in order, as the player may see
    them: in a new match, those of the AI's first moves, if it starts (none if
    the player does); after the player's action, those of the action and then
    those of the AI's answer.
    """

    events: tuple[EventView, ...]


class Move(Schema):
    """What the player sends to play: an action, and the version it was chosen at.

    ``action`` is one of the legal actions of the view, sent back as it is,
    and ``version`` is the version of the match that came with that view. If
    the match is at another version by then, the move isn't played.
    """

    version: int
    action: Action


# What went wrong, for a program to read: the browser can show its own text.
# too_many_requests comes from nginx, in front of the API, when an address
# sends more requests than its limits allow (frontend/nginx.conf); the API
# itself never sends it.
type ErrorCode = Literal[
    "invalid_request",
    "unknown_deck",
    "match_not_found",
    "illegal_action",
    "match_changed",
    "not_found",
    "method_not_allowed",
    "server_error",
    "too_many_requests",
]


class Error(Schema):
    """What the API sends when it turns a request down.

    ``code`` says what went wrong, for the browser, and ``message`` says it in
    words, for a person. A message may say where in the request the mistake
    is, even with the name of a field the API doesn't know, but it never holds
    a value from the request: a value can be nested too deep to send back.
    A request over 16 KB never reaches the API: nginx turns it down with a
    page of its own, not this error.
    """

    code: ErrorCode
    message: str


def from_view(view: engine.PlayerView) -> PlayerView:
    """Return the player view as the API sends it."""
    return PlayerView(
        player=view.player,
        hand=tuple(_card(card) for card in view.hand),
        players=(_side(view.players[0]), _side(view.players[1])),
        current=view.current,
        round=view.round,
        reviving=view.reviving,
        legal_actions=tuple(_action(action) for action in view.legal_actions),
        match_over=view.match_over,
        winner=view.winner,
    )


def _side(side: engine.SideView) -> SideView:
    """Return what both players see of one player, as the API sends it."""
    return SideView(
        rows=RowsView(
            melee=_row(side.rows[Row.MELEE]),
            ranged=_row(side.rows[Row.RANGED]),
            siege=_row(side.rows[Row.SIEGE]),
        ),
        weather=tuple(_special(card) for card in side.weather),
        discard=tuple(_card(card) for card in side.discard),
        lives=side.lives,
        passed=side.passed,
        redraws_left=side.redraws_left,
        hand_size=side.hand_size,
        deck_size=side.deck_size,
        total=side.total,
    )


def _row(row: engine.RowView) -> RowView:
    """Return one row on one side of the board, as the API sends it."""
    return RowView(
        units=tuple(
            UnitView(card=_unit(unit.card), strength=unit.strength)
            for unit in row.units
        ),
        horn=None if row.horn is None else _special(row.horn),
        scarecrows=tuple(_special(card) for card in row.scarecrows),
        weathered=row.weathered,
        score=row.score,
    )


def _card(card: engine.Card) -> Card:
    """Return a card, unit or special, as the API sends it."""
    match card:
        case engine.UnitCard():
            return _unit(card)
        # The last kind left, so the match never falls through.
        case engine.SpecialCard():  # pragma: no branch
            return _special(card)


def _unit(card: engine.UnitCard) -> UnitCard:
    """Return a unit as the API sends it."""
    return UnitCard(
        type="unit",
        id=card.id,
        name=card.name,
        rows=card.rows,
        strength=card.strength,
        ability=card.ability,
        group=card.group,
        legend=card.legend,
    )


def _special(card: engine.SpecialCard) -> SpecialCard:
    """Return a special card as the API sends it."""
    return SpecialCard(
        type="special",
        id=card.id,
        name=card.name,
        kind=card.kind,
        weather_row=engine.WEATHER_ROWS.get(card.kind),
    )


def _action(action: engine.Action) -> Action:
    """Return an action as the API sends it.

    Every kind of action is here, so mypy reports a missing return when a new
    kind has no shape yet.
    """
    match action:
        case engine.PlayUnit():
            return PlayUnit(type="play_unit", card=action.card, row=action.row)
        case engine.PlaySpecial():
            return PlaySpecial(type="play_special", card=action.card)
        case engine.PlayHorn():
            return PlayHorn(type="play_horn", card=action.card, row=action.row)
        case engine.PlayScarecrow():
            return PlayScarecrow(
                type="play_scarecrow",
                card=action.card,
                row=action.row,
                unit=action.unit,
            )
        case engine.Pass():
            return Pass(type="pass")
        case engine.Revive():
            return Revive(type="revive", card=action.card, row=action.row)
        case engine.Redraw():
            return Redraw(type="redraw", card=action.card)
        # The last kind left, so the match never falls through.
        case engine.EndRedraw():  # pragma: no branch
            return EndRedraw(type="end_redraw")


def from_events(events: tuple[engine.Event, ...], player: int) -> tuple[EventView, ...]:
    """Return the events of an action as ``player`` may see them, as the API sends them.

    First, ``engine.player_events`` hides the cards the opponent drew or
    swapped. It is called here, and not left to the endpoint, because mypy
    would not catch an endpoint that forgot it. ``from_view`` can't be given
    the state, since the state isn't a view. But every event ``apply`` returns
    is also an ``engine.EventView``, so mypy would let the events from before
    ``player_events`` through where the ones from after it are expected.

    Args:
        events: The events, as ``engine.apply`` returned them.
        player: The player's index, 0 or 1.
    """
    return tuple(_event(event) for event in engine.player_events(events, player))


def _event(event: engine.EventView) -> EventView:
    """Return an event, as a player may see it, as the API sends it.

    Every kind of event is here, so mypy reports a missing return when a new
    kind has no shape yet.
    """
    match event:
        case engine.UnitPlayed():
            return UnitPlayed(
                type="unit_played",
                player=event.player,
                card=event.card,
                row=event.row,
                side=event.side,
            )
        case engine.UnitRevived():
            return UnitRevived(
                type="unit_revived",
                player=event.player,
                card=event.card,
                row=event.row,
                side=event.side,
            )
        case engine.UnitMustered():
            return UnitMustered(
                type="unit_mustered",
                player=event.player,
                card=event.card,
                row=event.row,
                from_hand=event.from_hand,
            )
        case engine.CardsDrawn():
            return CardsDrawn(
                type="cards_drawn", player=event.player, cards=event.cards
            )
        case engine.WeatherPlayed():
            return WeatherPlayed(
                type="weather_played",
                player=event.player,
                card=event.card,
                row=event.row,
            )
        case engine.WeatherCleared():
            return WeatherCleared(
                type="weather_cleared", player=event.player, card=event.card
            )
        case engine.HornPlayed():
            return HornPlayed(
                type="horn_played", player=event.player, card=event.card, row=event.row
            )
        case engine.ScarecrowPlayed():
            return ScarecrowPlayed(
                type="scarecrow_played",
                player=event.player,
                card=event.card,
                row=event.row,
                unit=event.unit,
            )
        case engine.WildfirePlayed():
            return WildfirePlayed(
                type="wildfire_played", player=event.player, card=event.card
            )
        case engine.UnitDestroyed():
            return UnitDestroyed(
                type="unit_destroyed", side=event.side, row=event.row, card=event.card
            )
        case engine.PlayerPassed():
            return PlayerPassed(type="player_passed", player=event.player)
        case engine.RoundEnded():
            return RoundEnded(
                type="round_ended", scores=event.scores, winner=event.winner
            )
        case engine.MatchEnded():
            return MatchEnded(type="match_ended", winner=event.winner)
        case engine.CardRedrawn():
            return CardRedrawn(
                type="card_redrawn",
                player=event.player,
                card=event.card,
                drawn=event.drawn,
            )
        case engine.RedrawEnded():
            return RedrawEnded(type="redraw_ended", player=event.player)
        case engine.OpponentDrew():
            return OpponentDrew(
                type="opponent_drew", player=event.player, count=event.count
            )
        # The last kind left, so the match never falls through.
        case engine.OpponentRedrew():  # pragma: no branch
            return OpponentRedrew(type="opponent_redrew", player=event.player)


def to_action(action: Action) -> engine.Action:
    """Return the action the player sent as the engine's own.

    It is the other way round from ``_action``. Whether the action is legal is
    for the engine to say: it works out the legal actions of each view.

    Every kind of action is here, so mypy reports a missing return when a new
    kind has no case yet.
    """
    match action:
        case PlayUnit():
            return engine.PlayUnit(card=action.card, row=action.row)
        case PlaySpecial():
            return engine.PlaySpecial(card=action.card)
        case PlayHorn():
            return engine.PlayHorn(card=action.card, row=action.row)
        case PlayScarecrow():
            return engine.PlayScarecrow(
                card=action.card, row=action.row, unit=action.unit
            )
        case Pass():
            return engine.Pass()
        case Revive():
            return engine.Revive(card=action.card, row=action.row)
        case Redraw():
            return engine.Redraw(card=action.card)
        # The last kind left, so the match never falls through.
        case EndRedraw():  # pragma: no branch
            return engine.EndRedraw()
