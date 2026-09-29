"""Tests for the card data files and the functions that read them."""

import re
from collections import Counter
from pathlib import Path

import pytest

from rowen import data
from rowen.data import deck_ids, load_deck

# The copies of each card, as listed in docs/cards.md.
HUMANS = {
    "human": 5,
    "soldier": 3,
    "sniper": 3,
    "informant": 2,
    "medic": 1,
    "smart-guy": 3,
    "plane": 4,
    "prime-minister": 1,
    "president": 1,
}
ROBOTS = {
    "robot": 5,
    "machine": 3,
    "drone": 3,
    "computer-spy": 2,
    "mechanic": 1,
    "ai": 3,
    "server": 4,
    "super-ai": 1,
    "sentry": 1,
}
SPECIALS = {
    "hoarfrost": 1,
    "thick-fog": 1,
    "downpour": 1,
    "clear-skies": 1,
    "wildfire": 1,
    "scarecrow": 2,
    "war-horn": 3,
}


def test_deck_ids_lists_the_deck_files() -> None:
    assert deck_ids() == ["humans", "robots"]


# deck_ids() runs when the tests are collected, so a new deck file is tested
# here without changing this file.
@pytest.mark.parametrize("deck_id", deck_ids())
def test_every_deck_loads(deck_id: str) -> None:
    deck = load_deck(deck_id)

    assert deck.id == deck_id


@pytest.mark.parametrize(("deck_id", "units"), [("humans", HUMANS), ("robots", ROBOTS)])
def test_mvp_decks_match_the_card_lists(deck_id: str, units: dict[str, int]) -> None:
    deck = load_deck(deck_id)

    assert Counter(card.id for card in deck.cards) == units | SPECIALS


def test_unknown_deck_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown deck elves"):
        load_deck("elves")


def test_only_deck_files_can_be_loaded() -> None:
    with pytest.raises(ValueError, match="unknown deck"):
        load_deck("../specials")


@pytest.fixture
def data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the loader at an empty temporary folder instead of the real data."""
    (tmp_path / "decks").mkdir()
    monkeypatch.setattr(data, "_DATA", tmp_path)
    return tmp_path


def test_deck_errors_name_the_file(data_folder: Path) -> None:
    (data_folder / "specials.json").write_text("[]")
    (data_folder / "decks" / "broken.json").write_text("{}")

    with pytest.raises(ValueError, match=re.escape("broken.json: missing fields")):
        load_deck("broken")


def test_specials_errors_name_the_file(data_folder: Path) -> None:
    (data_folder / "specials.json").write_text("[")
    (data_folder / "decks" / "humans.json").write_text("{}")

    with pytest.raises(ValueError, match=re.escape("specials.json: Expecting value")):
        load_deck("humans")
