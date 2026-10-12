"""Tests for the web API's endpoints, through FastAPI's test client.

The test client sends the app the requests a browser would send and gets the
same responses, without running a server.
"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from rowen.api import schemas
from rowen.api.app import AI, HUMAN, SEED_BITS, _ai_plays, app, get_store, new_seed
from rowen.api.store import MatchStore
from rowen.data import deck_ids, load_deck
from rowen.engine.public import GameState, apply, player_view, start_match

# Seeds of 20 digits, which no response can hold by chance. With the humans
# against the robots, the AI wins the coin flip with the first one, and the
# player with the second one.
AI_STARTS = 12_345_678_901_234_567_890
PLAYER_STARTS = 12_345_678_901_234_567_891

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
@pytest.mark.parametrize("method", ["POST", "GET"])
def test_the_seed_is_never_sent(client: TestClient, seed: int, method: str) -> None:
    response = start(client, seed=seed)
    if method == "GET":
        response = client.get(response.headers["Location"])

    sent = response.text + str(response.headers)
    assert str(seed) not in sent
    assert f"{seed:x}" not in sent


def test_the_ai_plays_first_when_it_wins_the_coin_flip(client: TestClient) -> None:
    decks = (DECKS["humans"], DECKS["robots"])
    assert player_view(start_match(decks, seed=AI_STARTS), HUMAN).current == AI

    view = start(client, seed=AI_STARTS).json()["view"]

    # The AI has done its redraw, and now it's the player's turn.
    assert view["players"][AI]["redraws_left"] == 0
    assert view["current"] == HUMAN


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
        "detail": "There is no such deck. The decks are: humans, robots."
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
    ],
)
def test_a_request_without_a_deck_is_turned_down(client: TestClient, body: Any) -> None:
    response = client.post("/matches", json=body)

    assert response.status_code == 422


def test_a_request_that_is_not_json_is_turned_down(client: TestClient) -> None:
    response = client.post("/matches", content="deck=humans")

    assert response.status_code == 422


def test_there_is_no_match_with_an_unknown_id(client: TestClient) -> None:
    start(client)

    response = client.get(f"/matches/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "There is no match with this id."}


@pytest.mark.parametrize("match_id", ["1", "not-an-id", "humans"])
def test_an_id_that_is_not_a_uuid_is_turned_down(
    client: TestClient, match_id: str
) -> None:
    response = client.get(f"/matches/{match_id}")

    assert response.status_code == 422


def test_seeds_are_big_and_random() -> None:
    seeds = {new_seed() for _ in range(100)}

    assert len(seeds) == 100
    assert all(0 <= seed < 2**SEED_BITS for seed in seeds)
    # A random seed of 64 bits is below 2**60 once in 16, so all 100 of them
    # are below it only if they are far smaller than they should be.
    assert max(seeds) >= 2**60


def test_every_request_gets_the_same_store() -> None:
    assert get_store() is get_store()


def test_the_ai_doesnt_play_once_the_match_is_over() -> None:
    # Each player plays the first legal action in their own view, to the end.
    # With this seed, the match ends with the AI as the current player.
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=0)
    view = player_view(state, HUMAN)
    while not view.match_over:
        state, _ = apply(state, player_view(state, view.current).legal_actions[0])
        view = player_view(state, HUMAN)
    assert view.current == AI

    assert _ai_plays(state) is state


def test_the_openapi_schema_lists_the_endpoints(client: TestClient) -> None:
    # The browser's types are built from this schema.
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/matches"]) == {"post"}
    assert set(paths["/matches/{match_id}"]) == {"get"}
