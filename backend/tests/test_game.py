"""Tests for setting up a match."""

from collections import Counter

from rowen.data import load_deck
from rowen.engine.game import HAND_SIZE, start_match
from rowen.engine.rng import Rng
from rowen.engine.state import STARTING_LIVES

HUMANS = load_deck("humans")
ROBOTS = load_deck("robots")
DECKS = (HUMANS, ROBOTS)


def test_each_player_draws_ten_cards() -> None:
    state = start_match(DECKS, seed=7)

    for player, deck in zip(state.players, DECKS, strict=True):
        assert len(player.hand) == HAND_SIZE == 10
        assert len(player.deck) == len(deck.cards) - HAND_SIZE


def test_no_card_is_lost_or_duplicated() -> None:
    state = start_match(DECKS, seed=7)

    for player, deck in zip(state.players, DECKS, strict=True):
        assert Counter(player.hand + player.deck) == Counter(deck.cards)


def test_decks_are_shuffled() -> None:
    state = start_match(DECKS, seed=7)
    humans = state.players[0]

    assert humans.hand + humans.deck != HUMANS.cards


def test_same_seed_gives_same_match() -> None:
    assert start_match(DECKS, seed=7) == start_match(DECKS, seed=7)


def test_different_seeds_give_different_matches() -> None:
    state = start_match(DECKS, seed=7)
    other = start_match(DECKS, seed=8)

    assert state.players[0].hand != other.players[0].hand


def test_same_deck_is_shuffled_differently_for_each_player() -> None:
    state = start_match((HUMANS, HUMANS), seed=7)

    assert state.players[0].hand != state.players[1].hand


def test_either_player_can_play_first() -> None:
    first_players = {start_match(DECKS, seed=seed).current for seed in range(20)}

    assert first_players == {0, 1}


def test_state_keeps_the_next_rng() -> None:
    # Two shuffles and a coin flip: the next random choice must be a new one.
    state = start_match(DECKS, seed=7)

    assert state.rng == Rng(seed=7, uses=3)


def test_match_starts_in_round_one() -> None:
    state = start_match(DECKS, seed=7)

    assert state.round == 1
    for player in state.players:
        assert player.lives == STARTING_LIVES
        assert not player.passed
        assert player.discard == ()
