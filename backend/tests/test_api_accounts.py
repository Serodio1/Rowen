"""Tests for where the web API keeps its accounts and their sessions.

They run against both stores, in memory and in PostgreSQL (tests/conftest.py),
so the API can count on the same behaviour from each.
"""

import threading
from datetime import UTC, datetime, timedelta

from rowen.api.accounts import AccountStore, StoredAccount, StoredSession

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
LATER = NOW + timedelta(days=30)


def create(store: AccountStore, username: str = "rui") -> StoredAccount:
    """Keep a new account, which must not be there yet, and return it."""
    account = store.create_account(username, "hash of " + username)
    assert account is not None
    return account


def test_an_account_is_found_by_its_username(any_accounts: AccountStore) -> None:
    store = any_accounts

    account = store.create_account("rui", "a hash")

    assert account is not None
    assert account.username == "rui"
    assert account.password_hash == "a hash"
    assert store.find_account("rui") == account


def test_there_is_no_account_with_an_unknown_username(
    any_accounts: AccountStore,
) -> None:
    store = any_accounts
    create(store, "rui")

    assert store.find_account("ana") is None


def test_a_username_is_taken_once(any_accounts: AccountStore) -> None:
    store = any_accounts
    first = create(store, "rui")

    assert store.create_account("rui", "another hash") is None
    assert store.find_account("rui") == first


def test_of_two_accounts_with_one_username_at_once_only_one_is_kept(
    any_accounts: AccountStore,
) -> None:
    store = any_accounts
    results: list[StoredAccount | None] = []
    threads = [
        threading.Thread(
            target=lambda: results.append(store.create_account("rui", "a hash"))
        )
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    kept = [result for result in results if result is not None]
    assert len(results) == 8
    assert len(kept) == 1
    assert store.find_account("rui") == kept[0]


def test_each_account_gets_an_id_of_its_own(any_accounts: AccountStore) -> None:
    store = any_accounts

    ids = {create(store, f"player{n}").id for n in range(20)}

    assert len(ids) == 20


def test_a_session_is_found_until_it_expires(any_accounts: AccountStore) -> None:
    store = any_accounts
    account = create(store)

    store.create_session(account, b"token", LATER, NOW)

    session = StoredSession(token_hash=b"token", account=account, expires_at=LATER)
    assert store.find_session(b"token", NOW) == session
    assert store.find_session(b"token", LATER - timedelta(seconds=1)) == session
    assert store.find_session(b"token", LATER) is None


def test_there_is_no_session_with_an_unknown_token(
    any_accounts: AccountStore,
) -> None:
    store = any_accounts
    store.create_session(create(store), b"token", LATER, NOW)

    assert store.find_session(b"other", NOW) is None


def test_a_renewed_session_lasts_longer(any_accounts: AccountStore) -> None:
    store = any_accounts
    store.create_session(create(store), b"token", LATER, NOW)

    store.renew_session(b"token", LATER + timedelta(days=1))

    assert store.find_session(b"token", LATER) is not None


def test_renewing_or_deleting_an_unknown_session_does_nothing(
    any_accounts: AccountStore,
) -> None:
    store = any_accounts
    store.create_session(create(store), b"token", LATER, NOW)

    store.renew_session(b"other", LATER + timedelta(days=1))
    store.delete_session(b"other")

    assert store.find_session(b"other", NOW) is None
    assert store.find_session(b"token", NOW) is not None


def test_a_deleted_session_is_gone(any_accounts: AccountStore) -> None:
    store = any_accounts
    account = create(store)
    store.create_session(account, b"token", LATER, NOW)
    store.create_session(account, b"other", LATER, NOW)

    store.delete_session(b"token")

    assert store.find_session(b"token", NOW) is None
    assert store.find_session(b"other", NOW) is not None


def test_a_new_session_deletes_the_accounts_expired_ones(
    any_accounts: AccountStore,
) -> None:
    store = any_accounts
    rui = create(store, "rui")
    ana = create(store, "ana")
    store.create_session(rui, b"expired", NOW, NOW - timedelta(days=30))
    store.create_session(rui, b"current", LATER, NOW - timedelta(days=30))
    store.create_session(ana, b"ana's", NOW, NOW - timedelta(days=30))

    store.create_session(rui, b"new", LATER, NOW)

    # Seen from before they expired: only the one deleted is gone.
    before = NOW - timedelta(days=1)
    assert store.find_session(b"expired", before) is None
    assert store.find_session(b"current", before) is not None
    assert store.find_session(b"ana's", before) is not None
    assert store.find_session(b"new", before) is not None
