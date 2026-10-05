"""Tests for playing a match in the terminal: the loop and the rowen command."""

import random
import re
from collections.abc import Callable
from importlib.metadata import entry_points

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.cli.play import main, play

# A seed where the AI swaps two cards before round 1 and later draws with a
# Spy, while the player always picks the first choice.
AI_SWAPS_AND_DRAWS = 19


class Player:
    """A scripted player: answers each prompt in turn and keeps every line shown.

    Once the answers run out, ``then`` answers the rest: by default, the first
    choice of every menu.
    """

    def __init__(
        self, *answers: str, then: Callable[[str], str] = lambda prompt: "1"
    ) -> None:
        self.answers = list(answers)
        self.then = then
        self.prompts: list[str] = []
        self.lines: list[str] = []

    def read(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.answers:
            return self.answers.pop(0)
        return self.then(prompt)

    def write(self, line: str) -> None:
        self.lines.append(line)


def last_choice(prompt: str) -> str:
    """Answer a menu, whose prompt is like ``Choose 1-12: ``, with its last number."""
    return prompt.removeprefix("Choose 1-").removesuffix(": ")


# A whole match


def test_a_match_is_played_to_the_end() -> None:
    player = Player()

    play(1, player.read, player.write)

    assert player.lines[:6] == [
        "Choose your faction:",
        "   1. Humans",
        "   2. Robots",
        "You play Humans and the AI plays Robots.",
        "Seed 1: to play this match again, run rowen --seed 1.",
        "Press Ctrl+C to stop.",
    ]
    assert player.lines[-1].startswith("Match over.")


def test_the_player_chooses_their_faction_and_the_ai_plays_the_other() -> None:
    player = Player("2")

    play(1, player.read, player.write)

    assert "You play Robots and the AI plays Humans." in player.lines


def test_the_board_and_the_menu_come_before_each_choice() -> None:
    player = Player()

    play(1, player.read, player.write)

    # After the faction, each prompt follows an empty line, the board, "Your
    # move:" and the menu, which ends with keeping the hand in the redraw and
    # passing later.
    board = player.lines.index("Your move:") - 1
    assert player.lines[board - 1] == ""
    assert player.lines[board].startswith("Round 1: your turn\n")
    assert player.lines[board + 1 : board + 3] == ["Your move:", "   1. Swap Downpour"]
    assert player.lines[board + 11] == "  10. Keep this hand"
    assert player.prompts[:2] == ["Choose 1-2: ", "Choose 1-10: "]


def test_the_chosen_action_is_the_one_played() -> None:
    # Always the last choice: keep the hand, then pass every round.
    player = Player("1", then=last_choice)

    play(1, player.read, player.write)

    assert "You finished swapping." in player.lines
    assert "You passed." in player.lines
    assert not [line for line in player.lines if line.startswith("You played")]
    assert player.lines[-1] == "Match over. The AI won the match."


def test_the_same_seed_and_answers_give_the_same_match() -> None:
    first, second, other = Player(), Player(), Player()

    play(5, first.read, first.write)
    play(5, second.read, second.write)
    play(6, other.read, other.write)

    assert first.lines == second.lines
    assert first.lines[5:] != other.lines[5:]


# What the player sees of the AI


def test_the_cards_the_ai_draws_or_swaps_never_show() -> None:
    player = Player()

    play(AI_SWAPS_AND_DRAWS, player.read, player.write)

    drew = [line for line in player.lines if line.startswith("The AI drew")]
    swapped = [line for line in player.lines if line.startswith("The AI swapped")]
    assert drew
    assert all(re.fullmatch(r"The AI drew \d+ cards?\.", line) for line in drew)
    assert swapped == ["The AI swapped a card."] * 2


# Answers


@pytest.mark.parametrize("answer", ["", "abc", "0", "3", "-1", "+2", "1.5", "2²"])
def test_an_invalid_answer_is_asked_again(answer: str) -> None:
    player = Player(answer, "2")

    play(1, player.read, player.write)

    assert player.lines[3:5] == [
        "Type a number from 1 to 2.",
        "You play Robots and the AI plays Humans.",
    ]
    assert player.prompts[:2] == ["Choose 1-2: ", "Choose 1-2: "]


def test_spaces_around_an_answer_are_fine() -> None:
    player = Player(" 2 ")

    play(1, player.read, player.write)

    assert "You play Robots and the AI plays Humans." in player.lines


# Whatever the player types, the match goes on to its end. Hypothesis types
# numbers up to 15, more than any menu has, and any other text. Its simplest
# answer is 1, which is always a choice, so its simplest match has an end.
@settings(deadline=None)
@given(seed=st.integers(min_value=0), data=st.data())
def test_any_answers_lead_to_the_end_of_the_match(
    seed: int, data: st.DataObject
) -> None:
    answers = st.integers(min_value=1, max_value=15).map(str) | st.text(max_size=3)
    player = Player(then=lambda prompt: data.draw(answers))

    play(seed, player.read, player.write)

    assert player.lines[-1].startswith("Match over.")


# The rowen command


def test_rowen_is_the_command_that_runs_main() -> None:
    (command,) = entry_points(group="console_scripts", name="rowen")

    assert command.load() is main


def test_the_command_plays_with_the_seed_given(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "1")

    main(["--seed", "3"])

    out = capsys.readouterr().out
    assert "Seed 3: to play this match again, run rowen --seed 3." in out
    assert "Match over." in out


def test_without_a_seed_the_command_picks_one_by_chance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    monkeypatch.setattr(random, "randrange", lambda stop: 42)

    main([])

    assert "Seed 42: to play this match again" in capsys.readouterr().out


def test_a_seed_must_be_a_whole_number(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--seed", "abc"])

    assert stopped.value.code == 2
    assert "invalid int value: 'abc'" in capsys.readouterr().err


@pytest.mark.parametrize("stop", [KeyboardInterrupt, EOFError])
def test_ctrl_c_or_the_end_of_the_input_abandons_the_match(
    stop: type[BaseException],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def read(prompt: str) -> str:
        raise stop

    monkeypatch.setattr("builtins.input", read)

    main(["--seed", "1"])

    assert capsys.readouterr().out.endswith("\nMatch abandoned.\n")
