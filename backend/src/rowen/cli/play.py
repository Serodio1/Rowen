"""Play a match against the AI in the terminal: the ``rowen`` command.

The loop is the same for every turn. It gets the human player's view. On their
turn, it shows the board and the legal actions as a numbered menu and reads
their choice; on the AI's turn, the AI chooses from its own view. Then the
engine applies the action, and the loop shows the events as the human may see
them, until the match is over.

The loop keeps the match state, but never looks inside it: it only passes it
to ``player_view`` and ``apply``. Everything it shows comes from the view and
from ``player_events``, so the AI's hand never shows (ADR 0002).

The seed is shown only once the match is over or abandoned: whoever knows it
can work out the order of every deck, and so the AI's hand. Then it lets the
player play the same match again, for example to report a bug.

Reading and printing are passed in as ``read`` and ``write``: ``input`` and
``print`` in the terminal, a script of answers and a list of lines in the
tests.
"""

import argparse
import random
from collections.abc import Callable, Sequence

from rowen.ai.baseline import choose_action
from rowen.cli.display import action_text, event_text, view_text
from rowen.data import deck_ids, load_deck
from rowen.engine.game import apply, start_match
from rowen.engine.view import player_events, player_view

# Read a line from the player after showing a prompt, like ``input``.
type Read = Callable[[str], str]

# Show a line to the player, like ``print``.
type Write = Callable[[str], None]

# The human player is always player 0 and the AI player 1. The coin flip in
# ``start_match`` still decides who starts.
HUMAN = 0
AI = 1

# A seed chosen by chance is below this, so it is short enough to type.
MAX_SEED = 1_000_000


def main(argv: Sequence[str] | None = None) -> None:
    """Run the ``rowen`` command: play a match against the AI in the terminal.

    Args:
        argv: The command-line arguments; by default, the ones the command
            was run with.
    """
    parser = argparse.ArgumentParser(
        prog="rowen", description="Play a match of Rowen against the AI."
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="the seed of the match; the same seed and the same choices give"
        " the same match",
    )
    args = parser.parse_args(argv)
    seed: int = random.randrange(MAX_SEED) if args.seed is None else args.seed

    try:
        play(seed, input, print)
    # Ctrl+C, or the end of the input (Ctrl+D, or Ctrl+Z on Windows).
    except KeyboardInterrupt, EOFError:
        print("\nMatch abandoned.")
    print(f"Seed {seed}. To play this match again: uv run rowen --seed {seed}")


def play(seed: int, read: Read, write: Write) -> None:
    """Play a whole match: the human player against the AI.

    The player chooses a faction first, and the AI plays another one.

    Args:
        seed: Where all the randomness of the match comes from.
        read: Reads the player's answer to a prompt.
        write: Shows a line to the player.
    """
    decks = [load_deck(deck_id) for deck_id in deck_ids()]
    write("Choose your faction:")
    yours = decks[_choose([deck.name for deck in decks], read, write)]
    theirs = next(deck for deck in decks if deck.id != yours.id)
    names = {card.id: card.name for deck in decks for card in deck.cards}

    write(f"You play {yours.name} and the AI plays {theirs.name}.")
    write("Press Ctrl+C to stop.")

    state = start_match((yours, theirs), seed=seed)
    view = player_view(state, HUMAN)
    while not view.match_over:
        if view.current == HUMAN:
            write("")
            write(view_text(view))
            write("Your move:")
            labels = [action_text(action, names) for action in view.legal_actions]
            action = view.legal_actions[_choose(labels, read, write)]
        else:
            action = choose_action(player_view(state, AI))

        state, events = apply(state, action)
        for event in player_events(events, HUMAN):
            write(event_text(event, HUMAN, names))
        view = player_view(state, HUMAN)


def _choose(labels: Sequence[str], read: Read, write: Write) -> int:
    """Show a numbered menu and return the index of the label the player picks.

    The menu starts at 1. Until the answer is one of its numbers, as it is
    shown, the player is told so and asked again.
    """
    numbers = [str(number) for number in range(1, len(labels) + 1)]
    for number, label in zip(numbers, labels, strict=True):
        write(f"{number:>4}. {label}")
    while True:
        answer = read(f"Choose 1-{len(labels)}: ").strip()
        if answer in numbers:
            return numbers.index(answer)
        write(f"Type a number from 1 to {len(labels)}.")
