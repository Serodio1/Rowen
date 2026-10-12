"""Tests for where the web API keeps its matches."""

import sys
import threading
from uuid import uuid4

from rowen.api.store import MatchStore
from rowen.data import deck_ids, load_deck
from rowen.engine.public import GameState, start_match

DECKS = tuple(load_deck(deck_id) for deck_id in deck_ids())


def new_state(seed: int = 0) -> GameState:
    """Return the state of a new match."""
    return start_match((DECKS[0], DECKS[1]), seed=seed)


def test_a_match_is_kept_under_its_id() -> None:
    store = MatchStore()
    state = new_state()

    match_id = store.create(state)

    assert store.get(match_id) is state


def test_there_is_no_match_under_an_unknown_id() -> None:
    store = MatchStore()
    store.create(new_state())

    assert store.get(uuid4()) is None


def test_each_match_gets_a_random_id_of_its_own() -> None:
    store = MatchStore()
    state = new_state()

    ids = {store.create(state) for _ in range(100)}

    assert len(ids) == 100
    # Version 4 is the kind of UUID made of random bits.
    assert {match_id.version for match_id in ids} == {4}


def test_a_full_store_pushes_out_the_match_left_unused_the_longest() -> None:
    store = MatchStore(max_matches=2)
    states = [new_state(seed) for seed in range(3)]
    first = store.create(states[0])
    second = store.create(states[1])
    # Seeing the first match again makes the second one the least recently used.
    store.get(first)

    third = store.create(states[2])

    assert store.get(second) is None
    assert store.get(first) is states[0]
    assert store.get(third) is states[2]


def test_many_threads_can_use_the_store_at_once() -> None:
    # Threads take turns far more often than usual, so that without the lock
    # one thread would soon push out a match that another one is reading.
    store = MatchStore(max_matches=4)
    state = new_state()
    errors: list[Exception] = []

    def use_store() -> None:
        try:
            for _ in range(2000):
                store.get(store.create(state))
        # An error in a thread doesn't fail the test by itself, so it is kept.
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=use_store) for _ in range(8)]
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(interval)

    assert errors == []
