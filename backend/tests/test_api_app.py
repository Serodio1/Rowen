"""Tests for the web API's endpoints, through FastAPI's test client.

The test client sends the app the requests a browser would send and gets the
same responses, without running a server.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen import data
from rowen.ai.baseline import choose_action
from rowen.api import schemas
from rowen.api.accounts import MemoryAccountStore
from rowen.api.app import (
    AI,
    HUMAN,
    _ai_plays,
    _replay,
    app,
    get_store,
    make_stores,
    new_seed,
)
from rowen.api.database import PostgresAccountStore, PostgresMatchStore
from rowen.api.store import FIRST_VERSION, MatchStore, MemoryMatchStore, StoredMatch
from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    Action,
    Event,
    GameState,
    Pass,
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
    return MemoryMatchStore()


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
    """Play an action from the view in a response, and return the new response.

    The move sends back the version of the match that came with the view.
    """
    move = {"version": response.json()["version"], "action": action}
    return client.post(f"/matches/{response.json()['id']}/actions", json=move)


def match_text(response: httpx2.Response) -> str:
    """Return the match in a response, its id, version and view, as GET sends it."""
    played = schemas.Played.model_validate_json(response.text)
    match = schemas.Match(id=played.id, version=played.version, view=played.view)
    return match.model_dump_json()


def first_action(response: httpx2.Response) -> Any:
    """Return the first legal action in the view of a response, as JSON."""
    return response.json()["view"]["legal_actions"][0]


def move_of(state: GameState, events: tuple[Event, ...]) -> schemas.MovePlayed:
    """Return an action's events and the state after it, as the player sees them."""
    return schemas.MovePlayed(
        events=schemas.from_events(events, HUMAN),
        view=schemas.from_view(player_view(state, HUMAN)),
    )


def ai_answers(
    state: GameState,
) -> tuple[GameState, tuple[schemas.MovePlayed, ...]]:
    """Let the baseline AI play from its own view, as the server does.

    Return the match once it is the player's turn or it is over, and the AI's
    moves, each with the view after it.
    """
    moves: tuple[schemas.MovePlayed, ...] = ()
    while (view := player_view(state, AI)).current == AI and not view.match_over:
        state, events = apply(state, choose_action(view))
        moves += (move_of(state, events),)
    return state, moves


def stored(store: MatchStore, response: httpx2.Response) -> StoredMatch:
    """Return what the store keeps for the match in a response."""
    match = store.get(UUID(response.json()["id"]))
    assert match is not None
    return match


def state_of(store: MatchStore, response: httpx2.Response) -> GameState:
    """Return the state of the match in a response, as the API plays it again."""
    return _replay(stored(store, response))


def test_the_decks_are_the_ones_in_the_data_files(client: TestClient) -> None:
    response = client.get("/decks")

    assert response.status_code == 200
    assert response.json() == {
        "decks": [
            {"id": "humans", "name": "Humans"},
            {"id": "robots", "name": "Robots"},
        ]
    }


def test_the_names_of_the_decks_are_read_from_the_data_files(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A copy of the data files where the humans have another name.
    shutil.copytree(Path(str(data._DATA)), tmp_path, dirs_exist_ok=True)
    humans = tmp_path / "decks" / "humans.json"
    text = humans.read_text(encoding="utf-8")
    humans.write_text(text.replace('"Humans"', '"The Humans"', 1), encoding="utf-8")
    monkeypatch.setattr(data, "_DATA", tmp_path)

    decks = client.get("/decks").json()["decks"]

    assert decks[0] == {"id": "humans", "name": "The Humans"}


def test_every_deck_in_the_list_can_start_a_match(client: TestClient) -> None:
    for deck in client.get("/decks").json()["decks"]:
        assert start(client, deck["id"]).status_code == 201


def test_a_new_match_gets_an_address_of_its_own(client: TestClient) -> None:
    response = start(client)

    assert response.status_code == 201
    match_id = UUID(response.json()["id"])
    # Version 4 is the kind of UUID made of random bits.
    assert match_id.version == 4
    assert response.headers["Location"] == f"/matches/{match_id}"


def test_behind_nginx_the_addresses_the_api_gives_out_start_with_api(
    client: TestClient,
) -> None:
    # In Docker, nginx serves the API under /api (ADR 0009), and uvicorn runs
    # with --root-path /api, which the test client's root_path stands in for:
    # the paths then start with /api, as uvicorn's do. The client fixture
    # still gives the app the store of this test. The docs page is FastAPI's,
    # checked because the README sends people to /api/docs.
    proxied = TestClient(app, root_path="/api")

    response = proxied.post("/api/matches", json={"deck": "humans"})
    docs = proxied.get("/api/docs")

    match_id = response.json()["id"]
    assert response.headers["Location"] == f"/api/matches/{match_id}"
    assert proxied.get(response.headers["Location"]).status_code == 200
    assert "'/api/openapi.json'" in docs.text


def test_the_player_gets_their_view_and_the_ais_first_moves(
    client: TestClient,
) -> None:
    # The same start, played with the engine and the AI directly.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_STARTS)
    state, moves = ai_answers(state)
    assert moves

    response = start(client, seed=AI_STARTS)

    sent = schemas.Played(
        id=UUID(response.json()["id"]),
        version=FIRST_VERSION,
        view=schemas.from_view(player_view(state, HUMAN)),
        moves=moves,
    )
    # The same JSON, as text: in Python, False == 0. Nothing more.
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


def test_a_new_match_is_kept_as_its_decks_seed_and_the_ais_first_actions(
    client: TestClient, store: MatchStore
) -> None:
    # The AI's first moves, chosen from its own view, as the server does.
    state = start_match((DECKS["robots"], DECKS["humans"]), seed=AI_STARTS)
    actions: list[Action] = []
    while (view := player_view(state, AI)).current == AI:
        actions.append(choose_action(view))
        state, _ = apply(state, actions[-1])

    response = start(client, "robots", AI_STARTS)

    match = stored(store, response)
    assert match.decks == ("robots", "humans")
    assert match.seed == AI_STARTS
    assert match.actions == tuple(actions)
    assert actions
    assert _replay(match) == state


def test_a_move_adds_the_players_action_and_the_ais_answer(
    client: TestClient, store: MatchStore
) -> None:
    response = start(client, seed=AI_DRAWS_AND_REDRAWS)
    while not response.json()["view"]["match_over"]:
        before = stored(store, response)
        state = _replay(before)
        action = player_view(state, HUMAN).legal_actions[0]
        state, _ = apply(state, action)
        answer: list[Action] = []
        while (view := player_view(state, AI)).current == AI and not view.match_over:
            answer.append(choose_action(view))
            state, _ = apply(state, answer[-1])

        response = play(client, response, first_action(response))

        after = stored(store, response)
        assert after.actions == (*before.actions, action, *answer)
        assert (after.decks, after.seed) == (before.decks, before.seed)
        assert _replay(after) == state


def test_the_ai_waits_when_the_player_wins_the_coin_flip(
    client: TestClient, store: MatchStore
) -> None:
    decks = (DECKS["humans"], DECKS["robots"])

    response = start(client, seed=PLAYER_STARTS)

    assert state_of(store, response) == start_match(decks, seed=PLAYER_STARTS)
    # No move was played, so nothing happened yet.
    assert response.json()["moves"] == []


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
    # The same match, without the AI's first moves: they come
    # only with the new match.
    assert response.text == match_text(started)


def test_each_match_has_an_id_of_its_own(client: TestClient) -> None:
    first = start(client, seed=AI_STARTS)
    second = start(client, seed=AI_STARTS)

    # The same seed gives the same match, but the id doesn't come from the seed.
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["view"] == second.json()["view"]
    for started in (first, second):
        assert client.get(started.headers["Location"]).text == match_text(started)


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
    # They fit PostgreSQL's BIGINT, whose largest value is 2**63 - 1.
    assert all(0 <= seed < 2**63 for seed in seeds)
    # A seed of 63 random bits is below 2**62 half the time, so all 100 of
    # them are below it once in 2**100: only if they have fewer bits.
    assert max(seeds) >= 2**62


@pytest.mark.parametrize("environ", [{}, {"DATABASE_URL": ""}])
def test_without_a_database_the_matches_are_kept_in_memory(
    environ: dict[str, str],
) -> None:
    store, accounts = make_stores(environ)

    assert isinstance(store, MemoryMatchStore)
    assert isinstance(accounts, MemoryAccountStore)


def test_with_a_database_the_matches_are_kept_there() -> None:
    # No connection is made until a match is asked for, so none here.
    url = "postgresql+psycopg://rowen:secret@db.example/rowen"

    store, accounts = make_stores({"DATABASE_URL": url})

    assert isinstance(store, PostgresMatchStore)
    assert isinstance(accounts, PostgresAccountStore)
    # On the same connections.
    assert store._engine is accounts._engine


def test_the_app_keeps_its_matches_in_a_store_of_its_own() -> None:
    # No overrides: the app's own store, and seeds chosen at random.
    client = TestClient(app)
    started = client.post("/matches", json={"deck": "humans"})
    client.post("/matches", json={"deck": "robots"})

    response = client.get(started.headers["Location"])

    assert response.text == match_text(started)


def test_the_ai_doesnt_play_once_the_match_is_over() -> None:
    # Each player plays the first legal action in their own view, to the end.
    # With this seed, the match ends with the AI as the current player.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=0)
    view = player_view(state, HUMAN)
    while not view.match_over:
        state, _ = apply(state, player_view(state, view.current).legal_actions[0])
        view = player_view(state, HUMAN)
    assert view.current == AI

    assert _ai_plays(state) == (state, (), ())
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
        # Or nothing at all: a 204 has no body.
        if route.status_code == 204:
            assert route.response_model is None, route.path
            continue
        assert isinstance(route.response_model, type), route.path
        assert issubclass(route.response_model, schemas.Schema), route.path


def test_the_openapi_schema_lists_the_endpoints(client: TestClient) -> None:
    # The browser's types are built from this schema.
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/decks"]) == {"get"}
    assert set(paths["/matches"]) == {"post"}
    assert set(paths["/matches/{match_id}"]) == {"get"}
    assert set(paths["/matches/{match_id}/actions"]) == {"post"}
    assert set(paths["/accounts"]) == {"post"}
    assert set(paths["/session"]) == {"get", "post", "delete"}


@pytest.mark.parametrize(
    ("path", "method", "errors"),
    [
        ("/decks", "get", set()),
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
        # Its last move leaves the match as it is now.
        assert response.json()["moves"][-1]["view"] == view
        # And the match is kept as it was sent.
        match = client.get(f"/matches/{response.json()['id']}").json()
        assert match["view"] == view

    # Once the match is over, there is nothing left to play.
    response = play(client, response, {"type": "pass"})
    assert response.status_code == 409
    assert response.json()["code"] == "illegal_action"


def test_the_moves_are_the_players_action_and_then_the_ais_answer(
    client: TestClient,
) -> None:
    # The same match, played with the engine and the AI directly.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_DRAWS_AND_REDRAWS)
    state, _ = ai_answers(state)
    response = start(client, seed=AI_DRAWS_AND_REDRAWS)
    version = FIRST_VERSION

    while not response.json()["view"]["match_over"]:
        action = first_action(response)
        state, events = apply(state, player_view(state, HUMAN).legal_actions[0])
        move = move_of(state, events)
        state, answer = ai_answers(state)

        response = play(client, response, action)
        version += 1

        sent = schemas.Played(
            id=UUID(response.json()["id"]),
            version=version,
            view=schemas.from_view(player_view(state, HUMAN)),
            moves=(move, *answer),
        )
        assert response.text == sent.model_dump_json()


def test_the_player_never_gets_the_cards_the_ai_drew_or_swapped(
    client: TestClient,
) -> None:
    events = []
    response = start(client, seed=AI_DRAWS_AND_REDRAWS)
    while not response.json()["view"]["match_over"]:
        response = play(client, response, first_action(response))
        events += [e for move in response.json()["moves"] for e in move["events"]]

    the_ais = {event["type"] for event in events if event.get("player") == AI}
    assert {"opponent_drew", "opponent_redrew"} <= the_ais
    assert not {"cards_drawn", "card_redrawn"} & the_ais


@settings(max_examples=20, deadline=None)
@given(
    deck=st.sampled_from(["humans", "robots"]),
    seed=st.integers(0, 2**63 - 1),
    choices=st.data(),
)
def test_any_legal_action_can_be_played_through_the_api(
    deck: str, seed: int, choices: st.DataObject
) -> None:
    # A store and a client of its own for each match Hypothesis tries.
    store = MemoryMatchStore()
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
            events = [e for move in response.json()["moves"] for e in move["events"]]
            for event in events:
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
    before = stored(store, response)

    turned_down = play(client, response, action)

    assert turned_down.status_code == 409
    assert turned_down.json()["code"] == "illegal_action"
    assert stored(store, response) == before


def test_the_player_can_never_make_a_move_of_the_ais(
    client: TestClient, store: MatchStore
) -> None:
    # A match kept on the AI's turn, which the server never does: with this
    # seed the AI wins the coin flip, and nobody lets it play.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=AI_STARTS)
    assert player_view(state, HUMAN).legal_actions == ()
    match = store.create(("humans", "robots"), AI_STARTS, ())
    ai_view = schemas.from_view(player_view(state, AI)).model_dump(mode="json")

    for action in ai_view["legal_actions"]:
        move = {"version": match.version, "action": action}
        response = client.post(f"/matches/{match.id}/actions", json=move)

        # Otherwise 200 and 409 would also tell the player the AI's cards.
        assert response.status_code == 409
        assert response.json()["code"] == "illegal_action"
    assert ai_view["legal_actions"]
    assert store.get(match.id) == match


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
    before = stored(store, response)

    turned_down = play(client, response, action)

    assert turned_down.status_code == 422
    assert turned_down.json()["code"] == "invalid_request"
    assert stored(store, response) == before


@pytest.mark.parametrize(
    "move",
    [
        # An action alone, as moves were sent before they had a version.
        {"type": "pass"},
        {"action": {"type": "pass"}},
        {"version": "first", "action": {"type": "pass"}},
        {"version": None, "action": {"type": "pass"}},
        {"version": FIRST_VERSION},
        {"version": FIRST_VERSION, "action": {"type": "pass"}, "player": 0},
    ],
)
def test_a_move_without_a_version_and_an_action_is_turned_down(
    client: TestClient, store: MatchStore, move: Any
) -> None:
    response = start(client)
    before = stored(store, response)

    turned_down = client.post(f"/matches/{response.json()['id']}/actions", json=move)

    assert turned_down.status_code == 422
    assert turned_down.json()["code"] == "invalid_request"
    assert stored(store, response) == before


def test_a_request_turned_down_says_where_its_first_mistake_is(
    client: TestClient,
) -> None:
    response = start(client)

    # Two mistakes: the card isn't a string, and there is no such row.
    action = {"type": "play_unit", "card": 1, "row": "sky"}
    turned_down = play(client, response, action)

    assert turned_down.json() == {
        "code": "invalid_request",
        "message": (
            "The request isn't valid at body.action.play_unit.card: string_type."
        ),
    }


def test_an_action_for_an_unknown_match_is_turned_down(client: TestClient) -> None:
    move = {"version": FIRST_VERSION, "action": {"type": "pass"}}
    response = client.post(f"/matches/{uuid4()}/actions", json=move)

    assert response.status_code == 404
    assert response.json()["code"] == "match_not_found"


def test_an_action_on_a_match_that_changed_meanwhile_is_turned_down(
    client: TestClient, store: MatchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two requests get the same match at once, and the other one keeps its
    # result first, while this one plays its action.
    response = start(client)
    get = store.get
    kept: list[StoredMatch] = []

    def get_then_the_other_request_wins(match_id: UUID) -> StoredMatch | None:
        match = get(match_id)
        assert match is not None
        other = player_view(_replay(match), HUMAN).legal_actions[-1]
        new = store.add_actions(match_id, match.version, (other,))
        assert new is not None
        kept.append(new)
        return match

    monkeypatch.setattr(store, "get", get_then_the_other_request_wins)

    turned_down = play(client, response, first_action(response))

    assert turned_down.status_code == 409
    assert turned_down.json()["code"] == "match_changed"
    # The other request's result is kept, not undone.
    monkeypatch.undo()
    assert [stored(store, response)] == kept


def test_each_move_takes_the_match_to_the_next_version(client: TestClient) -> None:
    response = start(client, seed=PLAYER_STARTS)
    assert response.json()["version"] == FIRST_VERSION

    for version in range(FIRST_VERSION + 1, FIRST_VERSION + 4):
        response = play(client, response, first_action(response))

        assert response.json()["version"] == version
        seen = client.get(f"/matches/{response.json()['id']}")
        assert seen.text == match_text(response)


def test_a_move_that_comes_late_is_not_played_again(
    client: TestClient, store: MatchStore
) -> None:
    # The player redraws a card, and the answer is lost on its way back. The
    # page gets the match again, the player redraws the same card, and then
    # the first move reaches the server once more, as a proxy can send it
    # again: the same move, still legal, chosen from the first view.
    # With this seed the player has two soldiers.
    started = start(client, seed=PLAYER_STARTS)
    redraw = {"type": "redraw", "card": "soldier"}
    played = play(client, started, redraw)
    assert played.status_code == 200
    assert redraw in played.json()["view"]["legal_actions"]
    before = stored(store, played)

    late = play(client, started, redraw)

    assert late.status_code == 409
    assert late.json()["code"] == "match_changed"
    assert stored(store, played) == before


@pytest.mark.parametrize("offset", [-1, 1, 1000])
def test_a_move_from_another_version_is_turned_down_and_changes_nothing(
    client: TestClient, store: MatchStore, offset: int
) -> None:
    response = start(client)
    before = stored(store, response)
    move = {
        "version": response.json()["version"] + offset,
        "action": first_action(response),
    }

    turned_down = client.post(f"/matches/{response.json()['id']}/actions", json=move)

    assert turned_down.status_code == 409
    assert turned_down.json() == {
        "code": "match_changed",
        "message": "The match changed since this action was chosen. Get it again.",
    }
    assert stored(store, response) == before


def test_the_version_is_checked_before_whether_the_action_is_legal(
    client: TestClient,
) -> None:
    # An illegal action from an old view: the view is what is out of date.
    response = start(client, seed=PLAYER_STARTS)
    move = {"version": FIRST_VERSION + 1, "action": {"type": "pass"}}

    turned_down = client.post(f"/matches/{response.json()['id']}/actions", json=move)

    assert turned_down.status_code == 409
    assert turned_down.json()["code"] == "match_changed"


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


def test_an_illegal_move_of_the_ai_is_a_bug_on_the_server(
    client: TestClient, store: MatchStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # After the player's redraw, the AI swaps cards: it can't pass yet.
    response = start(client, seed=PLAYER_STARTS)
    before = stored(store, response)

    def choose_action(view: PlayerView) -> Action:
        return Pass()

    monkeypatch.setattr("rowen.api.app.choose_action", choose_action)
    server = TestClient(app, raise_server_exceptions=False)

    failed = play(server, response, {"type": "end_redraw"})

    # Not a 409: the player did nothing wrong.
    assert failed.status_code == 500
    assert failed.json()["code"] == "server_error"
    # Not even the player's action is kept.
    assert stored(store, response) == before


def test_an_unknown_address_is_turned_down(client: TestClient) -> None:
    response = client.get("/no-such-address")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_address_with_a_slash_at_the_end_is_unknown_not_redirected(
    client: TestClient,
) -> None:
    response = client.get("/decks/", follow_redirects=False)

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_unknown_method_is_turned_down(client: TestClient) -> None:
    response = client.delete("/matches")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert response.headers["Allow"] == "POST"
