"""Tests for where the web API keeps its matches.

The tests that take ``any_store`` run against both stores, in memory and in
PostgreSQL (tests/conftest.py), so the API can count on the same behaviour from
each. The others are about the store in memory only.
"""

import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import UUID, uuid4

import pytest

from rowen.api.accounts import AccountStore
from rowen.api.store import (
    FIRST_VERSION,
    MAX_MATCHES,
    DeckStats,
    MatchResult,
    MatchStore,
    MatchSummary,
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
    calls: dict[str, Callable[[], object]] = {
        "create": partial(store.create, DECKS, 0, SOME_ACTIONS, owner=None, now=NOW),
        "get": partial(store.get, match.id),
        "add_actions": partial(store.add_actions, match.id, match.version, (Pass(),)),
        "list_matches": partial(store.list_matches, owner, 20),
        "stats": partial(store.stats, owner),
    }
    thread = threading.Thread(target=calls[method])

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


# Matches with an owner. In PostgreSQL the owner must be an account, so these
# tests make one in the store of accounts that goes with the store of matches.

WON = MatchResult(outcome="won", rounds=((30, 12), (25, 40), (18, 9)), ended_at=NOW)


def owner_of(stores: tuple[MatchStore, AccountStore], username: str = "rui") -> UUID:
    """Make an account and return its id."""
    _, accounts = stores
    account = accounts.create_account(username, "a hash")
    assert account is not None
    return account.id


def start(
    store: MatchStore, owner: UUID | None, now: datetime = NOW, deck: str = "humans"
) -> StoredMatch:
    """Keep a new match of an owner's, at a time, and return it."""
    return store.create((deck, "robots"), 0, SOME_ACTIONS, owner=owner, now=now)


def end(store: MatchStore, match: StoredMatch, result: MatchResult = WON) -> None:
    """Add the actions that end a match, with its result."""
    assert store.add_actions(match.id, match.version, (Pass(),), result) is not None


def ids(matches: tuple[MatchSummary, ...]) -> list[UUID]:
    return [match.id for match in matches]


def test_a_match_keeps_its_owner(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    owner = owner_of(any_stores)

    match = start(store, owner)

    assert match.owner == owner
    assert store.get(match.id) == match


def test_the_actions_that_end_a_match_keep_its_result(
    any_store: MatchStore,
) -> None:
    store = any_store
    old = create(store)

    new = store.add_actions(old.id, old.version, (Pass(),), WON)

    assert new is not None
    assert new.result == WON
    assert store.get(old.id) == new


def test_an_owners_matches_are_listed_newest_first_with_their_results(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    owner = owner_of(any_stores)
    old = start(store, owner, NOW)
    new = start(store, owner, NOW + timedelta(minutes=1), deck="robots")
    end(store, old)

    listed = store.list_matches(owner, 10)

    assert listed == (
        MatchSummary(
            id=new.id,
            decks=("robots", "robots"),
            created_at=new.created_at,
            result=None,
        ),
        MatchSummary(id=old.id, decks=DECKS, created_at=old.created_at, result=WON),
    )


def test_only_the_owners_matches_are_listed(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    rui = owner_of(any_stores, "rui")
    ana = owner_of(any_stores, "ana")
    ruis = start(store, rui)
    start(store, ana)
    create(store)

    assert ids(store.list_matches(rui, 10)) == [ruis.id]
    assert store.list_matches(uuid4(), 10) == ()


def test_matches_are_listed_a_page_at_a_time(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    owner = owner_of(any_stores)
    matches = [start(store, owner, NOW + timedelta(minutes=n)) for n in range(5)]
    newest_first = [match.id for match in reversed(matches)]

    first = store.list_matches(owner, 2)
    second = store.list_matches(owner, 2, before=first[-1].id)
    third = store.list_matches(owner, 2, before=second[-1].id)

    assert ids(first) + ids(second) + ids(third) == newest_first
    assert len(third) == 1


def test_matches_that_started_at_the_same_time_are_each_on_one_page(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    # Then their ids put them in order, the same in both stores.
    store, _ = any_stores
    owner = owner_of(any_stores)
    matches = [start(store, owner) for _ in range(6)]

    pages = [store.list_matches(owner, 4)]
    pages.append(store.list_matches(owner, 4, before=pages[0][-1].id))

    listed = [match_id for page in pages for match_id in ids(page)]
    assert listed == sorted((match.id for match in matches), reverse=True)


def test_a_match_started_meanwhile_doesnt_move_the_next_page(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    owner = owner_of(any_stores)
    matches = [start(store, owner, NOW + timedelta(minutes=n)) for n in range(4)]
    first = store.list_matches(owner, 2)

    start(store, owner, NOW + timedelta(hours=1))
    second = store.list_matches(owner, 2, before=first[-1].id)

    assert ids(second) == [matches[1].id, matches[0].id]


def test_no_page_comes_after_a_match_that_isnt_the_owners(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    rui = owner_of(any_stores, "rui")
    ana = owner_of(any_stores, "ana")
    start(store, rui, NOW - timedelta(minutes=1))
    anas = start(store, ana)

    assert store.list_matches(rui, 10, before=anas.id) == ()
    assert store.list_matches(rui, 10, before=uuid4()) == ()


def test_stats_count_how_the_owners_matches_ended_with_each_deck(
    any_stores: tuple[MatchStore, AccountStore],
) -> None:
    store, _ = any_stores
    rui = owner_of(any_stores, "rui")
    ana = owner_of(any_stores, "ana")
    lost = MatchResult(outcome="lost", rounds=((1, 2), (3, 4)), ended_at=NOW)
    drawn = MatchResult(outcome="drawn", rounds=((5, 5), (6, 6)), ended_at=NOW)
    for deck, result in [
        ("robots", WON),
        ("humans", WON),
        ("humans", WON),
        ("humans", lost),
        ("humans", drawn),
    ]:
        end(store, start(store, rui, deck=deck), result)
    # Neither a match that goes on nor another owner's counts.
    start(store, rui, deck="humans")
    end(store, start(store, ana, deck="humans"))

    assert store.stats(rui) == (
        DeckStats(deck="humans", won=2, lost=1, drawn=1),
        DeckStats(deck="robots", won=1, lost=0, drawn=0),
    )
    assert store.stats(uuid4()) == ()
