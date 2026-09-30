"""Tests for the game state."""

import dataclasses

import pytest

from rowen.engine.cards import Row
from rowen.engine.rng import Rng
from rowen.engine.state import STARTING_LIVES, GameState, PlayerState, RowState

PLAYER = PlayerState(deck=(), hand=())
STATE = GameState(players=(PLAYER, PLAYER), current=0, rng=Rng(seed=7))


def test_player_starts_with_an_empty_board() -> None:
    assert PLAYER.rows == {
        Row.MELEE: RowState(),
        Row.RANGED: RowState(),
        Row.SIEGE: RowState(),
    }
    assert PLAYER.weather == ()
    assert PLAYER.discard == ()
    assert PLAYER.lives == STARTING_LIVES
    assert not PLAYER.passed


def test_state_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        STATE.round = 2  # type: ignore[misc]


def test_a_change_builds_a_new_state() -> None:
    next_state = dataclasses.replace(STATE, round=2)

    assert next_state.round == 2
    assert STATE.round == 1
