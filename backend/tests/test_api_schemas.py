"""Tests for what the web API sends as JSON: the player view in shapes of its own."""

import json
from dataclasses import asdict, replace
from typing import Any

import pytest

from rowen.api import schemas
from rowen.data import deck_ids, load_deck
from rowen.engine import public as engine

MELEE, RANGED, SIEGE = engine.Row.MELEE, engine.Row.RANGED, engine.Row.SIEGE

SNIPER = engine.UnitCard(id="sniper", name="Sniper", rows=(RANGED,), strength=6)
SOLDIER = engine.UnitCard(
    id="soldier",
    name="Soldier",
    rows=(MELEE, RANGED),
    strength=4,
    ability=engine.Ability.AGILE,
)
THICK_FOG = engine.SpecialCard(
    id="thick-fog", name="Thick Fog", kind=engine.SpecialKind.THICK_FOG
)
WAR_HORN = engine.SpecialCard(
    id="war-horn", name="War Horn", kind=engine.SpecialKind.WAR_HORN
)

SNIPER_JSON = {
    "type": "unit",
    "id": "sniper",
    "name": "Sniper",
    "rows": ["ranged"],
    "strength": 6,
    "ability": None,
    "group": None,
    "legend": False,
}
SOLDIER_JSON = {
    "type": "unit",
    "id": "soldier",
    "name": "Soldier",
    "rows": ["melee", "ranged"],
    "strength": 4,
    "ability": "agile",
    "group": None,
    "legend": False,
}
THICK_FOG_JSON = {
    "type": "special",
    "id": "thick-fog",
    "name": "Thick Fog",
    "kind": "thick-fog",
}
WAR_HORN_JSON = {
    "type": "special",
    "id": "war-horn",
    "name": "War Horn",
    "kind": "war-horn",
}

EMPTY_ROW = engine.RowView(units=(), horn=None, scarecrows=(), weathered=False, score=0)
EMPTY_ROW_JSON: dict[str, Any] = {
    "units": [],
    "horn": None,
    "scarecrows": [],
    "weathered": False,
    "score": 0,
}

EMPTY_SIDE = engine.SideView(
    rows={MELEE: EMPTY_ROW, RANGED: EMPTY_ROW, SIEGE: EMPTY_ROW},
    weather=(),
    discard=(),
    lives=2,
    passed=False,
    redraws_left=2,
    hand_size=0,
    deck_size=0,
    total=0,
)
EMPTY_VIEW = engine.PlayerView(
    player=0,
    hand=(),
    players=(EMPTY_SIDE, EMPTY_SIDE),
    current=0,
    round=1,
    reviving=False,
    legal_actions=(),
    match_over=False,
    winner=None,
)


DECKS = tuple(load_deck(deck_id) for deck_id in deck_ids())


def test_a_view_is_sent_field_by_field() -> None:
    # Round 2: the opponent passed after playing Thick Fog. A Sniper of theirs
    # is in their discard pile, and the player's own Sniper is under the fog.
    view = engine.PlayerView(
        player=0,
        hand=(SOLDIER, THICK_FOG),
        players=(
            engine.SideView(
                rows={
                    MELEE: EMPTY_ROW,
                    RANGED: engine.RowView(
                        units=(engine.UnitView(card=SNIPER, strength=1),),
                        horn=None,
                        scarecrows=(),
                        weathered=True,
                        score=1,
                    ),
                    SIEGE: engine.RowView(
                        units=(),
                        horn=WAR_HORN,
                        scarecrows=(),
                        weathered=False,
                        score=0,
                    ),
                },
                weather=(),
                discard=(),
                lives=2,
                passed=False,
                redraws_left=0,
                hand_size=2,
                deck_size=12,
                total=1,
            ),
            engine.SideView(
                rows={
                    MELEE: EMPTY_ROW,
                    RANGED: replace(EMPTY_ROW, weathered=True),
                    SIEGE: EMPTY_ROW,
                },
                weather=(THICK_FOG,),
                discard=(SNIPER,),
                lives=1,
                passed=True,
                redraws_left=0,
                hand_size=7,
                deck_size=11,
                total=0,
            ),
        ),
        current=0,
        round=2,
        reviving=False,
        legal_actions=(
            engine.PlayUnit(card="soldier", row=MELEE),
            engine.PlayUnit(card="soldier", row=RANGED),
            engine.PlaySpecial(card="thick-fog"),
            engine.Pass(),
        ),
        match_over=False,
        winner=None,
    )

    sent = json.loads(schemas.from_view(view).model_dump_json())

    assert as_text(sent) == as_text(
        {
            "player": 0,
            "hand": [SOLDIER_JSON, THICK_FOG_JSON],
            "players": [
                {
                    "rows": {
                        "melee": EMPTY_ROW_JSON,
                        "ranged": {
                            "units": [{"card": SNIPER_JSON, "strength": 1}],
                            "horn": None,
                            "scarecrows": [],
                            "weathered": True,
                            "score": 1,
                        },
                        "siege": {
                            "units": [],
                            "horn": WAR_HORN_JSON,
                            "scarecrows": [],
                            "weathered": False,
                            "score": 0,
                        },
                    },
                    "weather": [],
                    "discard": [],
                    "lives": 2,
                    "passed": False,
                    "redraws_left": 0,
                    "hand_size": 2,
                    "deck_size": 12,
                    "total": 1,
                },
                {
                    "rows": {
                        "melee": EMPTY_ROW_JSON,
                        "ranged": {**EMPTY_ROW_JSON, "weathered": True},
                        "siege": EMPTY_ROW_JSON,
                    },
                    "weather": [THICK_FOG_JSON],
                    "discard": [SNIPER_JSON],
                    "lives": 1,
                    "passed": True,
                    "redraws_left": 0,
                    "hand_size": 7,
                    "deck_size": 11,
                    "total": 0,
                },
            ],
            "current": 0,
            "round": 2,
            "reviving": False,
            "legal_actions": [
                {"type": "play_unit", "card": "soldier", "row": "melee"},
                {"type": "play_unit", "card": "soldier", "row": "ranged"},
                {"type": "play_special", "card": "thick-fog"},
                {"type": "pass"},
            ],
            "match_over": False,
            "winner": None,
        }
    )


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (
            engine.PlayUnit(card="sniper", row=RANGED),
            {"type": "play_unit", "card": "sniper", "row": "ranged"},
        ),
        (
            engine.PlaySpecial(card="thick-fog"),
            {"type": "play_special", "card": "thick-fog"},
        ),
        (
            engine.PlayHorn(card="war-horn", row=SIEGE),
            {"type": "play_horn", "card": "war-horn", "row": "siege"},
        ),
        (
            engine.PlayScarecrow(card="scarecrow", row=RANGED, unit="sniper"),
            {
                "type": "play_scarecrow",
                "card": "scarecrow",
                "row": "ranged",
                "unit": "sniper",
            },
        ),
        (engine.Pass(), {"type": "pass"}),
        (
            engine.Revive(card="sniper", row=RANGED),
            {"type": "revive", "card": "sniper", "row": "ranged"},
        ),
        (engine.Redraw(card="sniper"), {"type": "redraw", "card": "sniper"}),
        (engine.EndRedraw(), {"type": "end_redraw"}),
    ],
)
def test_each_kind_of_action_is_sent_with_its_type(
    action: engine.Action, expected: dict[str, Any]
) -> None:
    view = replace(EMPTY_VIEW, legal_actions=(action,))

    sent = schemas.from_view(view).model_dump(mode="json")

    assert sent["legal_actions"] == [expected]


def test_a_view_after_a_medic_says_the_player_is_reviving() -> None:
    # After a Medic, the only actions are revives (rules, section 7.2).
    view = replace(
        EMPTY_VIEW,
        reviving=True,
        legal_actions=(engine.Revive(card="sniper", row=RANGED),),
    )

    sent = schemas.from_view(view).model_dump(mode="json")

    assert sent["reviving"] is True


@pytest.mark.parametrize(
    ("union", "types"),
    [
        ("Card", {"unit", "special"}),
        (
            "Action",
            {
                "play_unit",
                "play_special",
                "play_horn",
                "play_scarecrow",
                "pass",
                "revive",
                "redraw",
                "end_redraw",
            },
        ),
    ],
)
def test_the_json_schema_tells_each_kind_apart_by_its_type(
    union: str, types: set[str]
) -> None:
    # The browser's types are built from this schema (OpenAPI).
    schema = schemas.PlayerView.model_json_schema(mode="serialization")

    discriminator = schema["$defs"][union]["discriminator"]
    assert discriminator["propertyName"] == "type"
    assert set(discriminator["mapping"]) == types


def test_every_field_is_always_sent() -> None:
    # So the browser's types have no optional fields: a field that may be empty
    # is sent as null or as an empty list, never left out.
    schema = schemas.PlayerView.model_json_schema(mode="serialization")
    shapes = [schema, *schema["$defs"].values()]

    for shape in shapes:
        if shape.get("type") == "object":
            assert set(shape["required"]) == set(shape["properties"]), shape["title"]


@pytest.mark.parametrize("seed", range(4))
def test_every_view_of_a_match_is_sent_as_it_is(seed: int) -> None:
    # Each player plays the first legal action in their own view, to the end.
    state = engine.start_match((DECKS[0], DECKS[1]), seed=seed)
    views = [engine.player_view(state, player) for player in (0, 1)]
    while not views[-1].match_over:
        mover = engine.player_view(state, views[-1].current)
        state, _ = engine.apply(state, mover.legal_actions[0])
        views += [engine.player_view(state, player) for player in (0, 1)]

    for view in views:
        sent = schemas.from_view(view)
        text = sent.model_dump_json()
        # Field by field, the JSON is the view, with a "type" on each card and
        # action.
        assert as_text(without_types(json.loads(text))) == as_text(asdict(view))
        # And what the JSON reads back as is what was sent.
        assert schemas.PlayerView.model_validate_json(text) == sent


def as_text(value: Any) -> str:
    """Return a value as JSON text, to compare it with JSON the API sent.

    Comparing text, not Python values, tells ``false`` from ``0``: in Python,
    ``False == 0``.
    """
    return json.dumps(value, sort_keys=True, indent=2)


def without_types(value: Any) -> Any:
    """Return JSON without the "type" of each card and action."""
    if isinstance(value, dict):
        return {
            key: without_types(item) for key, item in value.items() if key != "type"
        }
    if isinstance(value, list):
        return [without_types(item) for item in value]
    return value
