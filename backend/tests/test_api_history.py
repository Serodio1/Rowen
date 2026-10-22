"""Tests for the matches of a player who is logged in: whose they are, their list.

As in tests/test_api_sessions.py, the test client talks to the app over https,
so it sends the session's cookie back. Each test has stores of its own, in
memory: tests/test_api_store.py checks that both stores behave the same.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from rowen.api.accounts import MemoryAccountStore
from rowen.api.app import (
    PAGE_SIZE,
    SESSION_COOKIE,
    app,
    get_accounts,
    get_now,
    get_store,
    new_seed,
)
from rowen.api.store import MatchStore, MemoryMatchStore

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
RUI = {"username": "rui", "password": "dragon123"}
ANA = {"username": "ana", "password": "phoenix456"}


class Clock:
    """The time the app sees, which a test moves on."""

    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def store() -> MatchStore:
    """Return an empty store of matches, for one test."""
    return MemoryMatchStore()


@pytest.fixture
def clock() -> Clock:
    """Return the app's clock for one test, at NOW."""
    return Clock()


@pytest.fixture
def client(store: MatchStore, clock: Clock) -> Iterator[TestClient]:
    """Return a test client for the app, over https, with this test's stores."""
    accounts = MemoryAccountStore()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_accounts] = lambda: accounts
    app.dependency_overrides[get_now] = clock
    app.dependency_overrides[new_seed] = lambda: 1
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def as_(client: TestClient, credentials: dict[str, str]) -> None:
    """Make an account and log in with it: the client now sends its cookie."""
    assert client.post("/accounts", json=credentials).status_code == 201


def start(client: TestClient, deck: str = "humans") -> httpx2.Response:
    """Start a match and return the response."""
    response = client.post("/matches", json={"deck": deck})
    assert response.status_code == 201
    return response


def play(client: TestClient, match: Any) -> httpx2.Response:
    """Play the first legal action of a match, as JSON, and return the response."""
    move = {"version": match["version"], "action": match["view"]["legal_actions"][0]}
    return client.post(f"/matches/{match['id']}/actions", json=move)


def play_to_the_end(client: TestClient, match: Any) -> list[Any]:
    """Play a match to its end with the first legal action each time.

    Return every event the player was sent, in order.
    """
    events = [event for move in match["moves"] for event in move["events"]]
    while not match["view"]["match_over"]:
        response = play(client, match)
        assert response.status_code == 200
        match = response.json()
        events += [event for move in match["moves"] for event in move["events"]]
    return events


def listed(client: TestClient, before: str | None = None) -> Any:
    """Return a page of the player's matches, as JSON."""
    params = {} if before is None else {"before": before}
    response = client.get("/matches", params=params)
    assert response.status_code == 200
    return response.json()


def test_a_match_started_logged_in_is_in_the_players_list(
    client: TestClient,
) -> None:
    as_(client, RUI)

    match = start(client).json()

    assert listed(client) == {
        "matches": [
            {
                "id": match["id"],
                "deck": "humans",
                "ai_deck": "robots",
                "started_at": "2026-10-22T12:00:00Z",
                "result": None,
            }
        ],
        "more": False,
    }


def test_a_guests_match_is_in_nobodys_list(client: TestClient) -> None:
    start(client)
    as_(client, RUI)

    assert listed(client) == {"matches": [], "more": False}


@pytest.mark.parametrize("path", ["/matches", "/stats"])
def test_a_guest_has_no_list_and_no_stats(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "not_logged_in"


def test_a_players_match_is_only_theirs(client: TestClient) -> None:
    as_(client, RUI)
    match = start(client).json()
    cookie = client.cookies[SESSION_COOKIE]
    client.cookies.clear()

    # To a guest and to another player, it is a match that doesn't exist, as
    # an unknown id is.
    unknown = client.get(f"/matches/{uuid4()}")
    for credentials in (None, ANA):
        if credentials is not None:
            as_(client, credentials)
        seen = client.get(f"/matches/{match['id']}")
        played = play(client, match)
        assert seen.status_code == played.status_code == 404
        assert seen.json() == played.json() == unknown.json()

    client.cookies.set(SESSION_COOKIE, cookie)
    assert client.get(f"/matches/{match['id']}").status_code == 200
    assert play(client, match).status_code == 200


def test_after_logging_out_the_players_match_is_out_of_reach(
    client: TestClient,
) -> None:
    as_(client, RUI)
    match = start(client).json()

    client.delete("/session")

    assert client.get(f"/matches/{match['id']}").status_code == 404


def test_a_guests_match_is_anybodys_who_has_its_id(client: TestClient) -> None:
    match = start(client).json()
    as_(client, RUI)

    assert client.get(f"/matches/{match['id']}").status_code == 200
    assert play(client, match).status_code == 200


def test_the_list_says_how_a_match_ended(client: TestClient, clock: Clock) -> None:
    as_(client, RUI)
    match = start(client).json()
    clock.now = NOW + timedelta(minutes=7)

    events = play_to_the_end(client, match)

    ended = next(event for event in events if event["type"] == "match_ended")
    rounds = [event["scores"] for event in events if event["type"] == "round_ended"]
    outcome = {0: "won", 1: "lost", None: "drawn"}[ended["winner"]]
    assert listed(client)["matches"][0]["result"] == {
        "outcome": outcome,
        "rounds": [{"player": player, "ai": ai} for player, ai in rounds],
        "ended_at": "2026-10-22T12:07:00Z",
    }
    assert len(rounds) >= 2


def test_stats_count_the_matches_that_ended(client: TestClient) -> None:
    as_(client, RUI)
    outcomes = []
    for deck in ("humans", "humans", "robots"):
        events = play_to_the_end(client, start(client, deck).json())
        ended = next(event for event in events if event["type"] == "match_ended")
        outcomes.append((deck, {0: "won", 1: "lost", None: "drawn"}[ended["winner"]]))
    # A match that goes on doesn't count.
    start(client)

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {
        "decks": [
            {
                "deck": deck,
                **{
                    outcome: outcomes.count((deck, outcome))
                    for outcome in ("won", "lost", "drawn")
                },
            }
            for deck in ("humans", "robots")
        ]
    }


def test_the_list_comes_a_page_at_a_time(client: TestClient, clock: Clock) -> None:
    as_(client, RUI)
    ids = []
    for minute in range(PAGE_SIZE + 3):
        clock.now = NOW + timedelta(minutes=minute)
        ids.append(start(client).json()["id"])

    first = listed(client)
    second = listed(client, before=first["matches"][-1]["id"])

    assert first["more"] is True
    assert second["more"] is False
    assert len(first["matches"]) == PAGE_SIZE
    pages = first["matches"] + second["matches"]
    assert [match["id"] for match in pages] == ids[::-1]


def test_a_full_last_page_says_there_are_no_more(client: TestClient) -> None:
    as_(client, RUI)
    for _ in range(PAGE_SIZE):
        start(client)

    assert listed(client)["more"] is False


def test_a_page_after_a_match_that_isnt_the_players_is_empty(
    client: TestClient,
) -> None:
    as_(client, RUI)
    ruis = start(client).json()
    client.cookies.clear()
    as_(client, ANA)
    start(client)

    assert listed(client, before=ruis["id"]) == {"matches": [], "more": False}


def test_a_page_after_something_that_isnt_an_id_is_turned_down(
    client: TestClient,
) -> None:
    as_(client, RUI)

    response = client.get("/matches", params={"before": "the-last-one"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
