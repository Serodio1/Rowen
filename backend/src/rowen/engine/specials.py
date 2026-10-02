"""Special cards: what each one does (rules, section 8).

The card data refers to a special card's effect by its kind, ``SpecialKind``,
and each effect is implemented once, here. Special cards come in two shapes,
by what the player chooses besides the card:

- **Nothing else:** weather, Clear Skies and Wildfire. Each kind has a
  function in the ``EFFECTS`` table, which ``play`` looks up. The function
  puts the card where it goes: the weather area or the discard pile.
- **A row:** the War Horn, which ``play_horn`` puts in the horn slot of one of
  the player's rows. Only a row in ``free_horn_rows`` will do.

So a new special card that needs no choice is one function, with the
``Effect`` signature, and one entry in ``EFFECTS``. The Scarecrow has no
effect here yet, so it can't be played.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace

from rowen.engine.cards import WEATHER_ROWS, Card, Row, SpecialCard, SpecialKind
from rowen.engine.events import (
    Event,
    HornPlayed,
    UnitDestroyed,
    WeatherCleared,
    WeatherPlayed,
    WildfirePlayed,
)
from rowen.engine.scoring import unit_strength, weathered_rows
from rowen.engine.state import GameState, PlayerState, with_player, without_unit

# The effect of a special card that needs no choice. It gets the state just
# after the card left the hand, the index of the player who played it and the
# card, and returns the new state and the events, like ``apply``.
type Effect = Callable[
    [GameState, int, SpecialCard], tuple[GameState, tuple[Event, ...]]
]


def play(
    state: GameState, player: int, card: SpecialCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Carry out the effect of a special card that needs no choice.

    The card must be of a kind in ``EFFECTS``.
    """
    return EFFECTS[card.kind](state, player, card)


def free_horn_rows(player: PlayerState) -> tuple[Row, ...]:
    """Return the player's rows with an empty horn slot, where a War Horn can go."""
    return tuple(row for row in Row if player.rows[row].horn is None)


def play_horn(
    state: GameState, player: int, card: SpecialCard, row: Row
) -> tuple[GameState, tuple[Event, ...]]:
    """Put the War Horn in the horn slot of one of the player's rows.

    It doubles the strength of the units in that row (``scoring``) until the
    end of the round. The slot must be empty (rules, section 8).
    """
    hornist = state.players[player]
    rows = {**hornist.rows, row: replace(hornist.rows[row], horn=card)}
    state = with_player(state, player, replace(hornist, rows=rows))
    return state, (HornPlayed(player=player, card=card.id, row=row),)


def _weather(
    state: GameState, player: int, card: SpecialCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Put the weather card in the weather area, on the player's side.

    It affects its row on both sides of the board (``scoring``) until Clear
    Skies or the end of the round. A second copy of the same weather stays
    there too, but adds nothing.
    """
    weatherer = state.players[player]
    weatherer = replace(weatherer, weather=(*weatherer.weather, card))
    event = WeatherPlayed(player=player, card=card.id, row=WEATHER_ROWS[card.kind])
    return with_player(state, player, weatherer), (event,)


def _clear_skies(
    state: GameState, player: int, card: SpecialCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Move every weather card, then the Clear Skies, to a discard pile.

    Each weather card goes to the discard pile of the player who played it,
    and the Clear Skies to its player's (rules, section 8). With no weather in
    play, only the Clear Skies goes.
    """
    for index, owner in enumerate(state.players):
        state = with_player(state, index, replace(owner, weather=()))
        state = _discard(state, index, owner.weather)

    state = _discard(state, player, (card,))
    return state, (WeatherCleared(player=player, card=card.id),)


def _wildfire(
    state: GameState, player: int, card: SpecialCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Destroy the strongest units on the board, on both sides, then discard.

    Legends don't count (rules, section 8, and D8): the highest strength is
    that of the strongest unit that isn't a Legend, and every unit with it is
    destroyed, into the discard pile of its side. They are all found before
    any is destroyed, so a Bond unit that would get weaker once another one
    goes is still destroyed. Then the Wildfire goes to its player's discard
    pile.
    """
    weather = weathered_rows(state)
    candidates = [
        (side, row, unit, unit_strength(unit, row_state, weathered=row in weather))
        for side, owner in enumerate(state.players)
        for row, row_state in owner.rows.items()
        for unit in row_state.units
        if not unit.legend
    ]
    highest = max((strength for *_, strength in candidates), default=None)

    events: list[Event] = [WildfirePlayed(player=player, card=card.id)]
    for side, row, unit, strength in candidates:
        if strength == highest:
            state = without_unit(state, side, row, unit)
            state = _discard(state, side, (unit,))
            events.append(UnitDestroyed(side=side, row=row, card=unit.id))

    state = _discard(state, player, (card,))
    return state, tuple(events)


def _discard(state: GameState, player: int, cards: tuple[Card, ...]) -> GameState:
    """Return the state with the cards at the end of a player's discard pile."""
    owner = state.players[player]
    return with_player(state, player, replace(owner, discard=(*owner.discard, *cards)))


# The effects of the special cards that need no choice, by kind.
EFFECTS: Mapping[SpecialKind, Effect] = {
    SpecialKind.HOARFROST: _weather,
    SpecialKind.THICK_FOG: _weather,
    SpecialKind.DOWNPOUR: _weather,
    SpecialKind.CLEAR_SKIES: _clear_skies,
    SpecialKind.WILDFIRE: _wildfire,
}
