"""Unit abilities: what each one does (rules, section 7).

The card data refers to an ability by its key, ``Ability``, and each ability is
implemented once, in the part of the engine that matches its kind:

- **Placement**, where the unit goes. Agile needs no code: an Agile unit has
  two rows, so ``legal_actions`` offers both. A Spy goes on the opponent's
  side, as ``side`` says.
- **On play**, once, when the unit is played: Spy, Medic and Muster. Each one
  is a function in the ``ON_PLAY`` table, which ``on_play`` looks up. The
  Medic only starts a choice: the unit to revive is the player's next action,
  ``Revive``, offered by ``legal_actions`` from ``revivable``.
- **Ongoing**, while the unit is on the board: Bond and Inspire, in
  ``scoring``.

So a new on-play ability is one function, with the ``OnPlay`` signature, and
one entry in ``ON_PLAY``.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace

from rowen.engine.cards import Ability, Card, UnitCard
from rowen.engine.events import CardsDrawn, Event, UnitMustered
from rowen.engine.state import GameState, PlayerState, with_player, with_unit

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


def revivable(player: PlayerState) -> tuple[UnitCard, ...]:
    """Return the units in the discard pile that a Medic can revive.

    That is every unit that isn't a Legend (rules, section 7.2).
    """
    return tuple(
        card
        for card in player.discard
        if isinstance(card, UnitCard) and not card.legend
    )


def _medic(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """The player must choose a unit to revive, if there is one."""
    if not revivable(state.players[player]):
        return state, ()
    return replace(state, reviving=True), ()


def _spy(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """The player draws 2 cards, or fewer if their deck has fewer."""
    return _draw(state, player, SPY_DRAWS)


def _muster(
    state: GameState, player: int, unit: UnitCard
) -> tuple[GameState, tuple[Event, ...]]:
    """Play every unit of the same muster group from the player's deck and hand.

    The units from the deck come first, then the ones from the hand, each in
    the order they were in (rules, section 7.2, and D7). The units that arrive
    don't muster again: there are none of their group left to call.
    """
    musterer = state.players[player]
    in_deck = _muster_group(musterer.deck, unit)
    in_hand = _muster_group(musterer.hand, unit)
    musterer = replace(
        musterer,
        deck=tuple(card for card in musterer.deck if card not in in_deck),
        hand=tuple(card for card in musterer.hand if card not in in_hand),
    )
    state = with_player(state, player, musterer)

    events: list[Event] = []
    for cards, from_hand in ((in_deck, False), (in_hand, True)):
        for card in cards:
            # A Muster unit isn't Agile, so it has one row.
            state = with_unit(state, player, card.rows[0], card)
            event = UnitMustered(
                player=player, card=card.id, row=card.rows[0], from_hand=from_hand
            )
            events.append(event)
    return state, tuple(events)


def _muster_group(cards: tuple[Card, ...], unit: UnitCard) -> tuple[UnitCard, ...]:
    """Return the cards that muster with the unit: Muster and the same group."""
    return tuple(
        card
        for card in cards
        if isinstance(card, UnitCard)
        and card.ability is Ability.MUSTER
        and card.group == unit.group
    )


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
    Ability.MEDIC: _medic,
    Ability.MUSTER: _muster,
}
