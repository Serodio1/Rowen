"""Tests for the web API's endpoints, through FastAPI's test client.

The test client sends the app the requests a browser would send and gets the
same responses, without running a server.
"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.ai.baseline import choose_action
from rowen.api import schemas
from rowen.api.app import AI, HUMAN, _ai_plays, app, get_store, new_seed
from rowen.api.store import MatchStore
from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    Action,
    Event,
    GameState,
    PlayerView,
    apply,
    player_view,
    start_match,
)

# Seeds of 20 digits, which no response can hold by chance. With the humans
# against the robots, the AI wins the coin flip with the first one, and the
# player with the second one.
AI_STARTS = 12_345_678_901_234_567_890
PLAYER_STARTS = 12_345_678_901_234_567_891

# With this seed, if the player always plays their first legal action, the AI
# plays a Medic in round 1 and then has to choose a unit to revive.
AI_REVIVES = 26

# With this seed, if the player with the humans always plays their first legal
# action, the AI swaps cards after the player's redraw, and later plays a Spy,
# which draws cards.
AI_DRAWS_AND_REDRAWS = 14

DECKS = {deck_id: load_deck(deck_id) for deck_id in deck_ids()}


@pytest.fixture
def store() -> MatchStore:
    """Return an empty store, for the app to keep the matches of one test."""
    return MatchStore()


@pytest.fixture
def client(store: MatchStore) -> Iterator[TestClient]:
    """Return a test client for the app, with the store of this test."""
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def start(
    client: TestClient, deck: str = "humans", seed: int = AI_STARTS
) -> httpx2.Response:
    """Start a match with the player's deck and a seed, and return the response."""
    app.dependency_overrides[new_seed] = lambda: seed
    return client.post("/matches", json={"deck": deck})


def play(client: TestClient, response: httpx2.Response, action: Any) -> httpx2.Response:
    """Send an action for the match in a response, and return the new response."""
    return client.post(f"/matches/{response.json()['id']}/actions", json=action)


def first_action(response: httpx2.Response) -> Any:
    """Return the first legal action in the view of a response, as JSON."""
    return response.json()["view"]["legal_actions"][0]


def ai_answers(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Let the baseline AI play from its own view, as the server does.

    Return the match once it is the player's turn or it is over, and the events
    of the AI's moves.
    """
    events: tuple[Event, ...] = ()
    while (view := player_view(state, AI)).current == AI and not view.match_over:
        state, new_events = apply(state, choose_action(view))
        events += new_events
    return state, events


def state_of(store: MatchStore, response: httpx2.Response) -> GameState:
    """Return the state the store keeps for the match in a response."""
    state = store.get(UUID(response.json()["id"]))
    assert state is not None
    return state


def test_a_new_match_gets_an_address_of_its_own(client: TestClient) -> None:
    response = start(client)

    assert response.status_code == 201
    match_id = UUID(response.json()["id"])
    # Version 4 is the kind of UUID made of random bits.
    assert match_id.version == 4
    assert response.headers["Location"] == f"/matches/{match_id}"


def test_the_player_gets_their_view_and_nothing_more(
    client: TestClient, store: MatchStore
) -> None:
    response = start(client)

    state = state_of(store, response)
    sent = schemas.Match(
        id=UUID(response.json()["id"]),
        view=schemas.from_view(player_view(state, HUMAN)),
    )
    # The same JSON, as text: in Python, False == 0.
    assert response.text == sent.model_dump_json()


@pytest.mark.parametrize("deck", ["humans", "robots"])
def test_the_ai_plays_the_other_deck(
    client: TestClient, store: MatchStore, deck: str
) -> None:
    (other,) = (deck_id for deck_id in DECKS if deck_id != deck)

    state = state_of(store, start(client, deck))

    for player, deck_id in ((HUMAN, deck), (AI, other)):
        hand = {card.id for card in player_view(state, player).hand}
        assert hand <= {card.id for card in DECKS[deck_id].cards}


@pytest.mark.parametrize("seed", [AI_STARTS, PLAYER_STARTS])
@pytest.mark.parametrize("request_", ["start", "get", "play"])
def test_the_seed_is_never_sent(client: TestClient, seed: int, request_: str) -> None:
    response = start(client, seed=seed)
    if request_ == "get":
        response = client.get(response.headers["Location"])
    if request_ == "play":
        response = play(client, response, first_action(response))

    sent = response.text + str(response.headers)
    assert str(seed) not in sent
    assert f"{seed:x}" not in sent


def test_the_ai_plays_first_when_it_wins_the_coin_flip(
    client: TestClient, store: MatchStore
) -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_STARTS)
    assert player_view(state, HUMAN).current == AI
    # The moves the baseline AI chooses from its own view, until it is the
    # player's turn.
    while (view := player_view(state, AI)).current == AI:
        state, _ = apply(state, choose_action(view))

    response = start(client, seed=AI_STARTS)

    assert state_of(store, response) == state
    # The AI has done its redraw, and now it's the player's turn.
    assert response.json()["view"]["players"][AI]["redraws_left"] == 0
    assert response.json()["view"]["current"] == HUMAN


def test_the_ai_waits_when_the_player_wins_the_coin_flip(
    client: TestClient, store: MatchStore
) -> None:
    decks = (DECKS["humans"], DECKS["robots"])

    response = start(client, seed=PLAYER_STARTS)

    assert state_of(store, response) == start_match(decks, seed=PLAYER_STARTS)


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("deck", ["humans", "robots"])
def test_a_new_match_is_always_the_players_turn(
    client: TestClient, deck: str, seed: int
) -> None:
    view = start(client, deck, seed).json()["view"]

    assert view["current"] == HUMAN
    assert not view["match_over"]
    assert view["legal_actions"]


def test_a_match_can_be_seen_again(client: TestClient) -> None:
    started = start(client)

    response = client.get(started.headers["Location"])

    assert response.status_code == 200
    assert response.text == started.text


def test_each_match_has_an_id_of_its_own(client: TestClient) -> None:
    first = start(client, seed=AI_STARTS)
    second = start(client, seed=AI_STARTS)

    # The same seed gives the same match, but the id doesn't come from the seed.
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["view"] == second.json()["view"]
    for started in (first, second):
        assert client.get(started.headers["Location"]).text == started.text


@pytest.mark.parametrize("deck", ["elves", "", "HUMANS", "../specials", "decks/humans"])
def test_an_unknown_deck_is_turned_down(client: TestClient, deck: str) -> None:
    response = start(client, deck)

    assert response.status_code == 422
    assert response.json() == {
        "code": "unknown_deck",
        "message": "There is no such deck. The decks are: humans, robots.",
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"deck": None},
        {"deck": 1},
        {"deck": ["humans"]},
        ["humans"],
        "humans",
        # A field the API doesn't know, such as the seed, is turned down too.
        {"deck": "humans", "seed": 1},
    ],
)
def test_a_request_without_a_deck_is_turned_down(client: TestClient, body: Any) -> None:
    response = client.post("/matches", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


# Text that isn't UTF-8 can't even be read: FastAPI turns it down with a 400.
@pytest.mark.parametrize(
    ("body", "status"), [(b"deck=humans", 422), (b'{"deck": "\xff"}', 400)]
)
def test_a_request_that_is_not_json_is_turned_down(
    client: TestClient, body: bytes, status: int
) -> None:
    response = client.post(
        "/matches", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == status
    assert response.json()["code"] == "invalid_request"


def test_there_is_no_match_with_an_unknown_id(client: TestClient) -> None:
    start(client)

    response = client.get(f"/matches/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {
        "code": "match_not_found",
        "message": "There is no match with this id.",
    }


@pytest.mark.parametrize("match_id", ["1", "not-an-id", "humans"])
def test_an_id_that_is_not_a_uuid_is_turned_down(
    client: TestClient, match_id: str
) -> None:
    response = client.get(f"/matches/{match_id}")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_seeds_are_big_and_random() -> None:
    seeds = {new_seed() for _ in range(100)}

    assert len(seeds) == 100
    assert all(0 <= seed < 2**64 for seed in seeds)
    # A seed of 64 random bits is below 2**63 half the time, so all 100 of
    # them are below it once in 2**100: only if they have fewer bits.
    assert max(seeds) >= 2**63


def test_the_app_keeps_its_matches_in_a_store_of_its_own() -> None:
    # No overrides: the app's own store, and seeds chosen at random.
    client = TestClient(app)
    started = client.post("/matches", json={"deck": "humans"})
    client.post("/matches", json={"deck": "robots"})

    response = client.get(started.headers["Location"])

    assert response.text == started.text


def test_the_ai_doesnt_play_once_the_match_is_over() -> None:
    # Each player plays the first legal action in their own view, to the end.
    # With this seed, the match ends with the AI as the current player.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=0)
    view = player_view(state, HUMAN)
    while not view.match_over:
        state, _ = apply(state, player_view(state, view.current).legal_actions[0])
        view = player_view(state, HUMAN)
    assert view.current == AI

    assert _ai_plays(state) == (state, ())
    assert _ai_plays(state)[0] is state


def test_the_ai_finishes_its_turn_after_a_medic() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_REVIVES)
    while not (view := player_view(state, AI)).reviving:
        if view.current == AI:
            action = choose_action(view)
        else:
            action = player_view(state, HUMAN).legal_actions[0]
        state, _ = apply(state, action)
    assert view.current == AI

    # The AI chooses a unit to revive, and only then does its turn end.
    view = player_view(_ai_plays(state)[0], HUMAN)

    assert view.current == HUMAN
    assert not view.reviving


def test_every_endpoint_sends_only_the_apis_own_models() -> None:
    # FastAPI sends what an endpoint returns through its response model, which
    # is its return type. An endpoint returning "GameState", "Any" or a dict,
    # or with no return type, could send the seed.
    docs = {app.openapi_url, app.docs_url, app.redoc_url}
    docs.add(app.swagger_ui_oauth2_redirect_url)
    routes = [route for route in app.routes if getattr(route, "path", "") not in docs]

    assert routes
    for route in routes:
        assert isinstance(route, APIRoute), route
        assert isinstance(route.response_model, type), route.path
        assert issubclass(route.response_model, schemas.Schema), route.path


def test_the_openapi_schema_lists_the_endpoints(client: TestClient) -> None:
    # The browser's types are built from this schema.
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/matches"]) == {"post"}
    assert set(paths["/matches/{match_id}"]) == {"get"}
    assert set(paths["/matches/{match_id}/actions"]) == {"post"}


@pytest.mark.parametrize(
    ("path", "method", "errors"),
    [
        ("/matches", "post", {"422"}),
        ("/matches/{match_id}", "get", {"404", "422"}),
        ("/matches/{match_id}/actions", "post", {"404", "409", "422"}),
    ],
)
def test_the_openapi_schema_says_how_each_endpoint_turns_requests_down(
    client: TestClient, path: str, method: str, errors: set[str]
) -> None:
    responses = client.get("/openapi.json").json()["paths"][path][method]["responses"]

    error = {"$ref": "#/components/schemas/Error"}
    assert {
        status for status, response in responses.items() if status.startswith("4")
    } == errors
    for status in errors:
        assert responses[status]["content"]["application/json"]["schema"] == error


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("deck", ["humans", "robots"])
def test_a_full_match_can_be_played_through_the_api(
    client: TestClient, deck: str, seed: int
) -> None:
    # The player always plays the first legal action in their view.
    response = start(client, deck, seed)
    while not response.json()["view"]["match_over"]:
        response = play(client, response, first_action(response))

        assert response.status_code == 200
        view = response.json()["view"]
        # The AI has played its moves: it is the player's turn, or it's over.
        assert view["current"] == HUMAN or view["match_over"]
        assert response.json()["events"]
        # And the match is kept as it was sent.
        match = client.get(f"/matches/{response.json()['id']}").json()
        assert match["view"] == view

    # Once the match is over, there is nothing left to play.
    response = play(client, response, {"type": "pass"})
    assert response.status_code == 409
    assert response.json()["code"] == "illegal_action"


def test_the_events_are_the_players_action_and_then_the_ais_answer(
    client: TestClient,
) -> None:
    # The same match, played with the engine and the AI directly.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_DRAWS_AND_REDRAWS)
    state, _ = ai_answers(state)
    response = start(client, seed=AI_DRAWS_AND_REDRAWS)

    while not response.json()["view"]["match_over"]:
        action = first_action(response)
        state, events = apply(state, player_view(state, HUMAN).legal_actions[0])
        state, answer = ai_answers(state)

        response = play(client, response, action)

        sent = schemas.Played(
            id=UUID(response.json()["id"]),
            view=schemas.from_view(player_view(state, HUMAN)),
            events=schemas.from_events(events + answer, HUMAN),
        )
        assert response.text == sent.model_dump_json()


def test_the_player_never_gets_the_cards_the_ai_drew_or_swapped(
    client: TestClient,
) -> None:
    events = []
    response = start(client, seed=AI_DRAWS_AND_REDRAWS)
    while not response.json()["view"]["match_over"]:
        response = play(client, response, first_action(response))
        events += response.json()["events"]

    the_ais = {event["type"] for event in events if event.get("player") == AI}
    assert {"opponent_drew", "opponent_redrew"} <= the_ais
    assert not {"cards_drawn", "card_redrawn"} & the_ais


@settings(max_examples=20, deadline=None)
@given(
    deck=st.sampled_from(["humans", "robots"]),
    seed=st.integers(0, 2**64 - 1),
    choices=st.data(),
)
def test_any_legal_action_can_be_played_through_the_api(
    deck: str, seed: int, choices: st.DataObject
) -> None:
    # A store and a client of its own for each match Hypothesis tries.
    store = MatchStore()
    app.dependency_overrides[get_store] = lambda: store
    try:
        client = TestClient(app)
        response = start(client, deck, seed)
        while not response.json()["view"]["match_over"]:
            legal = response.json()["view"]["legal_actions"]
            response = play(client, response, choices.draw(st.sampled_from(legal)))

            assert response.status_code == 200
            view = response.json()["view"]
            assert view["current"] == HUMAN or view["match_over"]
            for event in response.json()["events"]:
                assert event["type"] not in {"cards_drawn", "card_redrawn"} or (
                    event["player"] == HUMAN
                )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "action",
    [
        # The player is swapping cards before round 1, so none of these is
        # legal now.
        {"type": "pass"},
        {"type": "revive", "card": "drone", "row": "ranged"},
        {"type": "play_unit", "card": "no-such-card", "row": "melee"},
        {"type": "redraw", "card": "no-such-card"},
    ],
)
def test_an_illegal_action_is_turned_down_and_changes_nothing(
    client: TestClient, store: MatchStore, action: dict[str, Any]
) -> None:
    response = start(client, seed=PLAYER_STARTS)
    before = state_of(store, response)

    turned_down = play(client, response, action)

    assert turned_down.status_code == 409
    assert turned_down.json()["code"] == "illegal_action"
    assert state_of(store, response) is before


def test_the_player_can_never_make_a_move_of_the_ais(
    client: TestClient, store: MatchStore
) -> None:
    # A match kept on the AI's turn, which the server never does: with this
    # seed the AI wins the coin flip, and nobody lets it play.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_STARTS)
    assert player_view(state, HUMAN).legal_actions == ()
    match_id = store.create(state)
    ai_view = schemas.from_view(player_view(state, AI)).model_dump(mode="json")

    for move in ai_view["legal_actions"]:
        response = client.post(f"/matches/{match_id}/actions", json=move)

        # Otherwise 200 and 409 would also tell the player the AI's cards.
        assert response.status_code == 409
        assert response.json()["code"] == "illegal_action"
    assert ai_view["legal_actions"]
    assert store.get(match_id) is state


@pytest.mark.parametrize(
    "action",
    [
        {},
        {"type": "play_unit", "card": "drone"},
        {"type": "play_unit", "card": "drone", "row": "sky"},
        {"type": "play_unit", "card": 1, "row": "melee"},
        {"type": "dance"},
        # A field the API doesn't know: maybe a typo, so it isn't left out.
        {"type": "pass", "player": 1},
        ["pass"],
    ],
)
def test_an_action_of_the_wrong_shape_is_turned_down(
    client: TestClient, store: MatchStore, action: Any
) -> None:
    response = start(client)
    before = state_of(store, response)

    turned_down = play(client, response, action)

    assert turned_down.status_code == 422
    assert turned_down.json()["code"] == "invalid_request"
    assert state_of(store, response) is before


def test_a_request_turned_down_says_where_its_first_mistake_is(
    client: TestClient,
) -> None:
    response = start(client)

    # Two mistakes: the card isn't a string, and there is no such row.
    action = {"type": "play_unit", "card": 1, "row": "sky"}
    turned_down = play(client, response, action)

    assert turned_down.json() == {
        "code": "invalid_request",
        "message": "The request isn't valid at body.play_unit.card: string_type.",
    }


def test_an_action_for_an_unknown_match_is_turned_down(client: TestClient) -> None:
    response = client.post(f"/matches/{uuid4()}/actions", json={"type": "pass"})

    assert response.status_code == 404
    assert response.json()["code"] == "match_not_found"


def test_an_action_on_a_match_that_changed_meanwhile_is_turned_down(
    client: TestClient, store: MatchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two requests get the same match at once, and the other one keeps its
    # result first, while this one plays its action.
    response = start(client)
    match_id = UUID(response.json()["id"])
    other = start_match((DECKS["humans"], DECKS["robots"]), seed=1)
    get = store.get

    def get_then_the_other_request_wins(match_id: UUID) -> GameState | None:
        state = get(match_id)
        assert state is not None
        assert store.replace(match_id, state, other)
        return state

    monkeypatch.setattr(store, "get", get_then_the_other_request_wins)

    turned_down = play(client, response, first_action(response))

    assert turned_down.status_code == 409
    assert turned_down.json()["code"] == "match_changed"
    # The other request's result is kept, not undone.
    monkeypatch.undo()
    assert store.get(match_id) is other


@pytest.mark.parametrize(
    "body",
    [
        {"deck": "SECRET" * 1000},
        {"deck": ["SECRET"]},
        {"deck": [[[[[[[[["SECRET"]]]]]]]]]},
        {"deck": "humans", "seed": "SECRET"},
    ],
)
def test_an_error_never_sends_a_value_back(client: TestClient, body: Any) -> None:
    # FastAPI's own answer would send back each wrong value.
    response = client.post("/matches", json=body)

    assert response.status_code == 422
    assert "SECRET" not in response.text


def test_a_value_nested_very_deep_is_turned_down(client: TestClient) -> None:
    deep = "[" * 5000 + "]" * 5000

    response = client.post(
        "/matches",
        content='{"deck": ' + deep + "}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_a_bug_on_the_server_is_answered_with_an_error_too(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The AI fails as it plays the first move of the match.
    def choose_action(view: PlayerView) -> Action:
        raise RuntimeError("SECRET")

    monkeypatch.setattr("rowen.api.app.choose_action", choose_action)
    # Unless told not to, the test client raises the errors of the server.
    server = TestClient(app, raise_server_exceptions=False)

    response = start(server, seed=AI_STARTS)

    assert response.status_code == 500
    assert response.json() == {
        "code": "server_error",
        "message": "Something went wrong on the server.",
    }


def test_an_unknown_address_is_turned_down(client: TestClient) -> None:
    response = client.get("/decks")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_unknown_method_is_turned_down(client: TestClient) -> None:
    response = client.delete("/matches")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert response.headers["Allow"] == "POST"
