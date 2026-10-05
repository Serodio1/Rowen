"""Tests for playing a match in the terminal: the loop and the rowen command."""

import random
import re
from collections.abc import Callable
from importlib.metadata import entry_points

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.cli.play import MAX_SEED, main, play

# A seed where the AI swaps two cards before round 1 and later draws with a
# Spy, while the player always picks the first choice.
AI_SWAPS_AND_DRAWS = 19

# Far more prompts than any match needs, so a test whose answers are never
# accepted fails instead of asking forever.
MAX_PROMPTS = 1000

# The first line of a board, like "Round 2: your turn".
BOARD = re.compile(r"Round \d: ")


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
        if len(self.prompts) > MAX_PROMPTS:
            raise AssertionError(f"asked more than {MAX_PROMPTS} times")
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

    assert player.lines[:5] == [
        "Choose your faction:",
        "   1. Humans",
        "   2. Robots",
        "You play Humans and the AI plays Robots.",
        "Press Ctrl+C to stop.",
    ]
    assert player.lines[-1].startswith("Match over.")


def test_the_player_gets_the_deck_of_the_faction_they_choose() -> None:
    player = Player("2")

    play(1, player.read, player.write)

    assert "You play Robots and the AI plays Humans." in player.lines
    first_board = next(line for line in player.lines if BOARD.match(line))
    assert "  Sentry (10 melee, legend, inspire)" in first_board
    assert "President" not in first_board


def test_a_board_and_a_menu_come_before_each_choice() -> None:
    player = Player()

    play(1, player.read, player.write)

    # Every prompt but the faction's follows an empty line, the board,
    # "Your move:" and the menu. No board is shown at any other time.
    boards = [i for i, line in enumerate(player.lines) if BOARD.match(line)]
    assert len(boards) == len(player.prompts) - 1
    for i in boards:
        assert player.lines[i - 1] == ""
        assert re.match(r"Round \d: your turn\n", player.lines[i])
        assert player.lines[i + 1] == "Your move:"
        assert player.lines[i + 2].startswith("   1. ")

    # The first menu is the redraw.
    first = boards[0]
    assert player.lines[first + 2] == "   1. Swap Downpour"
    assert player.lines[first + 11] == "  10. Keep this hand"
    assert player.prompts[:2] == ["Choose 1-2: ", "Choose 1-10: "]


def test_the_chosen_action_is_the_one_played() -> None:
    # In the redraw, choice 3 is Wildfire, and then choice 1 is Downpour.
    player = Player("1", "3")

    play(1, player.read, player.write)

    assert "You swapped Wildfire for Soldier." in player.lines
    assert "You swapped Downpour for War Horn." in player.lines


def test_a_player_who_always_passes_loses() -> None:
    # The last choice of every menu: keep the hand, then pass every round.
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
    assert first.lines != other.lines


# What the player sees of the AI


def test_the_cards_the_ai_draws_or_swaps_never_show() -> None:
    player = Player()

    play(AI_SWAPS_AND_DRAWS, player.read, player.write)

    drew = [line for line in player.lines if line.startswith("The AI drew")]
    swapped = [line for line in player.lines if line.startswith("The AI swapped")]
    assert drew
    assert all(re.fullmatch(r"The AI drew \d+ cards?\.", line) for line in drew)
    assert swapped == ["The AI swapped a card."] * 2


def test_the_seed_never_shows_during_the_match() -> None:
    player = Player()

    play(123456, player.read, player.write)

    assert not [line for line in player.lines if "123456" in line]


# Answers


@pytest.mark.parametrize(
    "answer", ["", "abc", "0", "3", "-1", "+2", "1.5", "2²", "02", "1" * 5000]
)
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
# numbers up to 30, which covers the menus and numbers too big for them, and
# any other text. Its simplest answer is 1, which is always a choice, so its
# simplest match has an end.
@settings(deadline=None)
@given(seed=st.integers(min_value=0), data=st.data())
def test_any_answers_lead_to_the_end_of_the_match(
    seed: int, data: st.DataObject
) -> None:
    answers = st.integers(min_value=1, max_value=30).map(str) | st.text(max_size=3)
    player = Player(then=lambda prompt: data.draw(answers))

    play(seed, player.read, player.write)

    assert player.lines[-1].startswith("Match over.")


# The rowen command


def test_rowen_is_the_command_that_runs_main() -> None:
    commands = entry_points(group="console_scripts", name="rowen")

    # The command is installed with the package, so after a change to it the
    # environment needs "uv sync" (which "uv run" does by itself).
    assert commands, "no rowen command: run uv sync"
    (command,) = commands
    assert command.load() is main


def test_the_command_shows_the_seed_once_the_match_is_over(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "1")

    main(["--seed", "3"])

    out = capsys.readouterr().out.splitlines()
    assert out[-2].startswith("Match over.")
    assert out[-1] == "Seed 3. To play this match again: uv run rowen --seed 3"


def test_the_seed_given_is_the_seed_played(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Seed 0 too: a seed given is never replaced by one chosen by chance.
    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    monkeypatch.setattr(random, "randrange", lambda stop: 42)
    player = Player()
    play(0, player.read, player.write)

    main(["--seed", "0"])

    seed = "Seed 0. To play this match again: uv run rowen --seed 0"
    assert capsys.readouterr().out == "\n".join([*player.lines, seed]) + "\n"


def test_without_a_seed_the_command_picks_a_short_one_by_chance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stops: list[int] = []

    def randrange(stop: int) -> int:
        stops.append(stop)
        return 42

    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    monkeypatch.setattr(random, "randrange", randrange)

    main([])

    assert stops == [MAX_SEED]
    assert capsys.readouterr().out.endswith(
        "\nSeed 42. To play this match again: uv run rowen --seed 42\n"
    )


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
        # Like input: show the prompt, then stop while waiting for the answer.
        print(prompt, end="")
        raise stop

    monkeypatch.setattr("builtins.input", read)

    main(["--seed", "1"])

    assert capsys.readouterr().out.endswith(
        "Choose 1-2: \nMatch abandoned.\n"
        "Seed 1. To play this match again: uv run rowen --seed 1\n"
    )
