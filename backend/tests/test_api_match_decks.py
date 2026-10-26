"""Tests for matches played with a deck the player built (ADR 0017).

As in tests/test_api_my_decks.py, the test client talks to the app over https,
so it sends the session's cookie back, and each test has stores of its own, in
memory.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rowen.api.accounts import MemoryAccountStore
from rowen.api.app import app, get_accounts, get_decks, get_now, get_store, new_seed
from rowen.api.player_decks import MemoryDeckStore
from rowen.api.store import MemoryMatchStore

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
RUI = {"username": "rui", "password": "dragon123"}
ANA = {"username": "ana", "password": "phoenix456"}

# 22 units of the Humans and no Plane, nor any special card: a deck unlike
# the faction's own, whose cards are easy to tell apart.
NO_PLANES = {
    "human": 5,
    "soldier": 3,
    "sniper": 3,
    "informant": 3,
    "medic": 3,
    "smart-guy": 3,
    "prime-minister": 1,
    "president": 1,
}


@pytest.fixture
def decks() -> MemoryDeckStore:
    """Return an empty store of decks, for one test."""
    return MemoryDeckStore()


@pytest.fixture
def client(decks: MemoryDeckStore) -> Iterator[TestClient]:
    """Return a test client for the app, over https, with stores of its own."""
    matches, accounts = MemoryMatchStore(), MemoryAccountStore()
    app.dependency_overrides[get_store] = lambda: matches
    app.dependency_overrides[get_accounts] = lambda: accounts
    app.dependency_overrides[get_decks] = lambda: decks
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[new_seed] = lambda: 1
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def as_(client: TestClient, credentials: dict[str, str]) -> None:
    """Make an account and log in with it: the client now sends its cookie."""
    assert client.post("/accounts", json=credentials).status_code == 201


def build(client: TestClient, copies: dict[str, int] = NO_PLANES) -> str:
    """Build a deck of the Humans and return its id."""
    response = client.post(
        "/my-decks", json={"name": "No planes", "deck": "humans", "copies": copies}
    )
    assert response.status_code == 201
    deck_id: str = response.json()["id"]
    return deck_id


def start(client: TestClient, deck_id: str) -> dict[str, Any]:
    """Start a match with a deck the player built, and return it."""
    response = client.post("/matches", json={"my_deck": deck_id})
    assert response.status_code == 201
    match: dict[str, Any] = response.json()
    return match


def cards(view: dict[str, Any]) -> set[str]:
    """Return the ids of the cards in the player's hand."""
    return {card["id"] for card in view["hand"]}


def test_a_match_is_played_with_the_deck_the_player_built(client: TestClient) -> None:
    as_(client, RUI)

    match = start(client, build(client))

    assert match["view"]["hand"]
    assert cards(match["view"]) <= NO_PLANES.keys()


def test_the_match_is_listed_with_the_decks_name_and_its_faction(
    client: TestClient,
) -> None:
    as_(client, RUI)
    match = start(client, build(client))

    (listed,) = client.get("/matches").json()["matches"]

    assert listed["id"] == match["id"]
    assert (listed["deck"], listed["deck_name"]) == ("humans", "No planes")
    # The AI plays the other faction's own deck.
    assert listed["ai_deck"] == "robots"


def test_a_match_with_the_factions_own_deck_has_no_decks_name(
    client: TestClient,
) -> None:
    as_(client, RUI)
    client.post("/matches", json={"deck": "humans"})

    (listed,) = client.get("/matches").json()["matches"]

    assert listed["deck_name"] is None


def test_changing_the_deck_doesnt_change_a_match_played_with_it(
    client: TestClient,
) -> None:
    # The match keeps its own copy of the deck: played again from the
    # deck as it is now, the same seed would deal other cards.
    as_(client, RUI)
    deck_id = build(client)
    match = start(client, deck_id)
    planes = {"plane": 4, "human": 3, "soldier": 3, "sniper": 3, "informant": 3}
    changed = client.put(
        f"/my-decks/{deck_id}",
        json={
            "name": "Planes",
            "deck": "humans",
            "copies": planes | {"medic": 3, "smart-guy": 3, "prime-minister": 1},
        },
    )
    assert changed.status_code == 200

    seen = client.get(f"/matches/{match['id']}")

    assert seen.json()["view"] == match["view"]
    (listed,) = client.get("/matches").json()["matches"]
    assert listed["deck_name"] == "No planes"


def test_a_match_plays_on_after_its_deck_is_deleted(client: TestClient) -> None:
    as_(client, RUI)
    deck_id = build(client)
    match = start(client, deck_id)
    assert client.delete(f"/my-decks/{deck_id}").status_code == 204

    move = {"version": match["version"], "action": match["view"]["legal_actions"][0]}
    played = client.post(f"/matches/{match['id']}/actions", json=move)

    assert played.status_code == 200
    assert cards(played.json()["view"]) <= NO_PLANES.keys()


def test_the_stats_count_a_built_deck_with_its_faction(client: TestClient) -> None:
    as_(client, RUI)
    match = start(client, build(client))
    # The player passes every time it is their turn, until the match ends.
    while not match["view"]["match_over"]:
        move = {"version": match["version"], "action": {"type": "pass"}}
        if move["action"] not in match["view"]["legal_actions"]:
            move["action"] = match["view"]["legal_actions"][0]
        match = client.post(f"/matches/{match['id']}/actions", json=move).json()

    (stats,) = client.get("/stats").json()["decks"]

    assert stats["deck"] == "humans"
    assert stats["won"] + stats["lost"] + stats["drawn"] == 1


def test_a_guest_has_no_deck_to_play(client: TestClient) -> None:
    response = client.post("/matches", json={"my_deck": str(uuid4())})

    assert response.status_code == 401
    assert response.json()["code"] == "not_logged_in"


def test_another_players_deck_is_a_deck_that_doesnt_exist(client: TestClient) -> None:
    as_(client, RUI)
    deck_id = build(client)
    client.delete("/session")
    as_(client, ANA)

    theirs = client.post("/matches", json={"my_deck": deck_id})
    unknown = client.post("/matches", json={"my_deck": str(uuid4())})

    for response in (theirs, unknown):
        assert response.status_code == 404
        assert response.json() == unknown.json()
    assert unknown.json()["code"] == "deck_not_found"
    assert client.get("/matches").json()["matches"] == []


@pytest.mark.parametrize(
    "body", [{}, {"deck": "humans", "my_deck": str(uuid4())}, {"deck": None}]
)
def test_a_match_needs_exactly_one_deck(
    client: TestClient, body: dict[str, Any]
) -> None:
    as_(client, RUI)

    response = client.post("/matches", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_a_kept_deck_that_breaks_the_rules_now_starts_no_match(
    client: TestClient, decks: MemoryDeckStore
) -> None:
    # As if the rules changed after the deck was built: the store doesn't
    # check a deck, so one that breaks them is put in it straight away.
    as_(client, RUI)
    deck_id = build(client)
    owner = next(iter(decks._decks.values())).owner
    decks.replace_deck(owner, next(iter(decks._decks)), "Old", "humans", {"human": 5})

    response = client.post("/matches", json={"my_deck": deck_id})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_deck"
    assert client.get("/matches").json()["matches"] == []
