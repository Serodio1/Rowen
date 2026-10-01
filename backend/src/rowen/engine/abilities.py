"""Unit abilities: what each one does (rules, section 7).

The card data refers to an ability by its key, ``Ability``, and each ability is
implemented once, in the part of the engine that matches its kind:

- **Placement**, where the unit goes. Agile needs no code: an Agile unit has
  two rows, so ``legal_actions`` offers both. A Spy goes on the opponent's
  side, as ``side`` says.
- **On play**, once, when the unit is played: Spy and Muster. Each one is a
  function in the ``ON_PLAY`` table, which ``on_play`` looks up.
- **Ongoing**, while the unit is on the board: Bond and Inspire, in
  ``scoring``.

So a new on-play ability is one function, with the ``OnPlay`` signature, and
one entry in ``ON_PLAY``.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace

from rowen.engine.cards import Ability, UnitCard
from rowen.engine.events import CardsDrawn, Event, UnitMustered
from rowen.engine.state import GameState, with_player, with_unit

# Cards the player of a Spy draws (rules, section 7.2).
SPY_DRAWS = 2

# An on-play ability. It gets the state just after the unit was placed, the
# index of the player who played it and the unit, and returns the new state
# and the events, like ``apply``.
type OnPlay = Callable[[GameState, int, UnitCard], tuple[GameState, tuple[Event, ...]]]


def side(unit: UnitCard, player: int) -> int:
    """Return the index of the side of the board the unit goes on.

    A Spy goes on the opponent's side; any other unit goes on the side of
    ``player``, who plays it (rules, section 5).
    """
    if unit.ability is Ability.SPY:
        return 1 - player
    return player


def on_play(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Carry out the unit's on-play ability, if it has one (rules, section 7.2)."""
    if unit.ability is None or unit.ability not in ON_PLAY:
        return state, ()
    return ON_PLAY[unit.ability](state, player, unit)


def _spy(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """The player draws 2 cards, or fewer if their deck has fewer."""
    return _draw(state, player, SPY_DRAWS)


def _muster(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Play every unit of the same muster group from the player's deck.

    They go in their row, in the order they were in the deck. The cards in the
    hand stay there. The units that arrive don't muster again: there are none
    of their group left in the deck.
    """
    deck = state.players[player].deck
    mustered = tuple(
        card
        for card in deck
        if isinstance(card, UnitCard) and _same_muster_group(card, unit)
    )
    rest = tuple(card for card in deck if card not in mustered)
    state = with_player(state, player, replace(state.players[player], deck=rest))

    events: list[Event] = []
    for card in mustered:
        # A Muster unit isn't Agile, so it has one row.
        state = with_unit(state, player, card.rows[0], card)
        events.append(UnitMustered(player=player, card=card.id, row=card.rows[0]))
    return state, tuple(events)


def _same_muster_group(card: UnitCard, unit: UnitCard) -> bool:
    """Return whether the card musters with the unit."""
    return card.ability is Ability.MUSTER and card.group == unit.group


def _draw(
    state: GameState, player: int, count: int
) -> tuple[GameState, tuple[Event, ...]]:
    """Move up to ``count`` cards from the top of the deck to the end of the hand."""
    drawer = state.players[player]
    cards = drawer.deck[:count]
    if not cards:
        return state, ()
    drawer = replace(drawer, deck=drawer.deck[count:], hand=(*drawer.hand, *cards))
    event = CardsDrawn(player=player, cards=tuple(card.id for card in cards))
    return with_player(state, player, drawer), (event,)


# The on-play abilities, by key.
ON_PLAY: Mapping[Ability, OnPlay] = {
    Ability.SPY: _spy,
    Ability.MUSTER: _muster,
}
