"""Tests for what the web API sends as JSON: the player view and the events."""

import json
from dataclasses import asdict, replace
from typing import Any

import pytest
from fastapi.routing import APIRoute
from pydantic import TypeAdapter, ValidationError

from rowen.api import schemas
from rowen.api.app import app
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
    "weather_row": "ranged",
}
WAR_HORN_JSON = {
    "type": "special",
    "id": "war-horn",
    "name": "War Horn",
    "kind": "war-horn",
    "weather_row": None,
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

# The events of an action, as a response holds them.
EVENTS = TypeAdapter(tuple[schemas.EventView, ...])

DECKS = tuple(load_deck(deck_id) for deck_id in deck_ids())

# Each kind of action, and the JSON of it: in a view, and as the player sends
# it back.
ACTIONS: list[tuple[engine.Action, dict[str, Any]]] = [
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
    # A second revive, so a row fixed to either one is caught: the player never
    # revives in the matches of test_api_app.
    (
        engine.Revive(card="soldier", row=MELEE),
        {"type": "revive", "card": "soldier", "row": "melee"},
    ),
    (engine.Redraw(card="sniper"), {"type": "redraw", "card": "sniper"}),
    (engine.EndRedraw(), {"type": "end_redraw"}),
]


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


# The row each kind of special card hits with its weather, as the API sends
# it (rules, section 8): written out, not taken from the engine.
WEATHER_ROWS_JSON = {
    engine.SpecialKind.HOARFROST: "melee",
    engine.SpecialKind.THICK_FOG: "ranged",
    engine.SpecialKind.DOWNPOUR: "siege",
    engine.SpecialKind.CLEAR_SKIES: None,
    engine.SpecialKind.WAR_HORN: None,
    engine.SpecialKind.WILDFIRE: None,
    engine.SpecialKind.SCARECROW: None,
}


@pytest.mark.parametrize(("kind", "weather_row"), WEATHER_ROWS_JSON.items())
def test_a_special_card_says_which_row_its_weather_hits(
    kind: engine.SpecialKind, weather_row: str | None
) -> None:
    card = engine.SpecialCard(id="card", name="Card", kind=kind)
    view = replace(EMPTY_VIEW, hand=(card,))

    sent = json.loads(schemas.from_view(view).model_dump_json())

    assert sent["hand"][0]["weather_row"] == weather_row


def test_every_kind_of_special_card_is_tested_for_its_weather_row() -> None:
    assert set(WEATHER_ROWS_JSON) == set(engine.SpecialKind)


@pytest.mark.parametrize(("action", "expected"), ACTIONS)
def test_each_kind_of_action_is_sent_with_its_type(
    action: engine.Action, expected: dict[str, Any]
) -> None:
    view = replace(EMPTY_VIEW, legal_actions=(action,))

    sent = schemas.from_view(view).model_dump(mode="json")

    assert sent["legal_actions"] == [expected]


@pytest.mark.parametrize(("expected", "sent"), ACTIONS)
def test_each_kind_of_action_sent_back_is_the_engines_own(
    expected: engine.Action, sent: dict[str, Any]
) -> None:
    # The player sends back an action as the view held it.
    action = TypeAdapter(schemas.Action).validate_json(json.dumps(sent))

    assert schemas.to_action(action) == expected


@pytest.mark.parametrize(
    ("shape", "sent"),
    [
        (schemas.NewMatch, {"deck": "humans", "seed": 1}),
        (schemas.Action, {"type": "pass", "card": "sniper"}),
        (schemas.Action, {"type": "redraw", "card": "sniper", "row": "melee"}),
    ],
)
def test_a_request_with_a_field_the_api_doesnt_know_is_turned_down(
    shape: Any, sent: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TypeAdapter(shape).validate_python(sent)


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
    ("sent", "union", "types"),
    [
        (schemas.PlayerView, "Card", {"unit", "special"}),
        (
            schemas.PlayerView,
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
        (
            tuple[schemas.EventView, ...],
            "EventView",
            {
                "unit_played",
                "unit_revived",
                "unit_mustered",
                "cards_drawn",
                "weather_played",
                "weather_cleared",
                "horn_played",
                "scarecrow_played",
                "wildfire_played",
                "unit_destroyed",
                "player_passed",
                "round_ended",
                "match_ended",
                "card_redrawn",
                "redraw_ended",
                "opponent_drew",
                "opponent_redrew",
            },
        ),
    ],
)
def test_the_json_schema_tells_each_kind_apart_by_its_type(
    sent: Any, union: str, types: set[str]
) -> None:
    # The browser's types are built from this schema (OpenAPI).
    schema = TypeAdapter(sent).json_schema(mode="serialization")

    discriminator = schema["$defs"][union]["discriminator"]
    assert discriminator["propertyName"] == "type"
    assert set(discriminator["mapping"]) == types


# Everything the API sends: the answer of each endpoint, found in the app so
# that a new endpoint is checked too, and the error of a request turned down.
SENT = {
    route.name: route.response_model
    for route in app.routes
    if isinstance(route, APIRoute)
} | {"error": schemas.Error}


@pytest.mark.parametrize("sent", SENT.values(), ids=SENT.keys())
def test_every_field_is_always_sent(sent: Any) -> None:
    # So the browser's types have no optional fields: a field that may be empty
    # is sent as null or as an empty list, never left out.
    schema = TypeAdapter(sent).json_schema(mode="serialization")
    shapes = [schema, *schema.get("$defs", {}).values()]

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
        # action, and a "weather_row" on each special card.
        assert as_text(without_added(json.loads(text))) == as_text(asdict(view))
        # And what the JSON reads back as is what was sent.
        assert schemas.PlayerView.model_validate_json(text) == sent


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            engine.UnitPlayed(player=0, card="spy", row=MELEE, side=1),
            {
                "type": "unit_played",
                "player": 0,
                "card": "spy",
                "row": "melee",
                "side": 1,
            },
        ),
        (
            engine.UnitRevived(player=0, card="spy", row=MELEE, side=1),
            {
                "type": "unit_revived",
                "player": 0,
                "card": "spy",
                "row": "melee",
                "side": 1,
            },
        ),
        # No full match below revives a unit, so a second one: not a Spy.
        (
            engine.UnitRevived(player=1, card="sniper", row=RANGED, side=1),
            {
                "type": "unit_revived",
                "player": 1,
                "card": "sniper",
                "row": "ranged",
                "side": 1,
            },
        ),
        (
            engine.UnitMustered(player=1, card="soldier", row=MELEE, from_hand=True),
            {
                "type": "unit_mustered",
                "player": 1,
                "card": "soldier",
                "row": "melee",
                "from_hand": True,
            },
        ),
        (
            engine.CardsDrawn(player=0, cards=("sniper", "soldier")),
            {"type": "cards_drawn", "player": 0, "cards": ["sniper", "soldier"]},
        ),
        (
            engine.WeatherPlayed(player=1, card="thick-fog", row=RANGED),
            {
                "type": "weather_played",
                "player": 1,
                "card": "thick-fog",
                "row": "ranged",
            },
        ),
        (
            engine.WeatherCleared(player=0, card="clear-skies"),
            {"type": "weather_cleared", "player": 0, "card": "clear-skies"},
        ),
        (
            engine.HornPlayed(player=0, card="war-horn", row=SIEGE),
            {"type": "horn_played", "player": 0, "card": "war-horn", "row": "siege"},
        ),
        (
            engine.ScarecrowPlayed(
                player=0, card="scarecrow", row=RANGED, unit="sniper"
            ),
            {
                "type": "scarecrow_played",
                "player": 0,
                "card": "scarecrow",
                "row": "ranged",
                "unit": "sniper",
            },
        ),
        (
            engine.WildfirePlayed(player=1, card="wildfire"),
            {"type": "wildfire_played", "player": 1, "card": "wildfire"},
        ),
        (
            engine.UnitDestroyed(side=0, row=RANGED, card="sniper"),
            {"type": "unit_destroyed", "side": 0, "row": "ranged", "card": "sniper"},
        ),
        (engine.PlayerPassed(player=1), {"type": "player_passed", "player": 1}),
        (
            engine.RoundEnded(scores=(12, 9), winner=0),
            {"type": "round_ended", "scores": [12, 9], "winner": 0},
        ),
        (engine.MatchEnded(winner=None), {"type": "match_ended", "winner": None}),
        (
            engine.CardRedrawn(player=0, card="sniper", drawn="soldier"),
            {
                "type": "card_redrawn",
                "player": 0,
                "card": "sniper",
                "drawn": "soldier",
            },
        ),
        (engine.RedrawEnded(player=1), {"type": "redraw_ended", "player": 1}),
        # The opponent's cards are hidden: only how many they drew. A Spy draws
        # one card when only one is left in the deck.
        (
            engine.CardsDrawn(player=1, cards=("sniper",)),
            {"type": "opponent_drew", "player": 1, "count": 1},
        ),
        (
            engine.CardRedrawn(player=1, card="sniper", drawn="soldier"),
            {"type": "opponent_redrew", "player": 1},
        ),
    ],
)
def test_each_kind_of_event_is_sent_with_its_type(
    event: engine.Event, expected: dict[str, Any]
) -> None:
    # As apply returns it, and as player 0 sees it.
    sent = EVENTS.dump_json(schemas.from_events((event,), player=0))

    assert as_text(json.loads(sent)) == as_text([expected])


@pytest.mark.parametrize("seed", range(4))
def test_every_event_of_a_match_is_sent_as_the_player_sees_it(seed: int) -> None:
    # Each player plays the first legal action in their own view, to the end.
    state = engine.start_match((DECKS[0], DECKS[1]), seed=seed)
    view = engine.player_view(state, 0)
    while not view.match_over:
        mover = engine.player_view(state, view.current)
        state, events = engine.apply(state, mover.legal_actions[0])
        view = engine.player_view(state, 0)

        for player in (0, 1):
            sent = schemas.from_events(events, player)
            text = EVENTS.dump_json(sent)
            # Field by field, the JSON is each event as player_events lets the
            # player see it, with a "type".
            seen = [asdict(event) for event in engine.player_events(events, player)]
            assert as_text(without_added(json.loads(text))) == as_text(seen)
            # And what the JSON reads back as is what was sent.
            assert EVENTS.validate_json(text) == sent


def as_text(value: Any) -> str:
    """Return a value as JSON text, to compare it with JSON the API sent.

    Comparing text, not Python values, tells ``false`` from ``0``: in Python,
    ``False == 0``.
    """
    return json.dumps(value, sort_keys=True, indent=2)


def without_added(value: Any) -> Any:
    """Return JSON without what the API adds to the view.

    That is the "type" of each card, action and event, and the "weather_row" of
    each special card.
    """
    if isinstance(value, dict):
        return {
            key: without_added(item)
            for key, item in value.items()
            if key not in {"type", "weather_row"}
        }
    if isinstance(value, list):
        return [without_added(item) for item in value]
    return value
