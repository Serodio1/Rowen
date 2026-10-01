"""Tests for the redraw: swapping cards before round 1."""

from collections import Counter

import pytest

from rowen.data import load_deck
from rowen.engine.actions import Action, EndRedraw, Pass, PlayUnit, Redraw
from rowen.engine.cards import Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.events import CardRedrawn, RedrawEnded
from rowen.engine.game import (
    MAX_REDRAWS,
    IllegalActionError,
    apply,
    legal_actions,
    start_match,
)
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)

DECKS = (load_deck("humans"), load_deck("robots"))


def make_state(
    hand: tuple[Card, ...],
    deck: tuple[Card, ...] = (SCOUT, SCOUT, SCOUT),
    *,
    redraws_left: tuple[int, int] = (MAX_REDRAWS, MAX_REDRAWS),
    current: int = 0,
    round_starter: int = 0,
    seed: int = 7,
) -> GameState:
    """Build a match before round 1, with player 0's hand and deck."""
    return GameState(
        players=(
            PlayerState(deck=deck, hand=hand, redraws_left=redraws_left[0]),
            PlayerState(deck=(KNIGHT,), hand=(KNIGHT,), redraws_left=redraws_left[1]),
        ),
        current=current,
        round_starter=round_starter,
        rng=Rng(seed=seed),
    )


# legal_actions


def test_player_can_swap_any_card_or_end_the_redraw() -> None:
    state = make_state((SNIPER, WAR_HORN))

    assert legal_actions(state) == (
        Redraw(card="sniper"),
        Redraw(card="war-horn"),
        EndRedraw(),
    )


def test_copies_of_a_card_give_one_swap() -> None:
    state = make_state((SNIPER, SNIPER))

    assert legal_actions(state) == (Redraw(card="sniper"), EndRedraw())


def test_no_swap_without_a_card_to_draw() -> None:
    state = make_state((SNIPER,), deck=())

    assert legal_actions(state) == (EndRedraw(),)


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(PlayUnit(card="sniper", row=Row.RANGED), id="play a unit"),
        pytest.param(Pass(), id="pass"),
    ],
)
def test_round_actions_are_illegal_during_the_redraw(action: Action) -> None:
    state = make_state((SNIPER,))

    with pytest.raises(IllegalActionError):
        apply(state, action)


def test_redraw_actions_are_illegal_once_round_one_has_started() -> None:
    state = make_state((SNIPER,), redraws_left=(0, 0))

    assert legal_actions(state) == (PlayUnit(card="sniper", row=Row.RANGED), Pass())
    with pytest.raises(IllegalActionError):
        apply(state, EndRedraw())


# apply: swapping a card


def test_new_card_takes_the_place_of_the_swapped_one() -> None:
    state = make_state((SNIPER, KNIGHT, WAR_HORN), deck=(SCOUT, SNIPER))

    state, events = apply(state, Redraw(card="knight"))

    assert state.players[0].hand == (SNIPER, SCOUT, WAR_HORN)
    assert events == (CardRedrawn(player=0, card="knight", drawn="scout"),)


def test_swapped_card_is_shuffled_back_into_the_deck() -> None:
    state = make_state((SNIPER, KNIGHT), deck=(SCOUT, SNIPER, WAR_HORN))

    state, _ = apply(state, Redraw(card="knight"))

    assert Counter(state.players[0].deck) == Counter((SNIPER, WAR_HORN, KNIGHT))


@pytest.mark.parametrize("seed", range(10))
def test_swapped_card_is_never_drawn_straight_back(seed: int) -> None:
    # The Scout is drawn before the Knight goes into the deck, whatever the
    # shuffle does.
    state = make_state((KNIGHT,), deck=(SCOUT,), seed=seed)

    state, _ = apply(state, Redraw(card="knight"))

    assert state.players[0].hand == (SCOUT,)
    assert state.players[0].deck == (KNIGHT,)


def test_swap_moves_the_rng_on() -> None:
    state = make_state((SNIPER, KNIGHT))

    state, _ = apply(state, Redraw(card="knight"))

    assert state.rng == Rng(seed=7, uses=1)


def test_player_keeps_redrawing_until_their_swaps_run_out() -> None:
    state = make_state((SNIPER, KNIGHT))

    state, _ = apply(state, Redraw(card="knight"))

    assert state.players[0].redraws_left == 1
    assert state.current == 0


def test_redraw_ends_by_itself_after_the_last_swap() -> None:
    state = make_state((SNIPER, KNIGHT), redraws_left=(1, MAX_REDRAWS))

    state, events = apply(state, Redraw(card="knight"))

    assert events == (
        CardRedrawn(player=0, card="knight", drawn="scout"),
        RedrawEnded(player=0),
    )
    assert state.players[0].redraws_left == 0
    assert state.current == 1


# apply: ending the redraw


def test_ending_the_redraw_lets_the_other_player_redraw() -> None:
    state = make_state((SNIPER, KNIGHT))

    state, events = apply(state, EndRedraw())

    assert events == (RedrawEnded(player=0),)
    assert state.players[0].redraws_left == 0
    assert state.current == 1
    assert legal_actions(state) == (Redraw(card="knight"), EndRedraw())


@pytest.mark.parametrize("round_starter", [0, 1])
def test_round_one_starts_with_the_coin_flip_winner_when_both_are_done(
    round_starter: int,
) -> None:
    # Player 0 is done; player 1 ends their redraw last.
    state = make_state(
        (SNIPER,),
        redraws_left=(0, MAX_REDRAWS),
        current=1,
        round_starter=round_starter,
    )

    state, _ = apply(state, EndRedraw())

    assert state.current == round_starter
    assert Pass() in legal_actions(state)


# A whole redraw, with the real decks


def test_match_starts_with_the_coin_flip_winner_redrawing() -> None:
    state = start_match(DECKS, seed=7)

    assert state.current == state.round_starter
    assert [player.redraws_left for player in state.players] == [2, 2]
    assert legal_actions(state)[-1] == EndRedraw()


def test_each_player_swaps_two_cards_at_most_and_keeps_ten() -> None:
    state = start_match(DECKS, seed=7)
    first = state.current
    cards_at_start = [Counter(player.hand + player.deck) for player in state.players]

    # The first player swaps twice, which ends their redraw.
    for _ in range(MAX_REDRAWS):
        state, _ = apply(state, legal_actions(state)[0])
    assert state.current == 1 - first
    # The other player swaps once and ends their redraw.
    state, _ = apply(state, legal_actions(state)[0])
    state, _ = apply(state, EndRedraw())

    assert state.current == first
    assert Pass() in legal_actions(state)
    for player, at_start in zip(state.players, cards_at_start, strict=True):
        assert len(player.hand) == 10
        assert Counter(player.hand + player.deck) == at_start


def test_same_seed_gives_the_same_redraw() -> None:
    def redraw_twice(seed: int) -> GameState:
        state = start_match(DECKS, seed=seed)
        for _ in range(MAX_REDRAWS):
            state, _ = apply(state, legal_actions(state)[0])
        return state

    assert redraw_twice(7) == redraw_twice(7)
    assert redraw_twice(7) != redraw_twice(8)
