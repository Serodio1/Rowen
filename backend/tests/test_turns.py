"""Tests for taking turns: the legal actions and applying them."""

from collections import Counter

import pytest

from rowen.data import load_deck
from rowen.engine.actions import Action, Pass, PlayUnit
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.events import PlayerPassed, UnitPlayed
from rowen.engine.game import (
    IllegalActionError,
    apply,
    legal_actions,
    start_match,
)
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState, RowState

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(
    id="scout",
    name="Scout",
    rows=(Row.MELEE, Row.RANGED),
    strength=3,
    ability=Ability.AGILE,
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)

PLAY_SNIPER = PlayUnit(card="sniper", row=Row.RANGED)
PLAY_KNIGHT = PlayUnit(card="knight", row=Row.MELEE)


def make_state(
    hand_0: tuple[Card, ...],
    hand_1: tuple[Card, ...] = (KNIGHT,),
    *,
    current: int = 0,
    passed: tuple[bool, bool] = (False, False),
) -> GameState:
    """Build a match in round 1 with these hands and an empty board."""
    return GameState(
        players=(
            PlayerState(deck=(), hand=hand_0, passed=passed[0]),
            PlayerState(deck=(), hand=hand_1, passed=passed[1]),
        ),
        current=current,
        rng=Rng(seed=7),
    )


def round_is_over(state: GameState) -> bool:
    return all(player.passed for player in state.players)


# legal_actions


def test_each_unit_can_be_played_on_its_row_or_the_player_passes() -> None:
    state = make_state((SNIPER, KNIGHT))

    assert legal_actions(state) == (PLAY_SNIPER, PLAY_KNIGHT, Pass())


def test_agile_unit_can_be_played_in_melee_or_ranged() -> None:
    state = make_state((SCOUT,))

    assert legal_actions(state) == (
        PlayUnit(card="scout", row=Row.MELEE),
        PlayUnit(card="scout", row=Row.RANGED),
        Pass(),
    )


def test_copies_of_a_card_give_one_action() -> None:
    state = make_state((SNIPER, SNIPER))

    assert legal_actions(state) == (PLAY_SNIPER, Pass())


def test_special_cards_cant_be_played_yet() -> None:
    state = make_state((WAR_HORN,))

    assert legal_actions(state) == (Pass(),)


def test_actions_are_for_the_player_whose_turn_it_is() -> None:
    state = make_state((SNIPER,), (KNIGHT,), current=1)

    assert legal_actions(state) == (PLAY_KNIGHT, Pass())


def test_no_actions_when_both_players_have_passed() -> None:
    state = make_state((SNIPER,), (KNIGHT,), passed=(True, True))

    assert legal_actions(state) == ()


# apply: playing a unit


def test_playing_a_unit_moves_it_from_the_hand_to_its_row() -> None:
    state = make_state((SNIPER, KNIGHT))

    state, events = apply(state, PLAY_SNIPER)

    player = state.players[0]
    assert player.hand == (KNIGHT,)
    assert player.rows[Row.RANGED] == RowState(units=(SNIPER,))
    assert player.rows[Row.MELEE] == RowState()
    assert events == (UnitPlayed(player=0, card="sniper", row=Row.RANGED),)


def test_agile_unit_goes_in_the_row_the_player_chooses() -> None:
    state = make_state((SCOUT, KNIGHT))

    state, _ = apply(state, PlayUnit(card="scout", row=Row.RANGED))

    assert state.players[0].rows[Row.RANGED].units == (SCOUT,)
    assert state.players[0].rows[Row.MELEE].units == ()


def test_playing_a_copy_keeps_the_others_in_hand() -> None:
    state = make_state((SNIPER, KNIGHT, SNIPER))

    state, _ = apply(state, PLAY_SNIPER)

    assert state.players[0].hand == (KNIGHT, SNIPER)


def test_new_unit_goes_after_the_units_already_in_the_row() -> None:
    state = make_state((SNIPER, SCOUT), (KNIGHT, KNIGHT))

    state, _ = apply(state, PLAY_SNIPER)
    state, _ = apply(state, PLAY_KNIGHT)
    state, _ = apply(state, PlayUnit(card="scout", row=Row.RANGED))

    assert state.players[0].rows[Row.RANGED].units == (SNIPER, SCOUT)


def test_unit_goes_on_the_side_of_the_player_who_plays_it() -> None:
    state = make_state((SNIPER,), (KNIGHT, KNIGHT), current=1)

    state, events = apply(state, PLAY_KNIGHT)

    assert state.players[1].rows[Row.MELEE].units == (KNIGHT,)
    assert state.players[0].rows[Row.MELEE].units == ()
    assert events == (UnitPlayed(player=1, card="knight", row=Row.MELEE),)


def test_apply_doesnt_change_the_old_state() -> None:
    state = make_state((SNIPER, KNIGHT))

    apply(state, PLAY_SNIPER)

    assert state == make_state((SNIPER, KNIGHT))


# apply: turns and passing


def test_turn_goes_to_the_opponent() -> None:
    state = make_state((SNIPER, KNIGHT))

    state, _ = apply(state, PLAY_SNIPER)

    assert state.current == 1


def test_passing_marks_the_player_and_gives_the_turn_away() -> None:
    state = make_state((SNIPER,))

    state, events = apply(state, Pass())

    assert state.players[0].passed
    assert not state.players[1].passed
    assert state.current == 1
    assert events == (PlayerPassed(player=0),)


def test_player_keeps_playing_after_the_opponent_has_passed() -> None:
    state = make_state((SNIPER, KNIGHT), passed=(False, True))

    state, _ = apply(state, PLAY_SNIPER)

    assert state.current == 0
    assert legal_actions(state) == (PLAY_KNIGHT, Pass())


def test_round_is_over_when_both_players_have_passed() -> None:
    state = make_state((SNIPER,))

    state, _ = apply(state, Pass())
    state, events = apply(state, Pass())

    assert round_is_over(state)
    assert events == (PlayerPassed(player=1),)
    assert legal_actions(state) == ()


def test_playing_the_last_card_passes_automatically() -> None:
    state = make_state((SNIPER,))

    state, events = apply(state, PLAY_SNIPER)

    assert state.players[0].passed
    assert state.current == 1
    assert events == (
        UnitPlayed(player=0, card="sniper", row=Row.RANGED),
        PlayerPassed(player=0),
    )


def test_last_card_after_the_opponent_has_passed_ends_the_round() -> None:
    state = make_state((KNIGHT,), (SNIPER,), current=1, passed=(True, False))

    state, events = apply(state, PLAY_SNIPER)

    assert round_is_over(state)
    assert events == (
        UnitPlayed(player=1, card="sniper", row=Row.RANGED),
        PlayerPassed(player=1),
    )


# apply: illegal actions


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(PlayUnit(card="knight", row=Row.MELEE), id="card not in hand"),
        pytest.param(PlayUnit(card="sniper", row=Row.MELEE), id="wrong row"),
        pytest.param(PlayUnit(card="scout", row=Row.SIEGE), id="agile in siege"),
        pytest.param(PlayUnit(card="war-horn", row=Row.MELEE), id="special card"),
    ],
)
def test_illegal_action_raises(action: Action) -> None:
    # The opponent holds a Knight, which player 0 can't play.
    state = make_state((SNIPER, SCOUT, WAR_HORN))

    with pytest.raises(IllegalActionError, match="illegal action"):
        apply(state, action)


def test_no_action_is_legal_when_the_round_is_over() -> None:
    state = make_state((SNIPER,), (KNIGHT,), passed=(True, True))

    with pytest.raises(IllegalActionError):
        apply(state, Pass())


# A whole round


def test_every_legal_action_is_accepted_until_the_round_is_over() -> None:
    # The "done when" of issue #11, with the real decks. Each turn tries every
    # legal action, then plays a unit, a different one each turn, and passes
    # only when there is none left.
    decks = (load_deck("humans"), load_deck("robots"))
    state = start_match(decks, seed=7)
    cards_at_start = [Counter(player.hand) for player in state.players]

    for turn in range(100):
        actions = legal_actions(state)
        if not actions:
            break
        for action in actions:
            apply(state, action)
        plays = [action for action in actions if isinstance(action, PlayUnit)]
        state, _ = apply(state, plays[turn % len(plays)] if plays else Pass())

    assert round_is_over(state)
    # Every card left in a hand or played is still there, none lost or copied.
    for player, at_start in zip(state.players, cards_at_start, strict=True):
        played = [unit for row in player.rows.values() for unit in row.units]
        assert Counter(player.hand) + Counter(played) == at_start
