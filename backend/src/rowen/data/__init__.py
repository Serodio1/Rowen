"""The card data: JSON files that define every card and deck.

Reading files is I/O, so it happens here and not in ``rowen.engine`` (ADR 0003).
This package only reads the files; turning their contents into cards and decks,
and checking them, is done by ``rowen.engine.parsing``.

To add a faction, add its deck to ``decks/``; ``deck_ids`` finds it by itself.
"""

import json
from importlib.resources import files

from rowen.engine.decks import Deck
from rowen.engine.parsing import parse_deck, parse_specials

# This package's folder, found through the installed package, so it works
# from any working directory.
_DATA = files(__name__)


def deck_ids() -> list[str]:
    """Return the id of every deck in the data files, in alphabetical order."""
    return sorted(
        file.name.removesuffix(".json")
        for file in (_DATA / "decks").iterdir()
        if file.name.endswith(".json")
    )


def load_deck(deck_id: str) -> Deck:
    """Read a deck and the special cards from the data files.

    Raises:
        ValueError: If there is no deck with that id, or if a file is not valid
            JSON or has invalid data. The message starts with the file's name.
    """
    # Checking against the known decks means no other path can be read.
    if deck_id not in deck_ids():
        raise ValueError(f"unknown deck {deck_id}")

    try:
        specials = parse_specials(_read_json("specials.json"))
    except ValueError as error:
        raise ValueError(f"specials.json: {error}") from error
    try:
        return parse_deck(_read_json("decks", f"{deck_id}.json"), specials)
    except ValueError as error:
        raise ValueError(f"{deck_id}.json: {error}") from error


def _read_json(*path: str) -> object:
    """Read and decode a JSON file from this package."""
    return json.loads(_DATA.joinpath(*path).read_text(encoding="utf-8"))
