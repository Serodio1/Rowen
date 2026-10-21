"""What each card does, in words: ``rowen.engine.texts``."""

import pytest

from rowen.engine.cards import Ability, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.texts import ABILITY_TEXTS, LEGEND_TEXT, SPECIAL_TEXTS, describe


def test_every_ability_and_special_card_has_its_text() -> None:
    assert set(ABILITY_TEXTS) == set(Ability)
    assert set(SPECIAL_TEXTS) == set(SpecialKind)


def test_a_unit_with_no_ability_has_no_text() -> None:
    unit = UnitCard(id="u", name="U", rows=(Row.MELEE,), strength=1)

    assert describe(unit) == ()


def test_a_legend_says_it_first_then_its_ability() -> None:
    unit = UnitCard(
        id="u",
        name="U",
        rows=(Row.MELEE,),
        strength=8,
        ability=Ability.SPY,
        legend=True,
    )

    assert describe(unit) == (LEGEND_TEXT, ABILITY_TEXTS[Ability.SPY])


@pytest.mark.parametrize("kind", list(SpecialKind))
def test_a_special_card_says_what_it_does(kind: SpecialKind) -> None:
    card = SpecialCard(id="s", name="S", kind=kind)

    assert describe(card) == (SPECIAL_TEXTS[kind],)


def test_the_weather_cards_name_their_own_row() -> None:
    for kind, row in [
        (SpecialKind.HOARFROST, "melee"),
        (SpecialKind.THICK_FOG, "ranged"),
        (SpecialKind.DOWNPOUR, "siege"),
    ]:
        assert f"{row} rows" in SPECIAL_TEXTS[kind]
