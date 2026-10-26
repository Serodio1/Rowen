"""Tests for the web API's accounts: registering, logging in and out, sessions.

The test client talks to the app over https, as the browser does online:
over plain http, it wouldn't send the cookie back, which is Secure.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from rowen.api.accounts import AccountStore, MemoryAccountStore
from rowen.api.app import (
    RENEW_AFTER,
    SESSION_COOKIE,
    SESSION_LENGTH,
    app,
    get_accounts,
    get_now,
    get_store,
)
from rowen.api.store import MemoryMatchStore

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
RUI = {"username": "rui", "password": "dragon123"}
# The address of the test client's requests, as a browser would send it in
# Origin from the game's own page.
OWN_ORIGIN = "https://testserver"


class Clock:
    """The time the app sees, which a test moves on."""

    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def accounts() -> AccountStore:
    """Return an empty store of accounts, for one test."""
    return MemoryAccountStore()


@pytest.fixture
def clock() -> Clock:
    """Return the app's clock for one test, at NOW."""
    return Clock()


@pytest.fixture
def client(accounts: AccountStore, clock: Clock) -> Iterator[TestClient]:
    """Return a test client for the app, over https, with this test's stores."""
    app.dependency_overrides[get_store] = MemoryMatchStore
    app.dependency_overrides[get_accounts] = lambda: accounts
    app.dependency_overrides[get_now] = clock
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def register(client: TestClient) -> None:
    """Make Rui's account, which also logs in."""
    response = client.post("/accounts", json=RUI)
    assert response.status_code == 201


def logged_in_as(client: TestClient) -> str | None:
    """Return the username the client is logged in with, or None."""
    response = client.get("/session")
    if response.status_code == 401:
        assert response.json()["code"] == "not_logged_in"
        return None
    assert response.status_code == 200
    username: str = response.json()["username"]
    return username


def test_registering_logs_in(client: TestClient) -> None:
    response = client.post("/accounts", json=RUI)

    assert response.status_code == 201
    assert response.json() == {"username": "rui"}
    assert logged_in_as(client) == "rui"


def test_the_session_cookie_is_safe(client: TestClient) -> None:
    response = client.post("/accounts", json=RUI)

    cookie = response.headers["set-cookie"]
    name, token = cookie.split(";")[0].split("=")
    assert name == SESSION_COOKIE
    assert len(token) == 43  # 32 random bytes, in base64
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert attributes == {
        "httponly",
        "secure",
        "samesite=lax",
        "path=/",
        f"max-age={int(SESSION_LENGTH.total_seconds())}",
    }


def test_no_response_holds_the_password_or_its_hash(client: TestClient) -> None:
    registered = client.post("/accounts", json=RUI)
    logged = client.post("/session", json=RUI)
    seen = client.get("/session")

    for response in (registered, logged, seen):
        assert RUI["password"] not in response.text
        assert "argon2" not in response.text


def test_a_username_is_taken_once(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/accounts", json={"username": "rui", "password": "another password"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "username_taken"


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "Rui", "password": "dragon123"},
        {"username": "ru", "password": "dragon123"},
        {"username": "r" * 21, "password": "dragon123"},
        {"username": "rui vasconcelos", "password": "dragon123"},
        {"username": "rui\n", "password": "dragon123"},
        {"username": "rui", "password": "dragon1"},
        {"username": "rui", "password": "d" * 129},
        {"username": "rui"},
        {"username": "rui", "password": "dragon123", "admin": True},
    ],
)
def test_a_wrong_username_or_password_makes_no_account(
    client: TestClient, credentials: dict[str, object]
) -> None:
    response = client.post("/accounts", json=credentials)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert "dragon" not in response.text
    assert logged_in_as(client) is None


def test_the_longest_username_and_password_and_the_shortest_are_fine(
    client: TestClient,
) -> None:
    for credentials in (
        {"username": "a_1", "password": "8 chars!"},
        {"username": "z-9" + "x" * 17, "password": "p" * 128},
    ):
        assert client.post("/accounts", json=credentials).status_code == 201


def test_logging_in_with_the_right_password(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post("/session", json=RUI)

    assert response.status_code == 200
    assert response.json() == {"username": "rui"}
    assert SESSION_COOKIE in response.cookies
    assert logged_in_as(client) == "rui"


def test_a_wrong_password_and_an_unknown_username_get_the_same_answer(
    client: TestClient,
) -> None:
    register(client)
    client.cookies.clear()

    wrong = client.post("/session", json={**RUI, "password": "dragon124"})
    unknown = client.post("/session", json={**RUI, "username": "ana"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["code"] == "wrong_credentials"
    assert "set-cookie" not in wrong.headers
    assert logged_in_as(client) is None


def test_without_a_cookie_nobody_is_logged_in(client: TestClient) -> None:
    assert logged_in_as(client) is None


def test_a_made_up_token_is_nobody(client: TestClient) -> None:
    register(client)
    client.cookies.set(SESSION_COOKIE, "made-up")

    assert logged_in_as(client) is None


def test_logging_out_ends_the_session(client: TestClient) -> None:
    register(client)
    token = client.cookies[SESSION_COOKIE]

    response = client.delete("/session")

    assert response.status_code == 204
    assert response.content == b""
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE.lower()}=")
    assert "max-age=0" in cookie
    assert logged_in_as(client) is None
    # The token is worth nothing now, even sent again.
    client.cookies.set(SESSION_COOKIE, token)
    assert logged_in_as(client) is None


def test_logging_in_again_ends_the_browsers_last_session(client: TestClient) -> None:
    # The new cookie takes the place of the last one, so nobody could use
    # that session any more: it doesn't stay in the store for 30 days.
    register(client)
    last = client.cookies[SESSION_COOKIE]

    assert client.post("/session", json=RUI).status_code == 200

    assert logged_in_as(client) == "rui"
    client.cookies.set(SESSION_COOKIE, last)
    assert logged_in_as(client) is None


def test_making_another_account_ends_the_browsers_last_session(
    client: TestClient,
) -> None:
    register(client)
    last = client.cookies[SESSION_COOKIE]

    response = client.post("/accounts", json={**RUI, "username": "ana"})
    assert response.status_code == 201

    assert logged_in_as(client) == "ana"
    client.cookies.set(SESSION_COOKIE, last)
    assert logged_in_as(client) is None


def test_logging_out_when_not_logged_in_is_fine(client: TestClient) -> None:
    assert client.delete("/session").status_code == 204


def test_logging_out_ends_only_that_session(client: TestClient) -> None:
    # As with a phone and a computer, each logged in on its own.
    register(client)
    other = TestClient(app, base_url="https://testserver")
    assert other.post("/session", json=RUI).status_code == 200

    client.delete("/session")

    assert logged_in_as(client) is None
    assert logged_in_as(other) == "rui"


def test_a_session_expires_30_days_after_the_player_was_last_seen(
    client: TestClient, clock: Clock
) -> None:
    register(client)

    clock.now = NOW + SESSION_LENGTH - timedelta(seconds=1)
    assert logged_in_as(client) == "rui"  # renewed: 30 days from now
    clock.now += SESSION_LENGTH - timedelta(seconds=1)
    assert logged_in_as(client) == "rui"
    clock.now += SESSION_LENGTH
    assert logged_in_as(client) is None


def test_a_session_is_renewed_at_most_once_a_day(
    client: TestClient, clock: Clock
) -> None:
    register(client)

    clock.now = NOW + RENEW_AFTER - timedelta(seconds=1)
    early = client.get("/session")
    clock.now = NOW + RENEW_AFTER + timedelta(seconds=1)
    late = client.get("/session")

    assert "set-cookie" not in early.headers
    assert late.headers["set-cookie"].startswith(
        f"{SESSION_COOKIE}={client.cookies[SESSION_COOKIE]};"
    )


def test_a_session_seen_on_its_first_day_still_ends_30_days_after_it_began(
    client: TestClient, clock: Clock
) -> None:
    register(client)

    clock.now = NOW + RENEW_AFTER - timedelta(seconds=1)
    assert logged_in_as(client) == "rui"
    clock.now = NOW + SESSION_LENGTH
    assert logged_in_as(client) is None


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/accounts", RUI),
        ("POST", "/session", RUI),
        ("DELETE", "/session", None),
        ("POST", "/matches", {"deck": "humans"}),
    ],
)
@pytest.mark.parametrize(
    "origin", ["https://evil.example", "https://testserver.evil.example", "null"]
)
def test_a_page_of_another_site_cant_change_anything(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
    origin: str,
) -> None:
    register(client)

    response = client.request(method, path, json=body, headers={"Origin": origin})

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_origin"
    assert "set-cookie" not in response.headers
    assert logged_in_as(client) == "rui"


def test_the_games_own_page_and_programs_can(client: TestClient) -> None:
    own = client.post("/accounts", json=RUI, headers={"Origin": OWN_ORIGIN})
    # curl, or a script, sends no Origin.
    program = client.post("/session", json=RUI)

    assert own.status_code == 201
    assert program.status_code == 200


def test_a_page_of_another_site_can_still_read(client: TestClient) -> None:
    # Reading changes nothing; the browser keeps the answer from that page
    # anyway, since the API sends no CORS headers.
    response = client.get("/decks", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200


def test_the_app_keeps_its_accounts_in_a_store_of_its_own() -> None:
    # No overrides: the app's own store, and the time now.
    client = TestClient(app, base_url="https://testserver")
    credentials = {"username": "own-store", "password": "dragon123"}
    client.post("/accounts", json=credentials)

    assert logged_in_as(client) == "own-store"
