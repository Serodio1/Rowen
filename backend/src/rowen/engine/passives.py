"""Leaders' passives: rules of a faction's own that work by themselves
(rules, section 12).

Each passive is carried out at the end of a round that doesn't end the match,
while the next one is set up (``game._start_next_round``). A new passive needs
a value in ``decks.Passive``, its text in ``texts.PASSIVE_TEXTS``, its rule
here, and a leader who brings it, in a faction's data file.
"""

from dataclasses import replace

from rowen.engine.cards import Ability, Row, UnitCard
from rowen.engine.decks import Passive
from rowen.engine.events import CardsDrawn, Event, UnitKept
from rowen.engine.state import GameState, PlayerState, with_player

# A unit a player keeps on the board for the next round: its row and the unit.
type Kept = tuple[Row, UnitCard]

# The cards the winner of a round draws, with ``Passive.DRAW_ON_ROUND_WIN``:
# 2, not 1, so the two factions win as often (docs/balance.md).
ROUND_WIN_DRAWS = 2


def unit_to_keep(state: GameState, index: int) -> tuple[Kept | None, GameState]:
    """Return the unit player ``index`` keeps for the next round, if any.

    With ``Passive.KEEP_A_UNIT``, one unit on their side is chosen at random:
    not a Legend, and not a Spy, which the opponent played there. Return the
    state to go on with, since the choice uses its randomness.
    """
    player = state.players[index]
    if _passive(player) is not Passive.KEEP_A_UNIT:
        return None, state
    units = tuple(
        (row, unit)
        for row in Row
        for unit in player.rows[row].units
        if not unit.legend and unit.ability is not Ability.SPY
    )
    if not units:
        return None, state
    order, rng = state.rng.shuffled(units)
    return order[0], replace(state, rng=rng)


def kept_event(index: int, kept: Kept) -> UnitKept:
    """Return the event of player ``index`` keeping a unit."""
    row, unit = kept
    return UnitKept(player=index, card=unit.id, row=row)


def draw_for_winner(
    state: GameState, winner: int | None
) -> tuple[GameState, tuple[Event, ...]]:
    """Let the round's winner draw ``ROUND_WIN_DRAWS`` cards, with
    ``Passive.DRAW_ON_ROUND_WIN``.

    A tie has no winner. A deck with fewer cards gives what it has, and an
    empty one nothing.
    """
    if winner is None:
        return state, ()
    player = state.players[winner]
    if _passive(player) is not Passive.DRAW_ON_ROUND_WIN or not player.deck:
        return state, ()
    cards = player.deck[:ROUND_WIN_DRAWS]
    player = replace(
        player, hand=(*player.hand, *cards), deck=player.deck[ROUND_WIN_DRAWS:]
    )
    return with_player(state, winner, player), (
        CardsDrawn(player=winner, cards=tuple(card.id for card in cards)),
    )


def _passive(player: PlayerState) -> Passive | None:
    """Return the passive the player's leader brings, if they have a leader."""
    return None if player.leader is None else player.leader.passive
