"""Tests for where the web API keeps its matches."""

import sys
import threading
from uuid import uuid4

import pytest

from rowen.api.store import FIRST_VERSION, MAX_MATCHES, MatchStore, StoredMatch
from rowen.data import deck_ids, load_deck
from rowen.engine.public import GameState, start_match

DECKS = tuple(load_deck(deck_id) for deck_id in deck_ids())


def new_state(seed: int = 0) -> GameState:
    """Return the state of a new match."""
    return start_match((DECKS[0], DECKS[1]), seed=seed)


def test_a_match_is_kept_under_its_id_at_the_first_version() -> None:
    store = MatchStore()
    state = new_state()

    match = store.create(state)

    assert match.state is state
    assert match.version == FIRST_VERSION
    assert store.get(match.id) == match


def test_there_is_no_match_under_an_unknown_id() -> None:
    store = MatchStore()
    store.create(new_state())

    assert store.get(uuid4()) is None


def test_each_match_gets_a_random_id_of_its_own() -> None:
    store = MatchStore()
    state = new_state()

    ids = {store.create(state).id for _ in range(100)}

    assert len(ids) == 100
    # Version 4 is the kind of UUID made of random bits.
    assert {match_id.version for match_id in ids} == {4}


def test_a_full_store_pushes_out_the_match_left_unused_the_longest() -> None:
    store = MatchStore(max_matches=2)
    first = store.create(new_state(0))
    second = store.create(new_state(1))
    # Seeing the first match again makes the second one the least recently used.
    store.get(first.id)

    third = store.create(new_state(2))

    assert store.get(second.id) is None
    assert store.get(first.id) == first
    assert store.get(third.id) == third


def test_a_store_holds_max_matches_by_default() -> None:
    store = MatchStore()
    state = new_state()
    matches = [store.create(state) for _ in range(MAX_MATCHES + 1)]

    assert store.get(matches[0].id) is None
    assert all(store.get(match.id) == match for match in matches[1:])


def test_a_match_still_at_the_version_is_replaced_at_the_next_one() -> None:
    store = MatchStore()
    old = store.create(new_state(0))
    state = new_state(1)

    new = store.replace(old.id, old.version, state)

    assert new == StoredMatch(id=old.id, state=state, version=old.version + 1)
    assert store.get(old.id) == new


def test_each_replacement_takes_the_match_to_the_next_version() -> None:
    store = MatchStore()
    match = store.create(new_state(0))

    for seed in range(1, 4):
        replaced = store.replace(match.id, match.version, new_state(seed))
        assert replaced is not None
        match = replaced

    assert match.version == FIRST_VERSION + 3


@pytest.mark.parametrize("offset", [-1, 1])
def test_a_match_at_another_version_is_not_replaced(offset: int) -> None:
    # The move was chosen from an older view, or its version is made up.
    store = MatchStore()
    old = store.create(new_state(0))
    kept = store.replace(old.id, old.version, new_state(1))
    assert kept is not None

    replaced = store.replace(old.id, kept.version + offset, new_state(2))

    assert replaced is None
    assert store.get(old.id) == kept


def test_a_match_another_request_replaced_first_is_not_replaced() -> None:
    # Two requests got the same match at once. The first one has already kept
    # its result.
    store = MatchStore()
    old = store.create(new_state(0))
    first = store.replace(old.id, old.version, new_state(1))

    second = store.replace(old.id, old.version, new_state(2))

    assert second is None
    assert store.get(old.id) == first


def test_an_unknown_match_is_not_replaced() -> None:
    store = MatchStore()
    store.create(new_state(0))
    match_id = uuid4()

    replaced = store.replace(match_id, FIRST_VERSION, new_state(1))

    assert replaced is None
    assert store.get(match_id) is None


def test_a_match_pushed_out_is_not_replaced() -> None:
    # The match was pushed out while its request was being played.
    store = MatchStore(max_matches=1)
    old = store.create(new_state(0))
    store.create(new_state(1))

    replaced = store.replace(old.id, old.version, new_state(2))

    assert replaced is None
    assert store.get(old.id) is None


def test_a_match_replaced_counts_as_used() -> None:
    store = MatchStore(max_matches=2)
    first = store.create(new_state(0))
    second = store.create(new_state(1))
    # Playing the first match makes the second one the least recently used.
    played = store.replace(first.id, first.version, new_state(2))

    store.create(new_state(3))

    assert store.get(second.id) is None
    assert store.get(first.id) == played


@pytest.mark.parametrize("method", ["create", "get", "replace"])
def test_a_thread_waits_while_another_one_uses_the_store(method: str) -> None:
    store = MatchStore()
    state = new_state()
    match = store.create(state)
    arguments = {
        "create": (state,),
        "get": (match.id,),
        "replace": (match.id, match.version, new_state(1)),
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
                store.get(store.create(state).id)
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
