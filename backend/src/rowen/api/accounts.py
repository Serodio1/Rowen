"""Where the web API keeps its accounts and their sessions: in memory, or in PostgreSQL.

As with the matches (``rowen.api.store``), ``AccountStore`` is what the API
needs from a store, and there are two: ``MemoryAccountStore``, here, and
``PostgresAccountStore`` (``rowen.api.database``). The same tests run against
both (``tests/test_api_accounts.py``).

An account is a username and the hash of its password (``rowen.api.passwords``),
never the password itself. Usernames are unique.

A session is how the server knows who sends a request (ADR 0014). When a
player logs in, the API makes a random secret, the session's token, and sends
it in a cookie; the browser sends it back with each request. The store keeps
only the token's SHA-256 hash, with whose account it is and when it expires:
so whoever reads the database can't use the sessions in it. Logging out
deletes the session, so its token is worth nothing from then on.

The store in memory is for development, when the server runs without a
database: its accounts are lost when the server stops.
"""

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoredAccount:
    """An account as the store keeps it.

    Attributes:
        id: The account's id.
        username: The name the player logs in with.
        password_hash: The hash of the password, from ``rowen.api.passwords``.
    """

    id: UUID
    username: str
    password_hash: str


@dataclass(frozen=True)
class StoredSession:
    """A session as the store keeps it.

    Attributes:
        token_hash: The SHA-256 hash of the session's token.
        account: The account that logged in.
        expires_at: When the session stops working, unless it is renewed.
    """

    token_hash: bytes
    account: StoredAccount
    expires_at: datetime


class AccountStore(Protocol):
    """What the API needs from a store of accounts: what each store does."""

    def create_account(self, username: str, password_hash: str) -> StoredAccount | None:
        """Keep a new account and return it, or None if the username is taken."""
        ...

    def find_account(self, username: str) -> StoredAccount | None:
        """Return the account with this username, or None if there is none."""
        ...

    def create_session(
        self,
        account: StoredAccount,
        token_hash: bytes,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        """Keep a new session of an account, until ``expires_at``.

        The account's sessions that expired before ``now`` are deleted, so
        they don't pile up.
        """
        ...

    def find_session(self, token_hash: bytes, now: datetime) -> StoredSession | None:
        """Return the session with this token's hash, or None.

        None also if the session expired before ``now``.
        """
        ...

    def renew_session(self, token_hash: bytes, expires_at: datetime) -> None:
        """Make a session last until ``expires_at``; nothing if there is none."""
        ...

    def delete_session(self, token_hash: bytes) -> None:
        """Delete a session, as logging out does; nothing if there is none."""
        ...


class MemoryAccountStore:
    """The accounts and their sessions, in the server's memory.

    As in ``MemoryMatchStore``, a lock lets one thread in at a time.
    """

    def __init__(self) -> None:
        """Make an empty store."""
        # Each account under its username.
        self._accounts: dict[str, StoredAccount] = {}
        # Each session under its token's hash.
        self._sessions: dict[bytes, StoredSession] = {}
        self._lock = threading.Lock()

    def create_account(self, username: str, password_hash: str) -> StoredAccount | None:
        """Keep a new account and return it, or None if the username is taken."""
        account = StoredAccount(
            id=uuid.uuid4(), username=username, password_hash=password_hash
        )
        with self._lock:
            if username in self._accounts:
                return None
            self._accounts[username] = account
        return account

    def find_account(self, username: str) -> StoredAccount | None:
        """Return the account with this username, or None if there is none."""
        with self._lock:
            return self._accounts.get(username)

    def create_session(
        self,
        account: StoredAccount,
        token_hash: bytes,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        """Keep a new session of an account, until ``expires_at``.

        The account's sessions that expired before ``now`` are deleted.
        """
        with self._lock:
            self._sessions = {
                key: session
                for key, session in self._sessions.items()
                if session.account.id != account.id or session.expires_at > now
            }
            self._sessions[token_hash] = StoredSession(
                token_hash=token_hash, account=account, expires_at=expires_at
            )

    def find_session(self, token_hash: bytes, now: datetime) -> StoredSession | None:
        """Return the session with this token's hash, or None.

        None also if the session expired before ``now``.
        """
        with self._lock:
            session = self._sessions.get(token_hash)
        if session is None or session.expires_at <= now:
            return None
        return session

    def renew_session(self, token_hash: bytes, expires_at: datetime) -> None:
        """Make a session last until ``expires_at``; nothing if there is none."""
        with self._lock:
            session = self._sessions.get(token_hash)
            if session is not None:
                self._sessions[token_hash] = replace(session, expires_at=expires_at)

    def delete_session(self, token_hash: bytes) -> None:
        """Delete a session, as logging out does; nothing if there is none."""
        with self._lock:
            self._sessions.pop(token_hash, None)
