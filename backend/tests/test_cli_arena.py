"""Tests for letting two AIs play each other: the rowen-arena command."""

from importlib.metadata import entry_points

import pytest

from rowen.ai import montecarlo
from rowen.cli import arena
from rowen.cli.arena import LEVELS, Level, Tally, choose, main, play_match, report, run
from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    Action,
    Card,
    Deck,
    PlayerView,
    player_view,
    start_match,
)

DECKS = [load_deck(deck_id) for deck_id in deck_ids()]


def test_easy_matches_end_with_a_winner_or_a_draw() -> None:
    lines: list[str] = []

    tally = run("easy", "easy", 4, 1, lines.append)

    assert tally.wins + tally.draws + tally.losses == 4
    # Both AIs chose moves, and the baseline takes some time to choose.
    assert min(tally.moves) > 0
    assert min(tally.seconds) > 0
    assert lines[0] == "4 matches: easy against easy."
    assert lines[-1].startswith("Time per move: easy ")


def test_the_same_seed_gives_the_same_matches() -> None:
    def results(seed: int) -> tuple[int, int, int, tuple[int, int]]:
        tally = run("easy", "easy", 4, seed, lambda line: None)
        return tally.wins, tally.draws, tally.losses, tally.moves

    assert results(7) == results(7)


def test_the_ais_swap_seats_and_play_each_pair_of_decks_both_ways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str, Level, Level]] = []

    def fake_match(
        decks: tuple[Deck, Deck], levels: tuple[Level, Level], seed: int, ai_seed: int
    ) -> tuple[int | None, tuple[float, float], tuple[int, int]]:
        seen.append((decks[0].id, decks[1].id, *levels))
        # Player 0 always wins, in 1 second over 10 moves; player 1 takes 2
        # seconds over 20 moves.
        return 0, (1.0, 2.0), (10, 20)

    monkeypatch.setattr(arena, "play_match", fake_match)
    first, second = (deck.id for deck in DECKS)

    tally = run("hard", "easy", 4, 0, lambda line: None)

    assert seen == [
        (first, second, "hard", "easy"),
        (first, second, "easy", "hard"),
        (second, first, "hard", "easy"),
        (second, first, "easy", "hard"),
    ]
    # Back from seats to AIs: the hard AI won as player 0 and lost as player 1,
    # and its figures come first.
    # Player 0 won each match: each deck once as player 0, so twice.
    assert tally == Tally(
        wins=2,
        draws=0,
        losses=2,
        seconds=(6.0, 6.0),
        moves=(60, 60),
        deck_wins={first: 2, second: 2},
    )


def test_a_match_counts_each_players_moves() -> None:
    winner, seconds, moves = play_match((DECKS[0], DECKS[1]), ("easy", "easy"), 3, 4)

    assert winner in (0, 1, None)
    assert min(seconds) > 0
    # Each player swaps cards or ends the swaps before round 1, and plays or
    # passes in each round after it.
    assert min(moves) >= 2


@pytest.mark.parametrize("level", LEVELS)
def test_each_level_chooses_a_legal_action(level: Level) -> None:
    view = player_view(start_match((DECKS[0], DECKS[1]), seed=5), 0)

    action = choose(view, level, (DECKS[0].cards, DECKS[1].cards), 6)

    assert action in view.legal_actions


def test_each_decision_guesses_with_a_seed_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeds: list[int] = []
    real_choose = arena.choose

    def spy(
        view: PlayerView,
        level: Level,
        decks: tuple[tuple[Card, ...], tuple[Card, ...]],
        seed: int,
    ) -> Action:
        seeds.append(seed)
        return real_choose(view, level, decks, seed)

    monkeypatch.setattr(arena, "choose", spy)

    play_match((DECKS[0], DECKS[1]), ("easy", "easy"), 3, 100)

    # As on the site: the AI seed, plus the moves chosen before.
    assert seeds == list(range(100, 100 + len(seeds)))


@pytest.mark.parametrize(
    ("level", "samples"),
    [("normal", montecarlo.NORMAL_SAMPLES), ("hard", montecarlo.HARD_SAMPLES)],
)
def test_each_monte_carlo_level_tries_its_own_samples(
    monkeypatch: pytest.MonkeyPatch, level: Level, samples: int
) -> None:
    tried: list[int] = []

    def fake_choose_action(view: PlayerView, *, samples: int, **_: object) -> Action:
        tried.append(samples)
        return view.legal_actions[0]

    monkeypatch.setattr(montecarlo, "choose_action", fake_choose_action)
    view = player_view(start_match((DECKS[0], DECKS[1]), seed=5), 0)

    choose(view, level, (DECKS[0].cards, DECKS[1].cards), 6)

    assert tried == [samples]


def test_the_report_shows_the_share_of_decisive_matches_and_its_margin() -> None:
    tally = Tally(wins=3, draws=2, losses=1, seconds=(1.2, 0.03), moves=(10, 10))

    # 3 of 4 decisive matches is 75%. Its margin is 1.96 standard errors:
    # 1.96 * sqrt(0.75 * 0.25 / 4) = 0.424.
    assert report("hard", "easy", tally) == [
        "6 matches: hard against easy.",
        "hard won 75.0% ± 42.4% of the decisive matches (3 won, 1 lost, 2 drawn).",
        "Time per move: hard 0.120 s, easy 0.003 s.",
    ]


def test_the_report_shows_the_share_each_deck_won() -> None:
    tally = Tally(wins=3, losses=1, deck_wins={"robots": 1, "humans": 3})

    # The same margin as the AIs': 3 of 4 decisive matches, and 1 of 4.
    assert report("easy", "easy", tally)[2:4] == [
        "humans won 75.0% ± 42.4% of the decisive matches.",
        "robots won 25.0% ± 42.4% of the decisive matches.",
    ]


def test_the_report_without_a_decisive_match() -> None:
    assert (
        report("easy", "easy", Tally(draws=1))[1] == "No match was decisive (1 drawn)."
    )


def test_the_command_plays_the_matches_it_is_asked_for(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["easy", "easy", "--matches", "2", "--seed", "9"])

    assert capsys.readouterr().out.startswith("2 matches: easy against easy.\n")


@pytest.mark.parametrize(
    "argv", [["easy", "easy", "--matches", "0"], ["easy", "expert"], ["easy"]]
)
def test_the_command_rejects_bad_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)

    assert exit_info.value.code == 2


def test_the_command_is_installed() -> None:
    commands = entry_points(group="console_scripts", name="rowen-arena")

    assert commands, "no rowen-arena command: run uv sync"
    (command,) = commands
    assert command.load() is main
