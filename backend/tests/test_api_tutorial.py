"""Tests for the tutorial's generator: the script played by the engine."""

from dataclasses import replace

import pytest

from rowen.api.schemas import from_action
from rowen.api.tutorial import SCRIPT, ScriptError, generate
from rowen.engine.public import PlayUnit, Row


def test_each_step_lights_only_the_asked_action() -> None:
    for script_step, step in zip(SCRIPT, generate().steps, strict=True):
        asked = () if script_step.action is None else (from_action(script_step.action),)
        assert step.view.legal_actions == asked


def test_the_player_wins_the_match_in_two_rounds() -> None:
    last = generate().steps[-1].moves[-1].view
    assert last.match_over
    assert last.winner == 0
    assert last.round == 2


def test_the_views_show_only_the_players_hand() -> None:
    for step in generate().steps:
        assert step.view.player == 0
        # The AI's side shows how many cards it holds, never which.
        assert "hand" not in step.view.players[1].model_dump()


def test_the_redraw_is_not_a_step() -> None:
    first = generate().steps[0].view
    assert first.round == 1
    assert first.current == 0
    assert not any(action.type == "end_redraw" for action in first.legal_actions)


def test_a_card_not_in_the_hand_fails_with_the_step() -> None:
    wrong = (replace(SCRIPT[0], target="card:president"),)
    with pytest.raises(ScriptError, match="step 1"):
        generate(wrong)


def test_an_illegal_action_fails_with_the_step() -> None:
    wrong = (replace(SCRIPT[2], action=PlayUnit(card="president", row=Row.SIEGE)),)
    with pytest.raises(ScriptError, match="step 1"):
        generate(wrong)
