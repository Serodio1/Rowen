"""Tests for unit strength, row scores and player totals."""

import dataclasses

from rowen.engine.cards import Ability, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.rng import Rng
from rowen.engine.scoring import (
    player_total,
    row_score,
    unit_strength,
    weathered_rows,
)
from rowen.engine.state import GameState, PlayerState, RowState

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
PRIME_MINISTER = UnitCard(
    id="prime-minister",
    name="Prime Minister",
    rows=(Row.RANGED,),
    strength=7,
    legend=True,
)
PRESIDENT = UnitCard(
    id="president",
    name="President",
    rows=(Row.MELEE,),
    strength=10,
    ability=Ability.INSPIRE,
    legend=True,
)
# Test cards, with the strength of the example in the rules, section 6.
GUARD = UnitCard(
    id="guard",
    name="Guard",
    rows=(Row.MELEE,),
    strength=4,
    ability=Ability.BOND,
    group="guards",
)
CAPTAIN = UnitCard(
    id="captain",
    name="Captain",
    rows=(Row.MELEE,),
    strength=2,
    ability=Ability.INSPIRE,
)

WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
THICK_FOG = SpecialCard(id="thick-fog", name="Thick Fog", kind=SpecialKind.THICK_FOG)

EMPTY_PLAYER = PlayerState(deck=(), hand=())


def strengths(row: RowState, *, weathered: bool = False) -> list[int]:
    """Return the strength of every unit in the row, in order."""
    return [unit_strength(unit, row, weathered=weathered) for unit in row.units]


def make_state(first: PlayerState, second: PlayerState = EMPTY_PLAYER) -> GameState:
    """Build a match with these two players."""
    return GameState(
        players=(first, second), current=0, round_starter=0, rng=Rng(seed=7)
    )


def test_unit_keeps_its_base_strength() -> None:
    assert strengths(RowState(units=(SNIPER,))) == [6]


def test_weather_sets_strength_to_one() -> None:
    assert strengths(RowState(units=(SNIPER,)), weathered=True) == [1]


def test_bond_multiplies_by_the_units_in_its_group() -> None:
    assert strengths(RowState(units=(GUARD,))) == [4]
    assert strengths(RowState(units=(GUARD, GUARD, GUARD))) == [12, 12, 12]


def test_bond_only_counts_bond_units_of_the_same_group() -> None:
    other_group = dataclasses.replace(GUARD, id="knight", group="knights")
    muster = dataclasses.replace(GUARD, id="recruit", ability=Ability.MUSTER)
    row = RowState(units=(GUARD, GUARD, other_group, muster))

    assert strengths(row) == [8, 8, 4, 4]


def test_inspire_gives_one_to_every_other_unit() -> None:
    row = RowState(units=(SNIPER, SNIPER, CAPTAIN))

    assert strengths(row) == [7, 7, 2]


def test_inspire_units_boost_each_other() -> None:
    assert strengths(RowState(units=(CAPTAIN, CAPTAIN))) == [3, 3]


def test_war_horn_doubles_strength() -> None:
    assert strengths(RowState(units=(SNIPER,), horn=WAR_HORN)) == [12]


def test_legend_keeps_its_base_strength() -> None:
    row = RowState(units=(PRIME_MINISTER, CAPTAIN), horn=WAR_HORN)

    assert strengths(row, weathered=True) == [7, 2]


def test_legend_with_inspire_boosts_others_but_not_itself() -> None:
    row = RowState(units=(PRESIDENT, SNIPER), horn=WAR_HORN)

    assert strengths(row) == [10, 14]


def test_example_from_the_rules() -> None:
    # Section 6: 1 (weather) -> 3 (x3 Bond) -> 3 (no Inspire) -> 6 (x2 horn).
    row = RowState(units=(GUARD, GUARD, GUARD), horn=WAR_HORN)

    assert strengths(row, weathered=True) == [6, 6, 6]
    assert row_score(row, weathered=True) == 18


def test_all_steps_in_order() -> None:
    # Guard: 1 (weather) -> 2 (x2 Bond) -> 3 (+1 Inspire) -> 6 (x2 horn).
    # Captain: 1 (weather) -> 1 (no other Inspire) -> 2 (x2 horn).
    row = RowState(units=(GUARD, GUARD, CAPTAIN), horn=WAR_HORN)

    assert strengths(row, weathered=True) == [6, 6, 2]
    assert row_score(row, weathered=True) == 14


def test_empty_row_scores_zero() -> None:
    assert row_score(RowState(), weathered=False) == 0


def test_no_weather_at_the_start() -> None:
    assert weathered_rows(make_state(EMPTY_PLAYER)) == frozenset()


def test_weather_from_both_players_counts() -> None:
    first = dataclasses.replace(EMPTY_PLAYER, weather=(HOARFROST,))
    second = dataclasses.replace(EMPTY_PLAYER, weather=(THICK_FOG,))

    assert weathered_rows(make_state(first, second)) == {Row.MELEE, Row.RANGED}


def test_same_weather_twice_counts_once() -> None:
    player = dataclasses.replace(EMPTY_PLAYER, weather=(HOARFROST,))

    assert weathered_rows(make_state(player, player)) == {Row.MELEE}


def test_total_adds_up_the_three_rows() -> None:
    rows = {
        Row.MELEE: RowState(units=(GUARD,)),
        Row.RANGED: RowState(units=(SNIPER, SNIPER)),
        Row.SIEGE: RowState(),
    }
    player = dataclasses.replace(EMPTY_PLAYER, rows=rows)

    assert player_total(make_state(player), 0) == 4 + 12
    assert player_total(make_state(player), 1) == 0


def test_opponents_weather_also_hits_the_player() -> None:
    rows = {**EMPTY_PLAYER.rows, Row.RANGED: RowState(units=(SNIPER, SNIPER))}
    player = dataclasses.replace(EMPTY_PLAYER, rows=rows)
    opponent = dataclasses.replace(EMPTY_PLAYER, weather=(THICK_FOG,))

    assert player_total(make_state(player, opponent), 0) == 2
