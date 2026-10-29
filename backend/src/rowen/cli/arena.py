"""Let two AIs play many matches against each other: the ``rowen-arena`` command.

It measures how well one level of the AI plays against another, for example
before and after a change to the Monte Carlo AI (ADR 0018). Each AI chooses
from its own player view, as in a match on the site, and the engine applies
the action.

The matches take turns: the two AIs swap seats from one match to the next,
and the decks change every two matches. So both AIs play each deck as often, and
the coin flip in ``start_match`` decides who starts, as in any match.

The result is the share of the decisive matches the first AI won, as ADR 0018
counts it, with a 95% margin of error: a change smaller than the margin may be
luck. Draws are shown apart. It also shows how long each AI takes per move,
since a better AI that is too slow is no good on the site.

The same seed gives the same matches, so a run can be repeated. Printing is
passed in as ``write``: ``print`` in the terminal, a list of lines in the
tests.
"""

import argparse
import math
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import cycle, islice, permutations
from typing import Literal

from rowen.ai import baseline, montecarlo
from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    Action,
    Card,
    Deck,
    PlayerView,
    apply,
    player_view,
    start_match,
)

# Show a line, like ``print``.
type Write = Callable[[str], None]

# The levels of the AI, as the web API names them: Easy is the baseline AI.
type Level = Literal["easy", "normal", "hard"]
LEVELS: tuple[Level, ...] = ("easy", "normal", "hard")

# A match seed or an AI seed chosen from the run's seed is below this.
MAX_SEED = 2**63

# 1.96 standard errors either side hold 95% of the outcomes.
Z_95 = 1.96


@dataclass(frozen=True)
class Tally:
    """What a run of matches gave, for the first AI.

    Attributes:
        wins: The matches the first AI won.
        draws: The matches no one won.
        losses: The matches the second AI won.
        seconds: The time each AI took to choose its moves, in all, by AI.
        moves: The moves each AI chose, by AI.
    """

    wins: int = 0
    draws: int = 0
    losses: int = 0
    seconds: tuple[float, float] = (0.0, 0.0)
    moves: tuple[int, int] = (0, 0)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the ``rowen-arena`` command.

    Args:
        argv: The command-line arguments; by default, the ones the command
            was run with.
    """
    parser = argparse.ArgumentParser(
        prog="rowen-arena", description="Let two levels of the AI play each other."
    )
    parser.add_argument("first", choices=LEVELS, help="the AI being measured")
    parser.add_argument("second", choices=LEVELS, help="the AI it plays against")
    parser.add_argument(
        "--matches", type=int, default=200, help="how many matches (default 200)"
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="the same seed gives the same matches"
    )
    args = parser.parse_args(argv)
    if args.matches < 1:
        parser.error("--matches must be at least 1")
    run(args.first, args.second, args.matches, args.seed, print)


def run(first: Level, second: Level, matches: int, seed: int, write: Write) -> Tally:
    """Play ``matches`` matches between two AIs and show the result.

    Args:
        first: The level of the AI being measured.
        second: The level of the AI it plays against.
        matches: How many matches to play.
        seed: Where all the randomness of the run comes from.
        write: Shows a line.

    Returns:
        The tally of the run, for the first AI.
    """
    rng = random.Random(seed)
    decks = [load_deck(deck_id) for deck_id in deck_ids()]
    # Each pair of decks, both ways round, and each twice: the first AI is
    # player 0, then player 1.
    plan = [(pair, seat) for pair in permutations(decks, 2) for seat in (0, 1)]
    tally = Tally()
    for pair, seat in islice(cycle(plan), matches):
        levels = (first, second) if seat == 0 else (second, first)
        winner, seconds, moves = play_match(
            pair, levels, rng.randrange(MAX_SEED), rng.randrange(MAX_SEED)
        )
        # Back from seats to AIs: the first AI's figures come first.
        if seat == 1:
            seconds, moves = seconds[::-1], moves[::-1]
            winner = None if winner is None else 1 - winner
        tally = Tally(
            wins=tally.wins + (winner == 0),
            draws=tally.draws + (winner is None),
            losses=tally.losses + (winner == 1),
            seconds=(tally.seconds[0] + seconds[0], tally.seconds[1] + seconds[1]),
            moves=(tally.moves[0] + moves[0], tally.moves[1] + moves[1]),
        )
    for line in report(first, second, tally):
        write(line)
    return tally


def play_match(
    decks: tuple[Deck, Deck], levels: tuple[Level, Level], seed: int, ai_seed: int
) -> tuple[int | None, tuple[float, float], tuple[int, int]]:
    """Play one match between two AIs, by player index.

    Args:
        decks: Each player's deck.
        levels: Each player's level of the AI.
        seed: The seed of the match.
        ai_seed: The seed of the AIs' guesses, apart from the match's, as on
            the site (ADR 0018).

    Returns:
        The winner (``None`` for a draw), the seconds each player took to
        choose their moves, and how many moves each chose.
    """
    state = start_match(decks, seed=seed)
    cards = (decks[0].cards, decks[1].cards)
    seconds, moves = [0.0, 0.0], [0, 0]
    view = player_view(state, 0)
    while not view.match_over:
        player = view.current
        mine = player_view(state, player)
        start = time.perf_counter()
        action = choose(mine, levels[player], cards, ai_seed + sum(moves))
        seconds[player] += time.perf_counter() - start
        moves[player] += 1
        state, _ = apply(state, action)
        view = player_view(state, 0)
    return view.winner, (seconds[0], seconds[1]), (moves[0], moves[1])


def choose(
    view: PlayerView,
    level: Level,
    decks: tuple[tuple[Card, ...], tuple[Card, ...]],
    seed: int,
) -> Action:
    """Return the AI's next action at ``level``, as the web API chooses it.

    The Monte Carlo AI guesses the opponent plays their faction's own deck,
    which here is the deck they do play.
    """
    if level == "easy":
        return baseline.choose_action(view)
    samples = (
        montecarlo.NORMAL_SAMPLES if level == "normal" else montecarlo.HARD_SAMPLES
    )
    return montecarlo.choose_action(view, decks=decks, samples=samples, seed=seed)


def report(first: Level, second: Level, tally: Tally) -> list[str]:
    """Return the lines that show a run's result, for the first AI."""
    played = tally.wins + tally.draws + tally.losses
    lines = [f"{played} matches: {first} against {second}."]
    decisive = tally.wins + tally.losses
    if decisive:
        share = tally.wins / decisive
        margin = Z_95 * math.sqrt(share * (1 - share) / decisive)
        lines.append(
            f"{first} won {share:.1%} ± {margin:.1%} of the decisive matches"
            f" ({tally.wins} won, {tally.losses} lost, {tally.draws} drawn)."
        )
    else:
        lines.append(f"No match was decisive ({tally.draws} drawn).")
    times = (
        f"{level} {seconds / max(moves, 1):.3f} s"
        for level, seconds, moves in zip(
            (first, second), tally.seconds, tally.moves, strict=True
        )
    )
    lines.append(f"Time per move: {', '.join(times)}.")
    return lines
