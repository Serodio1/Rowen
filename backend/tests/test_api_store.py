"""Tests for where the web API keeps its matches."""

import sys
import threading
from uuid import uuid4

import pytest

from rowen.api.store import MAX_MATCHES, MatchStore
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


def test_a_store_holds_max_matches_by_default() -> None:
    store = MatchStore()
    state = new_state()
    ids = [store.create(state) for _ in range(MAX_MATCHES + 1)]

    assert store.get(ids[0]) is None
    assert all(store.get(match_id) is state for match_id in ids[1:])


def test_a_match_is_replaced_if_it_is_still_the_old_one() -> None:
    store = MatchStore()
    old, new = new_state(0), new_state(1)
    match_id = store.create(old)

    replaced = store.replace(match_id, old, new)

    assert replaced
    assert store.get(match_id) is new


def test_a_match_another_request_replaced_first_is_not_replaced() -> None:
    # Two requests got the same match at once. The first one has already kept
    # its result.
    store = MatchStore()
    old, first, second = new_state(0), new_state(1), new_state(2)
    match_id = store.create(old)
    store.replace(match_id, old, first)

    replaced = store.replace(match_id, old, second)

    assert not replaced
    assert store.get(match_id) is first


def test_an_equal_state_is_not_the_old_one() -> None:
    # The same seed makes an equal state, but not the one the store holds.
    store = MatchStore()
    old, equal, new = new_state(0), new_state(0), new_state(1)
    assert equal == old
    match_id = store.create(old)

    replaced = store.replace(match_id, equal, new)

    assert not replaced
    assert store.get(match_id) is old


def test_an_unknown_match_is_not_replaced() -> None:
    store = MatchStore()
    old, new = new_state(0), new_state(1)
    store.create(old)
    match_id = uuid4()

    replaced = store.replace(match_id, old, new)

    assert not replaced
    assert store.get(match_id) is None


def test_a_match_pushed_out_is_not_replaced() -> None:
    # The match was pushed out while its request was being played.
    store = MatchStore(max_matches=1)
    old, other, new = new_state(0), new_state(1), new_state(2)
    match_id = store.create(old)
    store.create(other)

    replaced = store.replace(match_id, old, new)

    assert not replaced
    assert store.get(match_id) is None


def test_a_match_replaced_counts_as_used() -> None:
    store = MatchStore(max_matches=2)
    states = [new_state(seed) for seed in range(4)]
    first = store.create(states[0])
    second = store.create(states[1])
    # Playing the first match makes the second one the least recently used.
    store.replace(first, states[0], states[2])

    store.create(states[3])

    assert store.get(second) is None
    assert store.get(first) is states[2]


@pytest.mark.parametrize("method", ["create", "get", "replace"])
def test_a_thread_waits_while_another_one_uses_the_store(method: str) -> None:
    store = MatchStore()
    state = new_state()
    match_id = store.create(state)
    arguments = {
        "create": (state,),
        "get": (match_id,),
        "replace": (match_id, state, new_state(1)),
    }[method]
    thread = threading.Thread(target=getattr(store, method), args=arguments)

    # While the test holds the lock, the other thread can't get in.
    with store._lock:
        thread.start()
        thread.join(timeout=0.1)
        waited = thread.is_alive()
    thread.join()

    assert waited


def test_many_threads_can_use_the_store_at_once() -> None:
    # Threads take turns far more often than usual, so that without the lock
    # one thread would soon push out a match that another one is reading, for
    # example in ``get``, between finding the match and moving it to the end.
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
