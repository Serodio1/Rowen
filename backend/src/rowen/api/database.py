"""Where the web API keeps its matches and accounts in PostgreSQL.

There they survive a restart.

Each match is a row of the ``matches`` table, as ``rowen.api.store`` describes
it: the ids of the two decks, the seed, every action played so far and the
version. The actions are a JSON list, each one in the shape the API sends it
(``schemas.Action``), so the database holds no Python objects. Each account is
a row of the ``accounts`` table and each session one of ``sessions``, as
``rowen.api.accounts`` describes them.

The tables are made by the migrations in ``backend/migrations`` (Alembic), never
by this module: the rows' classes only say what the tables look like, and a
test checks that the migrations make the same tables, as ``alembic check``
does.
That check sees columns and their types, but not everything: not a CHECK
constraint, for one, which its own test covers.

SQLAlchemy keeps a few connections open and lends one to each request, so a
request doesn't wait for a new connection (a pool). A connection that the
database closed meanwhile, as a database that sleeps when idle does, is found
before it is lent (``pool_pre_ping``).
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Engine,
    ForeignKey,
    LargeBinary,
    String,
    delete,
    func,
    select,
    update,
)
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    joinedload,
    mapped_column,
    relationship,
)

from rowen.api.accounts import StoredAccount, StoredSession
from rowen.api.schemas import Action as ActionJson
from rowen.api.schemas import from_action, to_action
from rowen.api.store import FIRST_VERSION, StoredMatch
from rowen.engine.public import Action

# Turns a list of actions into JSON and back, checking each one's shape.
_ACTIONS = TypeAdapter(tuple[ActionJson, ...])


class Base(DeclarativeBase):
    """What every table here has in common: Alembic finds them through it."""


class MatchRow(Base):
    """A match, as a row of the ``matches`` table."""

    __tablename__ = "matches"
    # Seeds have 63 bits, so they fit a BIGINT, which has a sign
    # (rowen.api.app.SEED_BITS). A negative one would be a bug.
    __table_args__ = (CheckConstraint("seed >= 0", name="seed_not_negative"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    player_deck: Mapped[str] = mapped_column(String)
    ai_deck: Mapped[str] = mapped_column(String)
    seed: Mapped[int] = mapped_column(BigInteger)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    version: Mapped[int]
    # When the match started and when it was last played: for the database's
    # own upkeep, such as deleting matches left alone for long.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AccountRow(Base):
    """An account, as a row of the ``accounts`` table."""

    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SessionRow(Base):
    """A session, as a row of the ``sessions`` table.

    Deleting an account deletes its sessions (``ondelete``).
    """

    __tablename__ = "sessions"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    account: Mapped[AccountRow] = relationship()


# How long a request waits to connect to the database, and then for a free
# connection, in seconds. Without a limit, a database that can't be reached
# (rather than one that refuses) holds each request for minutes, until every
# thread of the server waits, and even GET /decks, the health check, gets no
# answer. Neon wakes up in about half a second, well within it.
CONNECT_TIMEOUT = 5
POOL_TIMEOUT = 10


def create_engine(url: str) -> Engine:
    """Return the connections to the database at ``url``, through psycopg.

    ``url`` is like ``postgresql+psycopg://user:password@host/database``.

    When a statement fails, SQLAlchemy's error holds the statement's values,
    and the error goes to the server's log: ``hide_parameters`` leaves them
    out, since they include the seed of a match, which must stay secret.
    """
    return _create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        pool_timeout=POOL_TIMEOUT,
        connect_args={"connect_timeout": CONNECT_TIMEOUT},
    )


class PostgresMatchStore:
    """The matches being played, each under its id, in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        """Make a store that keeps its matches in a database.

        Args:
            engine: The connections to the database, from ``create_engine``.
        """
        self._engine = engine

    def create(
        self, decks: tuple[str, str], seed: int, actions: tuple[Action, ...]
    ) -> StoredMatch:
        """Keep a new match, at its first version, and return it."""
        player_deck, ai_deck = decks
        row = MatchRow(
            id=uuid4(),
            player_deck=player_deck,
            ai_deck=ai_deck,
            seed=seed,
            actions=_to_json(actions),
            version=FIRST_VERSION,
        )
        with Session(self._engine) as session, session.begin():
            session.add(row)
            session.flush()
            return _stored(row)

    def get(self, match_id: UUID) -> StoredMatch | None:
        """Return a match, or None if there is no match with that id."""
        with Session(self._engine) as session:
            row = session.get(MatchRow, match_id)
            return None if row is None else _stored(row)

    def add_actions(
        self, match_id: UUID, version: int, actions: tuple[Action, ...]
    ) -> StoredMatch | None:
        """Add actions to a match, but only if it is still at ``version``.

        One statement does it all, in the database: it finds the match only
        if it is at ``version``, adds the actions after the others (``||``
        joins two JSON lists) and takes it to the next version. Two requests
        can't both do it, since the second finds the match at another version.
        """
        statement = (
            update(MatchRow)
            .where(MatchRow.id == match_id, MatchRow.version == version)
            .values(
                actions=MatchRow.actions.op("||")(_to_json(actions)),
                version=MatchRow.version + 1,
                updated_at=func.now(),
            )
            .returning(MatchRow)
        )
        with Session(self._engine) as session, session.begin():
            row = session.scalars(statement).one_or_none()
            return None if row is None else _stored(row)


def _to_json(actions: tuple[Action, ...]) -> list[dict[str, Any]]:
    """Return actions as a JSON list, each one in the shape the API sends it."""
    json: list[dict[str, Any]] = _ACTIONS.dump_python(
        tuple(from_action(action) for action in actions), mode="json"
    )
    return json


def _stored(row: MatchRow) -> StoredMatch:
    """Return a row as the store gives a match."""
    return StoredMatch(
        id=row.id,
        decks=(row.player_deck, row.ai_deck),
        seed=row.seed,
        actions=tuple(
            to_action(action) for action in _ACTIONS.validate_python(row.actions)
        ),
        version=row.version,
    )


class PostgresAccountStore:
    """The accounts and their sessions, in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        """Make a store that keeps its accounts in a database.

        Args:
            engine: The connections to the database, from ``create_engine``.
        """
        self._engine = engine

    def create_account(self, username: str, password_hash: str) -> StoredAccount | None:
        """Keep a new account and return it, or None if the username is taken.

        If another account has the username, the database adds no row
        (``ON CONFLICT DO NOTHING``) and returns none, even when two requests
        ask for it at the same time.
        """
        statement = (
            insert(AccountRow)
            .values(id=uuid4(), username=username, password_hash=password_hash)
            .on_conflict_do_nothing(index_elements=[AccountRow.username])
            .returning(AccountRow)
        )
        with Session(self._engine) as session, session.begin():
            row = session.scalars(statement).one_or_none()
            return None if row is None else _account(row)

    def find_account(self, username: str) -> StoredAccount | None:
        """Return the account with this username, or None if there is none."""
        statement = select(AccountRow).where(AccountRow.username == username)
        with Session(self._engine) as session:
            row = session.scalars(statement).one_or_none()
            return None if row is None else _account(row)

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
        expired = delete(SessionRow).where(
            SessionRow.account_id == account.id, SessionRow.expires_at <= now
        )
        with Session(self._engine) as session, session.begin():
            session.execute(expired)
            session.add(
                SessionRow(
                    token_hash=token_hash, account_id=account.id, expires_at=expires_at
                )
            )

    def find_session(self, token_hash: bytes, now: datetime) -> StoredSession | None:
        """Return the session with this token's hash, or None.

        None also if the session expired before ``now``. One query reads the
        session and its account (``joinedload``).
        """
        statement = (
            select(SessionRow)
            .where(SessionRow.token_hash == token_hash, SessionRow.expires_at > now)
            .options(joinedload(SessionRow.account))
        )
        with Session(self._engine) as session:
            row = session.scalars(statement).one_or_none()
            if row is None:
                return None
            return StoredSession(
                token_hash=row.token_hash,
                account=_account(row.account),
                expires_at=row.expires_at,
            )

    def renew_session(self, token_hash: bytes, expires_at: datetime) -> None:
        """Make a session last until ``expires_at``; nothing if there is none."""
        statement = (
            update(SessionRow)
            .where(SessionRow.token_hash == token_hash)
            .values(expires_at=expires_at)
        )
        with Session(self._engine) as session, session.begin():
            session.execute(statement)

    def delete_session(self, token_hash: bytes) -> None:
        """Delete a session, as logging out does; nothing if there is none."""
        statement = delete(SessionRow).where(SessionRow.token_hash == token_hash)
        with Session(self._engine) as session, session.begin():
            session.execute(statement)


def _account(row: AccountRow) -> StoredAccount:
    """Return a row as the store gives an account."""
    return StoredAccount(
        id=row.id, username=row.username, password_hash=row.password_hash
    )
