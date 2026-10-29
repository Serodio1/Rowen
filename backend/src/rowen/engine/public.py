"""The engine's public face: all a client needs to play a match.

A client, such as the CLI or the web API, shows a match to a player and
passes their moves on to the engine. For that it needs four functions:
``start_match`` and ``apply`` to play, and ``player_view`` and
``player_events`` to see what one player may see. It also needs the types
they work with: actions, events, cards, the player view and the match state.
For a deck a player builds, ``build_deck`` checks the player's choice and makes
the deck, and ``choices``, ``max_copies`` and the deck limits say what may be
chosen, for the client to show.

The rest of the engine holds the rules, such as ``legal_actions``, which a
client must not work out for itself (ADR 0002): the legal actions, the scores
and the winner all come in the player view. So a client imports this module
and nothing else from the engine. import-linter checks it for each client
with a contract in ``pyproject.toml``: today, the CLI and the web API.

A client keeps the match state that ``start_match`` and ``apply`` return, to
give it back to ``apply`` and ``player_view``, but never looks inside it: the
state holds what no player may see, such as the seed and the order of both
decks. Its type, ``GameState``, is here only so that a client can name it, for
example to keep the states of many matches, as the web API does.

Everything here is defined elsewhere in the engine: this module only brings it
together. ``__all__`` is the list of what it offers, and mypy rejects
importing from here a name that isn't in it.
"""

from rowen.engine.abilities import on_opponent_side
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlayScarecrow,
    PlaySpecial,
    PlayUnit,
    Redraw,
    Revive,
)
from rowen.engine.cards import (
    WEATHER_ROWS,
    Ability,
    Card,
    Row,
    SpecialCard,
    SpecialKind,
    UnitCard,
)
from rowen.engine.decks import (
    MAX_SPECIALS,
    MIN_UNITS,
    Deck,
    Passive,
    build_deck,
    choices,
    max_copies,
)
from rowen.engine.events import (
    CardRedrawn,
    CardsDrawn,
    Event,
    HornPlayed,
    MatchEnded,
    NothingToRevive,
    PlayerPassed,
    RedrawEnded,
    RoundEnded,
    ScarecrowPlayed,
    UnitDestroyed,
    UnitKept,
    UnitMustered,
    UnitPlayed,
    UnitRevived,
    WeatherCleared,
    WeatherPlayed,
    WildfirePlayed,
)
from rowen.engine.game import IllegalActionError, apply, start_match
from rowen.engine.state import GameState
from rowen.engine.texts import PASSIVE_TEXTS, describe
from rowen.engine.view import (
    EventView,
    OpponentDrew,
    OpponentRedrew,
    PlayerView,
    RowView,
    SideView,
    UnitView,
    player_events,
    player_view,
)

__all__ = [
    "MAX_SPECIALS",
    "MIN_UNITS",
    "PASSIVE_TEXTS",
    "WEATHER_ROWS",
    "Ability",
    "Action",
    "Card",
    "CardRedrawn",
    "CardsDrawn",
    "Deck",
    "EndRedraw",
    "Event",
    "EventView",
    "GameState",
    "HornPlayed",
    "IllegalActionError",
    "MatchEnded",
    "NothingToRevive",
    "OpponentDrew",
    "OpponentRedrew",
    "Pass",
    "Passive",
    "PlayHorn",
    "PlayScarecrow",
    "PlaySpecial",
    "PlayUnit",
    "PlayerPassed",
    "PlayerView",
    "Redraw",
    "RedrawEnded",
    "Revive",
    "RoundEnded",
    "Row",
    "RowView",
    "ScarecrowPlayed",
    "SideView",
    "SpecialCard",
    "SpecialKind",
    "UnitCard",
    "UnitDestroyed",
    "UnitKept",
    "UnitMustered",
    "UnitPlayed",
    "UnitRevived",
    "UnitView",
    "WeatherCleared",
    "WeatherPlayed",
    "WildfirePlayed",
    "apply",
    "build_deck",
    "choices",
    "describe",
    "max_copies",
    "on_opponent_side",
    "player_events",
    "player_view",
    "start_match",
]
