"""Tests for the decks a player builds: what they may choose, and their decks.

As in tests/test_api_history.py, the test client talks to the app over https,
so it sends the session's cookie back. Each test has stores of its own, in
memory: tests/test_api_player_decks.py checks that both stores behave the same.
"""

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rowen.api.accounts import MemoryAccountStore
from rowen.api.app import app, get_accounts, get_decks, get_now, get_store
from rowen.api.player_decks import MAX_DECKS, MemoryDeckStore
from rowen.api.store import MemoryMatchStore
from rowen.data import load_deck

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
RUI = {"username": "rui", "password": "dragon123"}
ANA = {"username": "ana", "password": "phoenix456"}

# The Humans' own deck, as a choice: it keeps to the rules.
HUMANS = dict(Counter(card.id for card in load_deck("humans").cards))


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return a test client for the app, over https, with stores of its own."""
    matches, accounts, decks = (
        MemoryMatchStore(),
        MemoryAccountStore(),
        MemoryDeckStore(),
    )
    app.dependency_overrides[get_store] = lambda: matches
    app.dependency_overrides[get_accounts] = lambda: accounts
    app.dependency_overrides[get_decks] = lambda: decks
    app.dependency_overrides[get_now] = lambda: NOW
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def as_(client: TestClient, credentials: dict[str, str]) -> None:
    """Make an account and log in with it: the client now sends its cookie."""
    assert client.post("/accounts", json=credentials).status_code == 201


def choice(**changes: Any) -> dict[str, Any]:
    """Return a deck to build: the Humans' own, with these changes."""
    return {"name": "Mine", "deck": "humans", "copies": HUMANS} | changes


def build(client: TestClient, **changes: Any) -> dict[str, Any]:
    """Build a deck and return it."""
    response = client.post("/my-decks", json=choice(**changes))
    assert response.status_code == 201
    deck: dict[str, Any] = response.json()
    return deck


def test_the_choices_are_each_card_once_with_the_most_copies() -> None:
    choices = TestClient(app).get("/decks/humans/choices")

    assert choices.status_code == 200
    body = choices.json()
    most = {choice["card"]["id"]: choice["most"] for choice in body["cards"]}
    # A Bond as many as the faction's deck has, a Legend 1, the rest 3, the
    # special cards included.
    assert most["human"] == 5
    assert most["plane"] == 4
    assert most["prime-minister"] == 1
    assert most["soldier"] == 3
    assert most["war-horn"] == 3
    assert len(most) == len(body["cards"])
    # The units first, then the special cards.
    kinds = [choice["card"]["type"] for choice in body["cards"]]
    assert kinds == sorted(kinds, key=lambda kind: kind != "unit")
    assert (body["deck"], body["min_units"], body["max_specials"]) == ("humans", 22, 10)


def test_a_card_comes_as_in_a_match() -> None:
    body = TestClient(app).get("/decks/humans/choices").json()
    human = next(
        choice["card"] for choice in body["cards"] if choice["card"]["id"] == "human"
    )

    assert human["ability"] == "bond"
    assert human["description"]


def test_a_faction_that_doesnt_exist_has_no_choices() -> None:
    response = TestClient(app).get("/decks/elves/choices")

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_deck"


def test_a_guest_has_no_decks(client: TestClient) -> None:
    assert client.get("/my-decks").status_code == 401
    assert client.post("/my-decks", json=choice()).status_code == 401
    assert client.put(f"/my-decks/{uuid4()}", json=choice()).status_code == 401
    assert client.delete(f"/my-decks/{uuid4()}").status_code == 401
    assert client.get("/my-decks").json()["code"] == "not_logged_in"


def test_a_deck_is_built_and_listed(client: TestClient) -> None:
    as_(client, RUI)

    deck = build(client)

    assert deck["name"] == "Mine"
    assert deck["deck"] == "humans"
    assert deck["copies"] == HUMANS
    assert client.get("/my-decks").json() == {"decks": [deck], "most": MAX_DECKS}


def test_the_spaces_around_a_name_are_left_out(client: TestClient) -> None:
    as_(client, RUI)

    assert build(client, name="  Mine  ")["name"] == "Mine"


# U+0085 is a space to Python, which leaves it out, and not to the browser.
@pytest.mark.parametrize("name", ["", "   ", "\u0085", "x" * 31])
def test_a_name_has_1_to_30_characters(client: TestClient, name: str) -> None:
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(name=name))

    # Said for the player, who sees it.
    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_request",
        "message": "A deck's name needs 1 to 30 characters, and no invisible ones.",
    }


@pytest.mark.parametrize(
    "name",
    [
        "a\u0000b",  # NUL, which PostgreSQL can't keep
        "a\u001fb",  # a control character
        "a\nb",  # a new line inside the name
        "a\u200bb",  # a zero-width space
        "\u202ebad",  # a right-to-left override
        "a\u2028b",  # a line separator
    ],
)
def test_a_name_has_no_control_or_invisible_characters(
    client: TestClient, name: str
) -> None:
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(name=name))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_a_name_may_have_accents_and_symbols(client: TestClient) -> None:
    as_(client, RUI)

    assert build(client, name="Ação ✨ 2")["name"] == "Ação ✨ 2"


def test_a_name_may_have_30_characters(client: TestClient) -> None:
    as_(client, RUI)

    assert build(client, name="x" * 30)["name"] == "x" * 30


def test_a_deck_of_a_faction_that_doesnt_exist_is_turned_down(
    client: TestClient,
) -> None:
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(deck="elves"))

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_deck"


@pytest.mark.parametrize(
    "copies",
    [{"<img src=x onerror=alert(1)>": "x"}, {"x" * 65: 1}],
)
def test_a_card_id_the_api_turns_down_isnt_sent_back(
    client: TestClient, copies: dict[str, Any]
) -> None:
    # The keys of copies are the client's: the answer stops at copies.
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(copies=copies))

    assert response.status_code == 422
    assert response.json()["message"].startswith(
        "The request isn't valid at body.copies: "
    )


@pytest.mark.parametrize(
    "copies",
    [
        # Too many copies of a card, of a Legend, of a Bond.
        HUMANS | {"soldier": 4},
        HUMANS | {"prime-minister": 2},
        HUMANS | {"human": 6},
        # No copies.
        HUMANS | {"medic": 0},
        # A card of the other faction, and one that doesn't exist.
        HUMANS | {"robot": 1},
        HUMANS | {"<script>": 1},
        # Too few units, and too many special cards.
        {card: count for card, count in HUMANS.items() if card != "human"},
        HUMANS | {"hoarfrost": 3, "thick-fog": 3, "downpour": 3},
    ],
)
def test_a_deck_that_breaks_the_rules_is_turned_down(
    client: TestClient, copies: dict[str, int]
) -> None:
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(copies=copies))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_deck"
    # The message never holds a value from the request, and is for the
    # player: it names no address of the API.
    assert "<script>" not in response.text
    assert "/decks" not in response.json()["message"]
    assert client.get("/my-decks").json()["decks"] == []


@pytest.mark.parametrize("count", [True, 1.0, "1"])
def test_a_number_of_copies_is_a_whole_number(client: TestClient, count: Any) -> None:
    as_(client, RUI)

    response = client.post("/my-decks", json=choice(copies=HUMANS | {"medic": count}))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_a_player_may_keep_up_to_ten_decks(client: TestClient) -> None:
    as_(client, RUI)
    for n in range(MAX_DECKS):
        build(client, name=str(n))

    response = client.post("/my-decks", json=choice())

    assert response.status_code == 409
    assert response.json()["code"] == "too_many_decks"
    assert len(client.get("/my-decks").json()["decks"]) == MAX_DECKS


def test_a_deck_is_changed_all_at_once(client: TestClient) -> None:
    as_(client, RUI)
    deck = build(client)
    robots = dict(Counter(card.id for card in load_deck("robots").cards))

    response = client.put(
        f"/my-decks/{deck['id']}",
        json=choice(name="Robots", deck="robots", copies=robots),
    )

    assert response.status_code == 200
    changed = {"id": deck["id"], "name": "Robots", "deck": "robots", "copies": robots}
    assert response.json() == changed
    assert client.get("/my-decks").json()["decks"] == [changed]


def test_a_change_that_breaks_the_rules_leaves_the_deck_as_it_was(
    client: TestClient,
) -> None:
    as_(client, RUI)
    deck = build(client)

    response = client.put(
        f"/my-decks/{deck['id']}", json=choice(copies=HUMANS | {"soldier": 4})
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_deck"
    assert client.get("/my-decks").json()["decks"] == [deck]


def test_a_deck_is_deleted(client: TestClient) -> None:
    as_(client, RUI)
    deck = build(client)

    deleted = client.delete(f"/my-decks/{deck['id']}")

    assert deleted.status_code == 204
    assert client.get("/my-decks").json()["decks"] == []
    assert client.delete(f"/my-decks/{deck['id']}").status_code == 404


def test_another_players_deck_is_a_deck_that_doesnt_exist(client: TestClient) -> None:
    as_(client, RUI)
    deck = build(client)
    client.delete("/session")
    as_(client, ANA)

    changed = client.put(f"/my-decks/{deck['id']}", json=choice(name="Hers"))
    deleted = client.delete(f"/my-decks/{deck['id']}")
    unknown = client.delete(f"/my-decks/{uuid4()}")

    assert client.get("/my-decks").json()["decks"] == []
    for response in (changed, deleted, unknown):
        assert response.status_code == 404
        assert response.json() == unknown.json()
    assert unknown.json()["code"] == "deck_not_found"


def test_a_deck_from_a_page_of_another_site_is_turned_down(client: TestClient) -> None:
    as_(client, RUI)

    response = client.post(
        "/my-decks", json=choice(), headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert client.get("/my-decks").json()["decks"] == []
