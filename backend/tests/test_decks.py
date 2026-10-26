"""Tests for decks, the limits checked when a deck is created, and built decks."""

import dataclasses
from collections import Counter

import pytest

from rowen.engine.cards import Ability, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.decks import (
    MAX_COPIES,
    MAX_SPECIALS,
    MIN_UNITS,
    Deck,
    build_deck,
    choices,
    max_copies,
)

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


# A faction to build decks from: seven plain units, a Bond group with more
# copies than MAX_COPIES, a Muster group with fewer, and a Legend.
PLAIN = tuple(
    UnitCard(id=f"unit-{n}", name=f"Unit {n}", rows=(Row.MELEE,), strength=n)
    for n in range(7)
)
BOND = UnitCard(
    id="bond",
    name="Bond",
    rows=(Row.MELEE,),
    strength=1,
    ability=Ability.BOND,
    group="bonds",
)
MUSTER = UnitCard(
    id="muster",
    name="Muster",
    rows=(Row.SIEGE,),
    strength=2,
    ability=Ability.MUSTER,
    group="musters",
)
LEGEND = UnitCard(
    id="legend", name="Legend", rows=(Row.SIEGE,), strength=10, legend=True
)
FACTION = Deck(
    id="faction",
    name="Faction",
    cards=(*PLAIN * 2, *(BOND,) * 5, *(MUSTER,) * 2, LEGEND, WAR_HORN),
)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
FOG = SpecialCard(id="thick-fog", name="Thick Fog", kind=SpecialKind.THICK_FOG)
SKIES = SpecialCard(id="clear-skies", name="Clear Skies", kind=SpecialKind.CLEAR_SKIES)
SPECIALS = {card.id: card for card in (WAR_HORN, HOARFROST, FOG, SKIES)}

# 18 plain units and 4 Bonds: 22 units, as few as a deck may have.
ENOUGH = {**{unit.id: MAX_COPIES for unit in PLAIN[:6]}, "bond": 4}


def build(copies: dict[str, int]) -> Deck:
    """Build a deck from the faction above."""
    return build_deck(
        id="mine", name="Mine", faction=FACTION, specials=SPECIALS, copies=copies
    )


def test_a_card_may_have_up_to_three_copies_but_a_legend_one() -> None:
    assert max_copies(PLAIN[0], FACTION) == MAX_COPIES == 3
    assert max_copies(WAR_HORN, FACTION) == 3
    assert max_copies(LEGEND, FACTION) == 1


def test_a_group_may_have_as_many_copies_as_its_factions_deck_if_more() -> None:
    # The faction's deck has 5 Bonds, so the whole group fits.
    assert max_copies(BOND, FACTION) == 5
    # It has only 2 Musters: 3, as for any card.
    assert max_copies(MUSTER, FACTION) == 3


def test_the_choices_are_the_factions_units_once_and_every_special() -> None:
    assert choices(FACTION, SPECIALS) == (
        *PLAIN,
        BOND,
        MUSTER,
        LEGEND,
        WAR_HORN,
        HOARFROST,
        FOG,
        SKIES,
    )


def test_a_deck_holds_the_copies_chosen() -> None:
    deck = build({**ENOUGH, "legend": 1, "hoarfrost": 3, "war-horn": 2})

    assert deck.id == "mine"
    assert deck.name == "Mine"
    assert Counter(card.id for card in deck.cards) == {
        **ENOUGH,
        "legend": 1,
        "hoarfrost": 3,
        "war-horn": 2,
    }


def test_the_same_choice_in_any_order_is_the_same_deck() -> None:
    # The seed shuffles the cards in their order: a deck built again from a
    # choice kept out of order must come out the same.
    copies = {**ENOUGH, "legend": 1, "hoarfrost": 2}
    backwards = dict(reversed(copies.items()))

    assert build(backwards) == build(copies)
    assert [card.id for card in build(copies).cards] == [
        card.id
        for card in choices(FACTION, SPECIALS)
        for _ in range(copies.get(card.id, 0))
    ]


def test_a_card_of_another_faction_is_turned_down() -> None:
    with pytest.raises(ValueError, match="mine: Faction has no card sniper"):
        build({**ENOUGH, "sniper": 1})


@pytest.mark.parametrize(
    ("card", "copies", "most"),
    [("unit-0", 4, 3), ("legend", 2, 1), ("bond", 6, 5), ("muster", 4, 3)],
)
def test_too_many_copies_are_turned_down(card: str, copies: int, most: int) -> None:
    with pytest.raises(
        ValueError, match=f"mine: {card} can have 1 to {most} copies, got {copies}"
    ):
        build({**ENOUGH, card: copies})


def test_no_copies_are_turned_down() -> None:
    # A card that isn't chosen is left out, rather than chosen 0 times.
    with pytest.raises(ValueError, match="legend can have 1 to 1 copies, got 0"):
        build({**ENOUGH, "legend": 0})


def test_a_built_deck_keeps_to_the_deck_limits() -> None:
    with pytest.raises(ValueError, match="at least 22 units, got 21"):
        build({**ENOUGH, "bond": 3})
    with pytest.raises(ValueError, match="more than 10 special cards, got 12"):
        build({**ENOUGH, **{card: 3 for card in SPECIALS}})
