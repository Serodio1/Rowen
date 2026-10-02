"""Tests for the player view: what each player may see (rules, section 11)."""

from dataclasses import replace

import pytest

from rowen.data import load_deck
from rowen.engine.cards import Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.game import apply, legal_actions, start_match
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState, RowState, with_player
from rowen.engine.view import RowView, UnitView, player_view

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
THICK_FOG = SpecialCard(id="thick-fog", name="Thick Fog", kind=SpecialKind.THICK_FOG)

# Cards held only in hidden places, to check they never show up in a view.
SECRET_HAND = UnitCard(
    id="secret-hand", name="Secret Hand", rows=(Row.MELEE,), strength=1
)
SECRET_DECK = UnitCard(
    id="secret-deck", name="Secret Deck", rows=(Row.MELEE,), strength=1
)
OWN_DECK = UnitCard(
    id="secret-own-deck", name="Secret Own Deck", rows=(Row.MELEE,), strength=1
)
SEED = 987654321


def make_state() -> GameState:
    """Build round 2, where player 0, with one life left, plays next.

    Player 0 has a Knight in melee and a Sniper in ranged, with a War Horn,
    and has played Thick Fog. Player 1 has a Sniper in ranged and has passed.
    Player 1's hand and both decks hold only secret cards.
    """
    first = PlayerState(
        deck=(OWN_DECK, OWN_DECK),
        hand=(KNIGHT, SNIPER),
        rows={
            Row.MELEE: RowState(units=(KNIGHT,)),
            Row.RANGED: RowState(units=(SNIPER,), horn=WAR_HORN),
            Row.SIEGE: RowState(),
        },
        weather=(THICK_FOG,),
        discard=(SCOUT,),
        lives=1,
    )
    second = PlayerState(
        deck=(SECRET_DECK,),
        hand=(SECRET_HAND, SECRET_HAND, SECRET_HAND),
        rows={
            Row.MELEE: RowState(),
            Row.RANGED: RowState(units=(SNIPER,)),
            Row.SIEGE: RowState(),
        },
        passed=True,
    )
    return GameState(
        players=(first, second),
        current=0,
        round_starter=1,
        round=2,
        rng=Rng(seed=SEED, uses=5),
    )


# What stays hidden


def test_the_opponents_hand_both_decks_and_the_rng_stay_hidden() -> None:
    view = player_view(make_state(), 0)

    # The repr shows every field of the view, however deep.
    text = repr(view)
    assert "secret" not in text.lower()
    assert "Rng" not in text
    assert str(SEED) not in text


def test_hidden_cards_are_only_counted() -> None:
    view = player_view(make_state(), 0)

    assert view.players[1].hand_size == 3
    assert view.players[1].deck_size == 1
    assert view.players[0].hand_size == 2
    assert view.players[0].deck_size == 2


def test_each_player_sees_their_own_hand() -> None:
    state = make_state()

    assert player_view(state, 0).hand == (KNIGHT, SNIPER)
    assert player_view(state, 1).hand == (SECRET_HAND, SECRET_HAND, SECRET_HAND)


# What both players see


def test_both_players_see_the_same_of_each_player() -> None:
    state = make_state()

    assert player_view(state, 0).players == player_view(state, 1).players


def test_units_come_with_their_current_strength_and_rows_with_their_score() -> None:
    side = player_view(make_state(), 1).players[0]

    # Under Thick Fog, with a War Horn, the Sniper is 1 x 2 = 2.
    assert side.rows[Row.RANGED] == RowView(
        units=(UnitView(card=SNIPER, strength=2),),
        horn=WAR_HORN,
        scarecrows=(),
        weathered=True,
        score=2,
    )
    assert side.rows[Row.MELEE].score == 5
    assert not side.rows[Row.MELEE].weathered
    assert side.total == 7


def test_weather_is_shown_on_both_sides() -> None:
    other_side = player_view(make_state(), 0).players[1]

    # Player 0 played the Thick Fog, but player 1's Sniper is under it too.
    assert other_side.rows[Row.RANGED].weathered
    assert other_side.total == 1


def test_the_rest_of_the_match_is_public() -> None:
    view = player_view(make_state(), 1)
    first, second = view.players

    assert first.weather == (THICK_FOG,)
    assert first.discard == (SCOUT,)
    assert (first.lives, first.passed, first.redraws_left) == (1, False, 0)
    assert (second.lives, second.passed) == (2, True)
    assert (view.player, view.current, view.round, view.reviving) == (1, 0, 2, False)


# What the player can do


def test_only_the_player_whose_turn_it_is_gets_legal_actions() -> None:
    state = make_state()

    assert player_view(state, 0).legal_actions == legal_actions(state)
    assert player_view(state, 0).legal_actions != ()
    assert player_view(state, 1).legal_actions == ()


def test_the_view_says_when_the_match_is_over_and_who_won() -> None:
    state = make_state()
    over = with_player(state, 0, replace(state.players[0], lives=0))

    assert not player_view(state, 0).match_over
    assert player_view(state, 0).winner is None
    view = player_view(over, 0)
    assert view.match_over
    assert view.winner == 1
    assert view.legal_actions == ()


# With the real decks


@pytest.mark.parametrize("seed", range(3))
def test_views_match_the_state_turn_after_turn(seed: int) -> None:
    decks = (load_deck("humans"), load_deck("robots"))
    state = start_match(decks, seed=seed)

    # It starts with the redraw, then goes through the rounds.
    for turn in range(60):
        for player in (0, 1):
            view = player_view(state, player)
            assert view.hand == state.players[player].hand
            assert (view.current, view.round, view.reviving) == (
                state.current,
                state.round,
                state.reviving,
            )
            for index, side in enumerate(view.players):
                public = state.players[index]
                assert side.hand_size == len(public.hand)
                assert side.deck_size == len(public.deck)
                assert side.weather == public.weather
                assert side.discard == public.discard
                assert side.lives == public.lives
                assert side.passed == public.passed
                assert side.redraws_left == public.redraws_left
                assert side.total == player_total(state, index)
            assert "Rng" not in repr(view)
        actions = legal_actions(state)
        if not actions:
            break
        state, _ = apply(state, actions[turn % len(actions)])
