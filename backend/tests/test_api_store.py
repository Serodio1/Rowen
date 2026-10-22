"""Tests for where the web API keeps its matches.

The tests that take ``any_store`` run against both stores, in memory and in
PostgreSQL (tests/conftest.py), so the API can count on the same behaviour from
each. The others are about the store in memory only.
"""

import sys
import threading
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

import pytest

from rowen.api.store import (
    FIRST_VERSION,
    MAX_MATCHES,
    MatchStore,
    MemoryMatchStore,
    StoredMatch,
)
from rowen.engine.public import Action, EndRedraw, Pass, Redraw

# The store doesn't check the actions: the API does. These are just some.
DECKS = ("humans", "robots")
SOME_ACTIONS: tuple[Action, ...] = (Redraw(card="soldier"), EndRedraw())
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def create(store: MatchStore, seed: int = 0) -> StoredMatch:
    """Keep a new guest's match with the humans against the robots, and return it."""
    return store.create(DECKS, seed, SOME_ACTIONS, owner=None, now=NOW)


def test_a_match_is_kept_under_its_id_at_the_first_version(
    any_store: MatchStore,
) -> None:
    store = any_store

    match = store.create(DECKS, 12, SOME_ACTIONS, owner=None, now=NOW)

    assert match == StoredMatch(
        id=match.id,
        decks=DECKS,
        seed=12,
        actions=SOME_ACTIONS,
        version=FIRST_VERSION,
        owner=None,
        created_at=NOW,
        result=None,
    )
    assert store.get(match.id) == match


def test_there_is_no_match_under_an_unknown_id(any_store: MatchStore) -> None:
    store = any_store
    create(store)

    assert store.get(uuid4()) is None


def test_each_match_gets_a_random_id_of_its_own(any_store: MatchStore) -> None:
    store = any_store

    ids = {create(store).id for _ in range(100)}

    assert len(ids) == 100
    # Version 4 is the kind of UUID made of random bits.
    assert {match_id.version for match_id in ids} == {4}


def test_a_full_store_pushes_out_the_match_left_unused_the_longest() -> None:
    store = MemoryMatchStore(max_matches=2)
    first = create(store, 0)
    second = create(store, 1)
    # Seeing the first match again makes the second one the least recently used.
    store.get(first.id)

    third = create(store, 2)

    assert store.get(second.id) is None
    assert store.get(first.id) == first
    assert store.get(third.id) == third


def test_a_store_holds_max_matches_by_default() -> None:
    store = MemoryMatchStore()
    matches = [create(store) for _ in range(MAX_MATCHES + 1)]

    assert store.get(matches[0].id) is None
    assert all(store.get(match.id) == match for match in matches[1:])


def test_actions_are_added_after_the_others_at_the_next_version(
    any_store: MatchStore,
) -> None:
    store = any_store
    old = create(store, 7)

    new = store.add_actions(old.id, old.version, (Pass(),))

    assert new == StoredMatch(
        id=old.id,
        decks=DECKS,
        seed=7,
        actions=(*SOME_ACTIONS, Pass()),
        version=old.version + 1,
        owner=None,
        created_at=NOW,
        result=None,
    )
    assert store.get(old.id) == new


def test_each_time_actions_are_added_the_match_goes_to_the_next_version(
    any_store: MatchStore,
) -> None:
    store = any_store
    match = create(store)

    for _ in range(3):
        added = store.add_actions(match.id, match.version, (Pass(),))
        assert added is not None
        match = added

    assert match.version == FIRST_VERSION + 3
    assert match.actions == (*SOME_ACTIONS, Pass(), Pass(), Pass())


@pytest.mark.parametrize("offset", [-1, 1])
def test_no_actions_are_added_to_a_match_at_another_version(
    offset: int, any_store: MatchStore
) -> None:
    # The move was chosen from an older view, or its version is made up.
    store = any_store
    old = create(store)
    kept = store.add_actions(old.id, old.version, (Pass(),))
    assert kept is not None

    added = store.add_actions(old.id, kept.version + offset, (EndRedraw(),))

    assert added is None
    assert store.get(old.id) == kept


def test_no_actions_are_added_once_another_request_added_its_own(
    any_store: MatchStore,
) -> None:
    # Two requests got the same match at once. The first one has already kept
    # its actions.
    store = any_store
    old = create(store)
    first = store.add_actions(old.id, old.version, (Pass(),))

    second = store.add_actions(old.id, old.version, (EndRedraw(),))

    assert second is None
    assert store.get(old.id) == first


def test_no_actions_are_added_to_an_unknown_match(any_store: MatchStore) -> None:
    store = any_store
    create(store)
    match_id = uuid4()

    added = store.add_actions(match_id, FIRST_VERSION, (Pass(),))

    assert added is None
    assert store.get(match_id) is None


def test_no_actions_are_added_to_a_match_pushed_out() -> None:
    # The match was pushed out while its request was being played.
    store = MemoryMatchStore(max_matches=1)
    old = create(store, 0)
    create(store, 1)

    added = store.add_actions(old.id, old.version, (Pass(),))

    assert added is None
    assert store.get(old.id) is None


def test_a_match_played_counts_as_used() -> None:
    store = MemoryMatchStore(max_matches=2)
    first = create(store, 0)
    second = create(store, 1)
    # Playing the first match makes the second one the least recently used.
    played = store.add_actions(first.id, first.version, (Pass(),))

    create(store, 2)

    assert store.get(second.id) is None
    assert store.get(first.id) == played


@pytest.mark.parametrize(
    "method", ["create", "get", "add_actions", "list_matches", "stats"]
)
def test_a_thread_waits_while_another_one_uses_the_store(method: str) -> None:
    store = MemoryMatchStore()
    match = create(store)
    owner = uuid4()
    call = {
        "create": partial(store.create, DECKS, 0, SOME_ACTIONS, owner=None, now=NOW),
        "get": partial(store.get, match.id),
        "add_actions": partial(store.add_actions, match.id, match.version, (Pass(),)),
        "list_matches": partial(store.list_matches, owner, 20),
        "stats": partial(store.stats, owner),
    }[method]
    thread = threading.Thread(target=call)

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
    store = MemoryMatchStore(max_matches=4)
    errors: list[Exception] = []

    def use_store() -> None:
        try:
            for _ in range(2000):
                store.get(create(store).id)
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
