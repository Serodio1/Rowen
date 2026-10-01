"""Tests for unit abilities (rules, section 7).

Agile, which only changes where a unit can go, is tested with the turns, in
test_turns.py.
"""

from rowen.engine.actions import Pass, PlayUnit
from rowen.engine.cards import Ability, Card, Row, UnitCard
from rowen.engine.events import (
    CardsDrawn,
    PlayerPassed,
    UnitMustered,
    UnitPlayed,
)
from rowen.engine.game import apply
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
INFORMANT = UnitCard(
    id="informant",
    name="Informant",
    rows=(Row.MELEE,),
    strength=3,
    ability=Ability.SPY,
)
DOUBLE_AGENT = UnitCard(
    id="double-agent",
    name="Double Agent",
    rows=(Row.MELEE,),
    strength=8,
    ability=Ability.SPY,
    legend=True,
)

PLANE = UnitCard(
    id="plane",
    name="Plane",
    rows=(Row.SIEGE,),
    strength=3,
    ability=Ability.MUSTER,
    group="planes",
)
SERVER = UnitCard(
    id="server",
    name="Server",
    rows=(Row.SIEGE,),
    strength=3,
    ability=Ability.MUSTER,
    group="servers",
)

PLAY_INFORMANT = PlayUnit(card="informant", row=Row.MELEE)
PLAY_PLANE = PlayUnit(card="plane", row=Row.SIEGE)
PLANE_PLAYED = UnitPlayed(player=0, card="plane", row=Row.SIEGE, side=0)
FROM_DECK = UnitMustered(player=0, card="plane", row=Row.SIEGE, from_hand=False)
FROM_HAND = UnitMustered(player=0, card="plane", row=Row.SIEGE, from_hand=True)
INFORMANT_PLAYED = UnitPlayed(player=0, card="informant", row=Row.MELEE, side=1)


def make_state(
    hand: tuple[Card, ...],
    deck: tuple[Card, ...] = (SNIPER, SCOUT, KNIGHT),
    *,
    opponent_passed: bool = False,
) -> GameState:
    """Build a round 1 where player 0, with this hand and deck, plays next."""
    return GameState(
        players=(
            PlayerState(deck=deck, hand=hand),
            PlayerState(deck=(), hand=(KNIGHT,), passed=opponent_passed),
        ),
        current=0,
        round_starter=0,
        rng=Rng(seed=7),
    )


# Units without an on-play ability


def test_unit_without_an_on_play_ability_only_goes_on_the_board() -> None:
    state = make_state((KNIGHT, SNIPER))

    state, events = apply(state, PlayUnit(card="knight", row=Row.MELEE))

    assert events == (UnitPlayed(player=0, card="knight", row=Row.MELEE, side=0),)
    assert state.players[0].deck == (SNIPER, SCOUT, KNIGHT)


# Spy


def test_spy_goes_on_the_opponents_side() -> None:
    state, events = apply(make_state((INFORMANT, KNIGHT)), PLAY_INFORMANT)

    assert state.players[1].rows[Row.MELEE].units == (INFORMANT,)
    assert state.players[0].rows[Row.MELEE].units == ()
    assert events[0] == INFORMANT_PLAYED


def test_spys_strength_counts_for_the_opponent() -> None:
    state, _ = apply(make_state((INFORMANT, KNIGHT)), PLAY_INFORMANT)

    assert (player_total(state, 0), player_total(state, 1)) == (0, 3)


def test_player_of_a_spy_draws_two_cards_from_the_top_of_the_deck() -> None:
    state = make_state((INFORMANT, KNIGHT), deck=(SNIPER, SCOUT, KNIGHT))

    state, events = apply(state, PLAY_INFORMANT)

    assert state.players[0].hand == (KNIGHT, SNIPER, SCOUT)
    assert state.players[0].deck == (KNIGHT,)
    assert events == (
        INFORMANT_PLAYED,
        CardsDrawn(player=0, cards=("sniper", "scout")),
    )


def test_spy_draws_one_card_when_the_deck_has_one() -> None:
    state = make_state((INFORMANT, KNIGHT), deck=(SNIPER,))

    state, events = apply(state, PLAY_INFORMANT)

    assert state.players[0].hand == (KNIGHT, SNIPER)
    assert state.players[0].deck == ()
    assert events == (INFORMANT_PLAYED, CardsDrawn(player=0, cards=("sniper",)))


def test_spy_draws_nothing_when_the_deck_is_empty() -> None:
    state = make_state((INFORMANT, KNIGHT), deck=())

    state, events = apply(state, PLAY_INFORMANT)

    assert state.players[0].hand == (KNIGHT,)
    assert events == (INFORMANT_PLAYED,)


def test_spy_played_as_the_last_card_draws_before_the_automatic_pass() -> None:
    # The player has cards again, so they don't pass.
    state = make_state((INFORMANT,), deck=(SNIPER, SCOUT))

    state, events = apply(state, PLAY_INFORMANT)

    assert not state.players[0].passed
    assert state.players[0].hand == (SNIPER, SCOUT)
    assert events == (
        INFORMANT_PLAYED,
        CardsDrawn(player=0, cards=("sniper", "scout")),
    )


def test_spy_played_as_the_last_card_with_an_empty_deck_passes() -> None:
    state = make_state((INFORMANT,), deck=())

    state, events = apply(state, PLAY_INFORMANT)

    assert state.players[0].passed
    assert events == (INFORMANT_PLAYED, PlayerPassed(player=0))


def test_legend_spy_works_like_any_spy() -> None:
    state = make_state((DOUBLE_AGENT, KNIGHT), deck=(SNIPER, SCOUT))

    state, _ = apply(state, PlayUnit(card="double-agent", row=Row.MELEE))

    assert state.players[1].rows[Row.MELEE].units == (DOUBLE_AGENT,)
    assert state.players[0].hand == (KNIGHT, SNIPER, SCOUT)


def test_spy_ends_the_round_in_the_opponents_discard_pile() -> None:
    # Rules, D4. Player 1 has passed, so player 0 plays the Spy and passes.
    state = make_state((INFORMANT, KNIGHT), opponent_passed=True)

    state, _ = apply(state, PLAY_INFORMANT)
    state, _ = apply(state, Pass())

    assert state.round == 2
    assert state.players[1].discard == (INFORMANT,)
    assert state.players[0].discard == ()


# Muster


def test_muster_plays_every_unit_of_its_group_from_the_deck() -> None:
    # The Server musters too, but with another group, so it stays.
    state = make_state((PLANE, KNIGHT), deck=(PLANE, SNIPER, SERVER, PLANE))

    state, events = apply(state, PLAY_PLANE)

    assert state.players[0].rows[Row.SIEGE].units == (PLANE, PLANE, PLANE)
    assert state.players[0].deck == (SNIPER, SERVER)
    assert events == (PLANE_PLAYED, FROM_DECK, FROM_DECK)


def test_muster_plays_its_group_from_the_hand_too() -> None:
    # Rules, D7. The other cards in the hand stay there.
    state = make_state((PLANE, KNIGHT, PLANE, SERVER), deck=(SNIPER,))

    state, events = apply(state, PLAY_PLANE)

    assert state.players[0].hand == (KNIGHT, SERVER)
    assert state.players[0].rows[Row.SIEGE].units == (PLANE, PLANE)
    assert events == (PLANE_PLAYED, FROM_HAND)


def test_muster_plays_the_deck_first_then_the_hand() -> None:
    state = make_state((PLANE, PLANE, KNIGHT), deck=(PLANE,))

    state, events = apply(state, PLAY_PLANE)

    assert state.players[0].rows[Row.SIEGE].units == (PLANE, PLANE, PLANE)
    assert state.players[0].hand == (KNIGHT,)
    assert state.players[0].deck == ()
    assert events == (PLANE_PLAYED, FROM_DECK, FROM_HAND)


def test_mustered_units_count_for_the_score() -> None:
    state = make_state((PLANE, KNIGHT, PLANE), deck=(PLANE,))

    state, _ = apply(state, PLAY_PLANE)

    assert player_total(state, 0) == 9


def test_muster_with_none_of_its_group_left_only_plays_itself() -> None:
    state = make_state((PLANE, KNIGHT, SERVER), deck=(SNIPER, SERVER))

    state, events = apply(state, PLAY_PLANE)

    assert state.players[0].rows[Row.SIEGE].units == (PLANE,)
    assert state.players[0].hand == (KNIGHT, SERVER)
    assert state.players[0].deck == (SNIPER, SERVER)
    assert events == (PLANE_PLAYED,)


def test_muster_that_empties_the_hand_passes_automatically() -> None:
    # The other Plane leaves the hand too, so it is empty afterwards.
    state = make_state((PLANE, PLANE), deck=(SNIPER,))

    state, events = apply(state, PLAY_PLANE)

    assert state.players[0].hand == ()
    assert state.players[0].passed
    assert events == (PLANE_PLAYED, FROM_HAND, PlayerPassed(player=0))
