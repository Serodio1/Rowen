"""Tests for the level of the AI a match is played at (ADR 0018).

As in tests/test_api_match_decks.py, the test client talks to the app over
https, so it sends the session's cookie back, and each test has stores of its
own, in memory. The Monte Carlo AI is watched through a spy, which records how
the API calls it and then lets it choose.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rowen.ai import montecarlo
from rowen.api.accounts import MemoryAccountStore
from rowen.api.app import (
    app,
    get_accounts,
    get_decks,
    get_now,
    get_store,
    new_ai_seed,
    new_seed,
)
from rowen.api.player_decks import MemoryDeckStore
from rowen.api.store import MemoryMatchStore
from rowen.data import load_deck
from rowen.engine.public import Action, Card, PlayerView

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)
RUI = {"username": "rui", "password": "dragon123"}

# With this seed, the humans against the robots, the AI wins the coin flip:
# it redraws first, so it chooses before the response comes.
AI_STARTS = 12_345_678_901_234_567_890

# The seed of the AI's guesses in each request, which the tests choose.
AI_SEED = 1_000


@dataclass(frozen=True)
class Call:
    """How the API called the Monte Carlo AI once."""

    decks: tuple[tuple[Card, ...], tuple[Card, ...]]
    samples: int
    seed: int


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    """Return the calls to the Monte Carlo AI during a test, as they happen."""
    made: list[Call] = []
    choose = montecarlo.choose_action

    def spy(
        view: PlayerView,
        *,
        decks: tuple[tuple[Card, ...], tuple[Card, ...]],
        samples: int,
        seed: int,
    ) -> Action:
        made.append(Call(decks=decks, samples=samples, seed=seed))
        return choose(view, decks=decks, samples=samples, seed=seed)

    monkeypatch.setattr(montecarlo, "choose_action", spy)
    return made


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
    app.dependency_overrides[new_seed] = lambda: AI_STARTS
    app.dependency_overrides[new_ai_seed] = lambda: AI_SEED
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def start(client: TestClient, **new_match: Any) -> dict[str, Any]:
    """Start a match with the humans, unless told otherwise, and return it."""
    response = client.post("/matches", json={"deck": "humans", **new_match})
    assert response.status_code == 201
    match: dict[str, Any] = response.json()
    return match


def play_first(client: TestClient, match: dict[str, Any]) -> dict[str, Any]:
    """Play the first legal action in the match's view, and return the answer."""
    move = {"version": match["version"], "action": match["view"]["legal_actions"][0]}
    response = client.post(f"/matches/{match['id']}/actions", json=move)
    assert response.status_code == 200
    answer: dict[str, Any] = response.json()
    return answer


def test_without_a_level_the_baseline_ai_plays(
    client: TestClient, calls: list[Call]
) -> None:
    match = start(client)
    play_first(client, match)

    assert calls == []


@pytest.mark.parametrize(
    ("level", "samples"),
    [("normal", montecarlo.NORMAL_SAMPLES), ("hard", montecarlo.HARD_SAMPLES)],
)
def test_at_normal_and_hard_the_monte_carlo_ai_plays(
    client: TestClient, calls: list[Call], level: str, samples: int
) -> None:
    start(client, level=level)

    # The AI started: each of its decisions guesses with a seed of its own,
    # from the request's.
    assert calls
    assert {call.samples for call in calls} == {samples}
    assert [call.seed for call in calls] == [AI_SEED + n for n in range(len(calls))]


def test_the_ai_guesses_from_the_factions_own_decks(
    client: TestClient, calls: list[Call]
) -> None:
    start(client, level="normal")

    # By player index: the player's, then the AI's.
    assert calls[0].decks == (load_deck("humans").cards, load_deck("robots").cards)


def test_the_ai_plays_its_later_moves_at_the_matchs_level(
    client: TestClient, calls: list[Call]
) -> None:
    match = start(client, level="hard")
    calls.clear()

    # The player's redraw comes first: the AI answers once it ends.
    while not calls:
        match = play_first(client, match)

    assert not match["view"]["match_over"]
    assert {call.samples for call in calls} == {montecarlo.HARD_SAMPLES}


def test_a_guess_never_comes_from_a_deck_the_player_built(
    client: TestClient, calls: list[Call]
) -> None:
    # 22 units of the Humans, none of them a Plane: not the faction's own.
    copies = {"human": 5, "soldier": 3, "sniper": 3, "informant": 3, "medic": 3}
    copies |= {"smart-guy": 3, "prime-minister": 1, "president": 1}
    assert client.post("/accounts", json=RUI).status_code == 201
    deck = client.post(
        "/my-decks", json={"name": "No planes", "deck": "humans", "copies": copies}
    ).json()

    start(client, deck=None, my_deck=deck["id"], level="normal")

    # The AI can't know the deck: it guesses the faction's own.
    assert calls[0].decks[0] == load_deck("humans").cards


def test_the_list_of_matches_says_each_ones_level(client: TestClient) -> None:
    assert client.post("/accounts", json=RUI).status_code == 201
    easy = start(client)
    hard = start(client, level="hard")

    listed = client.get("/matches").json()["matches"]

    levels = {match["id"]: match["level"] for match in listed}
    assert levels == {easy["id"]: "easy", hard["id"]: "hard"}


@pytest.mark.parametrize("level", ["Hard", "expert", "", 2, None])
def test_an_unknown_level_is_turned_down(client: TestClient, level: object) -> None:
    response = client.post("/matches", json={"deck": "humans", "level": level})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_a_whole_match_can_be_played_at_normal(client: TestClient) -> None:
    match = start(client, level="normal")
    while not match["view"]["match_over"]:
        match = play_first(client, match)

    assert len(match["rounds"]) >= 2


def test_the_ais_seeds_are_big_random_and_not_the_matchs() -> None:
    seeds = {new_ai_seed() for _ in range(100)}

    assert len(seeds) == 100
    assert all(0 <= seed < 2**63 for seed in seeds)
    # As for new_seed: all 100 below 2**62 happens once in 2**100.
    assert max(seeds) >= 2**62
