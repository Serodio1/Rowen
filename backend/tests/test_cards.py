"""Tests for the card definitions and the rules checked when a card is created."""

import dataclasses

import pytest

from rowen.engine.cards import (
    WEATHER_ROWS,
    Ability,
    Row,
    SpecialCard,
    SpecialKind,
    UnitCard,
)

# Valid cards from docs/cards.md. Each test changes one field with
# dataclasses.replace, which builds a new card and runs its checks again.
SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
PRESIDENT = UnitCard(
    id="president",
    name="President",
    rows=(Row.MELEE,),
    strength=10,
    ability=Ability.INSPIRE,
    legend=True,
)


def test_unit_card_keeps_its_data() -> None:
    assert SNIPER.name == "Sniper"
    assert SNIPER.rows == (Row.RANGED,)
    assert SNIPER.strength == 6
    assert SNIPER.ability is None
    assert SNIPER.group is None
    assert not SNIPER.legend


def test_cards_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        SNIPER.strength = 99  # type: ignore[misc]


def test_enums_are_read_from_text() -> None:
    assert Row("siege") is Row.SIEGE
    assert Ability("muster") is Ability.MUSTER
    assert SpecialKind("thick-fog") is SpecialKind.THICK_FOG


def test_unknown_text_is_not_a_valid_enum() -> None:
    with pytest.raises(ValueError, match="not a valid Row"):
        Row("sky")


def test_negative_strength_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        dataclasses.replace(SNIPER, strength=-1)


def test_agile_unit_goes_in_melee_or_ranged() -> None:
    soldier = UnitCard(
        id="soldier",
        name="Soldier",
        rows=(Row.MELEE, Row.RANGED),
        strength=4,
        ability=Ability.AGILE,
    )
    assert soldier.rows == (Row.MELEE, Row.RANGED)


def test_agile_unit_with_other_rows_is_rejected() -> None:
    with pytest.raises(ValueError, match="Agile"):
        dataclasses.replace(SNIPER, ability=Ability.AGILE)


@pytest.mark.parametrize("rows", [(), (Row.MELEE, Row.SIEGE)])
def test_unit_that_is_not_agile_needs_exactly_one_row(rows: tuple[Row, ...]) -> None:
    with pytest.raises(ValueError, match="exactly one row"):
        dataclasses.replace(SNIPER, rows=rows)


@pytest.mark.parametrize("ability", [Ability.BOND, Ability.MUSTER])
def test_bond_or_muster_unit_needs_a_group(ability: Ability) -> None:
    with pytest.raises(ValueError, match="needs a group"):
        dataclasses.replace(SNIPER, ability=ability)


@pytest.mark.parametrize("ability", [None, Ability.SPY, Ability.INSPIRE])
def test_other_units_have_no_group(ability: Ability | None) -> None:
    with pytest.raises(ValueError, match="only Bond and Muster"):
        dataclasses.replace(SNIPER, ability=ability, group="snipers")


@pytest.mark.parametrize("ability", [None, Ability.SPY, Ability.MEDIC, Ability.INSPIRE])
def test_legend_can_have_spy_medic_or_inspire(ability: Ability | None) -> None:
    legend = dataclasses.replace(PRESIDENT, ability=ability)
    assert legend.ability is ability


@pytest.mark.parametrize("ability", [Ability.BOND, Ability.MUSTER])
def test_legend_with_another_ability_is_rejected(ability: Ability) -> None:
    with pytest.raises(ValueError, match="Legend"):
        dataclasses.replace(PRESIDENT, ability=ability, group="leaders")


def test_special_card_keeps_its_data() -> None:
    card = SpecialCard(id="thick-fog", name="Thick Fog", kind=SpecialKind.THICK_FOG)
    assert card.name == "Thick Fog"
    assert card.kind is SpecialKind.THICK_FOG


def test_each_row_has_one_weather_card() -> None:
    assert sorted(WEATHER_ROWS.values()) == sorted(Row)
