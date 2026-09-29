"""Tests for decks and the limits checked when a deck is created."""

import dataclasses

import pytest

from rowen.engine.cards import Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.decks import MAX_SPECIALS, MIN_UNITS, Deck

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)


def make_deck(*, units: int = MIN_UNITS, specials: int = 0) -> Deck:
    """Build a deck with the given number of Snipers and War Horns."""
    cards = (SNIPER,) * units + (WAR_HORN,) * specials
    return Deck(id="test", name="Test", cards=cards)


def test_deck_can_be_at_its_limits() -> None:
    deck = make_deck(units=MIN_UNITS, specials=MAX_SPECIALS)

    assert deck.cards.count(SNIPER) == 22
    assert deck.cards.count(WAR_HORN) == 10


def test_deck_needs_enough_units() -> None:
    with pytest.raises(ValueError, match="at least 22 units, got 21"):
        make_deck(units=MIN_UNITS - 1)


def test_deck_limits_special_cards() -> None:
    with pytest.raises(ValueError, match="more than 10 special cards, got 11"):
        make_deck(specials=MAX_SPECIALS + 1)


def test_one_id_means_one_card() -> None:
    stronger_sniper = dataclasses.replace(SNIPER, strength=99)

    with pytest.raises(ValueError, match="two different cards use the id sniper"):
        Deck(id="test", name="Test", cards=(SNIPER,) * MIN_UNITS + (stronger_sniper,))
