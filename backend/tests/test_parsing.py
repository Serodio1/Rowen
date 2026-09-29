"""Tests for turning JSON data into cards and decks, including invalid data."""

import dataclasses
import re
from typing import Any

import pytest

from rowen.engine.cards import Ability, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.parsing import parse_deck, parse_specials

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
PRESIDENT = UnitCard(
    id="president",
    name="President",
    rows=(Row.MELEE,),
    strength=10,
    ability=Ability.INSPIRE,
    legend=True,
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
SPECIALS = {"war-horn": WAR_HORN}


def deck_data() -> dict[str, Any]:
    """Return valid deck data, as json.loads would; each test changes one part.

    It is a function so that every test gets its own copy to change.
    """
    return {
        "id": "test",
        "name": "Test",
        "units": [
            {
                "id": "sniper",
                "name": "Sniper",
                "rows": ["ranged"],
                "strength": 6,
                "copies": 21,
            },
            {
                "id": "president",
                "name": "President",
                "rows": ["melee"],
                "strength": 10,
                "ability": "inspire",
                "legend": True,
                "copies": 1,
            },
        ],
        "specials": {"war-horn": 3},
    }


def test_deck_has_one_card_per_copy() -> None:
    deck = parse_deck(deck_data(), SPECIALS)

    assert deck.id == "test"
    assert deck.name == "Test"
    assert deck.cards == (SNIPER,) * 21 + (PRESIDENT,) + (WAR_HORN,) * 3


def test_unit_group_is_read() -> None:
    data = deck_data()
    data["units"][0].update(ability="bond", group="snipers")

    deck = parse_deck(data, SPECIALS)

    assert deck.cards[0] == dataclasses.replace(
        SNIPER, ability=Ability.BOND, group="snipers"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("abilty", "spy", "units[0]: unknown fields: abilty"),
        ("strength", "6", "units[0]: strength must be of type int, got '6'"),
        ("strength", -1, "units[0]: sniper: strength can't be negative"),
        ("rows", "ranged", "units[0]: rows must be of type list, got 'ranged'"),
        ("rows", ["air"], "units[0]: 'air' is not a valid Row"),
        ("ability", "flying", "units[0]: 'flying' is not a valid Ability"),
        ("group", "snipers", "units[0]: sniper: only Bond and Muster units"),
        ("legend", "yes", "units[0]: legend must be of type bool, got 'yes'"),
        ("copies", 0, "units[0]: copies must be a whole number of at least 1"),
    ],
)
def test_invalid_unit_is_rejected(field: str, value: object, message: str) -> None:
    data = deck_data()
    data["units"][0][field] = value

    # re.escape: match reads a regular expression, where [0] has a meaning.
    with pytest.raises(ValueError, match=re.escape(message)):
        parse_deck(data, SPECIALS)


def test_missing_unit_field_is_rejected() -> None:
    data = deck_data()
    del data["units"][1]["strength"]

    with pytest.raises(
        ValueError, match=re.escape("units[1]: missing fields: strength")
    ):
        parse_deck(data, SPECIALS)


def test_deck_must_be_an_object() -> None:
    with pytest.raises(ValueError, match=re.escape("expected an object, got []")):
        parse_deck([], SPECIALS)


def test_missing_deck_field_is_rejected() -> None:
    data = deck_data()
    del data["specials"]

    with pytest.raises(ValueError, match="missing fields: specials"):
        parse_deck(data, SPECIALS)


def test_unknown_special_card_is_rejected() -> None:
    data = deck_data()
    data["specials"] = {"war-hron": 1}

    with pytest.raises(ValueError, match="specials: unknown special card war-hron"):
        parse_deck(data, SPECIALS)


def test_invalid_special_copies_are_rejected() -> None:
    data = deck_data()
    data["specials"] = {"war-horn": "3"}

    with pytest.raises(
        ValueError, match=re.escape("specials.war-horn: copies must be")
    ):
        parse_deck(data, SPECIALS)


def test_deck_limits_are_checked() -> None:
    data = deck_data()
    data["units"][0]["copies"] = 20

    with pytest.raises(ValueError, match="at least 22 units, got 21"):
        parse_deck(data, SPECIALS)


def test_specials_are_indexed_by_id() -> None:
    data = [{"id": "war-horn", "name": "War Horn", "kind": "war-horn"}]

    assert parse_specials(data) == {"war-horn": WAR_HORN}


def test_specials_must_be_a_list() -> None:
    with pytest.raises(ValueError, match="expected a list of special cards"):
        parse_specials({})


def test_unknown_special_kind_is_rejected() -> None:
    data = [{"id": "lightning", "name": "Lightning", "kind": "lightning"}]

    with pytest.raises(ValueError, match=re.escape("[0]: 'lightning' is not a valid")):
        parse_specials(data)


def test_special_ids_are_unique() -> None:
    war_horn = {"id": "war-horn", "name": "War Horn", "kind": "war-horn"}

    with pytest.raises(ValueError, match="another special card uses the id war-horn"):
        parse_specials([war_horn, war_horn])
