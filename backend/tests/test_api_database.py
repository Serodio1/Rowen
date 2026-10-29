"""Tests for the store in PostgreSQL, beyond those both stores share.

They run only when TEST_DATABASE_URL is set (tests/conftest.py).
"""

import threading
import time
import traceback
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from rowen.api.app import app, get_accounts, get_store, new_seed
from rowen.api.database import (
    PostgresAccountStore,
    PostgresDeckStore,
    PostgresMatchStore,
    create_engine,
)
from rowen.api.player_decks import MAX_DECKS, StoredDeck
from rowen.api.store import FIRST_VERSION, DeckCopy, MatchResult, StoredMatch
from rowen.engine.public import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlayScarecrow,
    PlaySpecial,
    PlayUnit,
    Redraw,
    Revive,
    Row,
)

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)

# A seed of 16 digits, which no error message holds by chance.
SECRET_SEED = 7_319_555_123_456_789

# One action of each kind. The store doesn't check them: the API does.
EVERY_KIND: tuple[Action, ...] = (
    Redraw(card="soldier"),
    EndRedraw(),
    PlayUnit(card="soldier", row=Row.MELEE),
    PlaySpecial(card="hoarfrost"),
    PlayHorn(card="war-horn", row=Row.SIEGE),
    PlayScarecrow(card="scarecrow", row=Row.RANGED, unit="sniper"),
    Revive(card="soldier", row=Row.MELEE),
    Pass(),
)


def test_every_kind_of_action_comes_back_as_it_was_kept(
    postgres_store: PostgresMatchStore,
) -> None:
    match = postgres_store.create(
        ("humans", "robots"), 1, EVERY_KIND[:4], owner=None, now=NOW
    )
    added = postgres_store.add_actions(match.id, match.version, EVERY_KIND[4:])

    assert added is not None
    assert added.actions == EVERY_KIND
    assert postgres_store.get(match.id) == added


@pytest.mark.parametrize("seed", [0, 2**63 - 1])
def test_seeds_of_63_bits_fit(postgres_store: PostgresMatchStore, seed: int) -> None:
    match = postgres_store.create(("humans", "robots"), seed, (), owner=None, now=NOW)

    stored = postgres_store.get(match.id)

    assert stored is not None
    assert stored.seed == seed


def test_the_database_turns_down_a_negative_seed(
    postgres_store: PostgresMatchStore,
) -> None:
    with pytest.raises(IntegrityError, match="seed_not_negative"):
        postgres_store.create(("humans", "robots"), -1, (), owner=None, now=NOW)


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        # An outcome the API never gives.
        (
            "outcome = 'lost badly', rounds = '[]', ended_at = now()",
            "outcome_is_known",
        ),
        # Only part of a result.
        ("outcome = 'won'", "result_is_whole"),
        ("rounds = '[]'", "result_is_whole"),
        ("ended_at = now()", "result_is_whole"),
        ("outcome = 'won', rounds = '[]'", "result_is_whole"),
        # Only part of a copy of the player's deck.
        ("player_deck_name = 'Mine'", "player_deck_copy_is_whole"),
        ("player_copies = '{}'", "player_deck_copy_is_whole"),
    ],
)
def test_the_database_turns_down_a_result_that_cant_be(
    postgres_store: PostgresMatchStore, database_url: str, change: str, constraint: str
) -> None:
    match = postgres_store.create(("humans", "robots"), 1, (), owner=None, now=NOW)

    engine = create_engine(database_url)
    try:
        with pytest.raises(IntegrityError, match=constraint), engine.begin() as c:
            c.execute(
                text(f"UPDATE matches SET {change} WHERE id = :id"), {"id": match.id}
            )
    finally:
        engine.dispose()


def test_deleting_an_account_leaves_its_matches_with_no_owner(
    postgres_store: PostgresMatchStore,
    postgres_accounts: PostgresAccountStore,
    database_url: str,
) -> None:
    account = postgres_accounts.create_account("rui", "a hash")
    assert account is not None
    match = postgres_store.create(
        ("humans", "robots"), 1, (), owner=account.id, now=NOW
    )

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM accounts WHERE id = :id"), {"id": account.id}
            )
    finally:
        engine.dispose()

    stored = postgres_store.get(match.id)
    assert stored is not None
    assert stored.owner is None


def test_a_match_outlives_the_store_that_kept_it(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # A new store, with connections of its own, as after a restart.
    match = postgres_store.create(
        ("humans", "robots"), 1, (Pass(),), owner=None, now=NOW
    )
    engine = create_engine(database_url)
    try:
        found = PostgresMatchStore(engine).get(match.id)
    finally:
        engine.dispose()

    assert found == match


def test_of_two_requests_at_once_only_one_adds_its_actions(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # Two requests chose a move from the same version, and both reach the
    # database while it is busy with the match. To be sure they meet there,
    # the test holds the match's row (FOR UPDATE) until both are waiting for
    # it, then lets them go. A store that read the version first and then
    # wrote the actions would keep both.
    match = postgres_store.create(("humans", "robots"), 1, (), owner=None, now=NOW)
    results: list[StoredMatch | None] = []

    def add(action: Action) -> None:
        results.append(postgres_store.add_actions(match.id, match.version, (action,)))

    threads = [
        threading.Thread(target=add, args=(action,)) for action in EVERY_KIND[:2]
    ]
    engine = create_engine(database_url)
    try:
        with engine.connect() as holder:
            holder.execute(
                text("SELECT 1 FROM matches WHERE id = :id FOR UPDATE"),
                {"id": match.id},
            )
            for thread in threads:
                thread.start()
            wait_until_waiting_for_a_lock(engine, 2)
            holder.rollback()
        for thread in threads:
            thread.join()
    finally:
        engine.dispose()

    kept = [result for result in results if result is not None]
    assert len(results) == 2
    assert len(kept) == 1
    assert kept[0].version == FIRST_VERSION + 1
    assert postgres_store.get(match.id) == kept[0]


def wait_until_waiting_for_a_lock(engine: Engine, count: int) -> None:
    """Wait until ``count`` connections to the database wait for a lock.

    Asked on a connection of its own, which sees each answer afresh
    (AUTOCOMMIT): within one transaction, PostgreSQL's statistics stay as they
    were when it began.
    """
    question = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE wait_event_type = 'Lock' AND datname = current_database()"
    )
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as asker:
        deadline = time.monotonic() + 10
        while asker.execute(question).scalar_one() < count:
            assert time.monotonic() < deadline, "the requests never waited"
            time.sleep(0.01)


def test_a_connection_the_database_closed_is_replaced(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # As when the database sleeps (Neon does after 5 idle minutes) or
    # restarts: the store's connections are closed under it.
    match = postgres_store.create(("humans", "robots"), 1, (), owner=None, now=NOW)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE datname = current_database() AND pid <> pg_backend_pid()"
                )
            )
    finally:
        engine.dispose()

    assert postgres_store.get(match.id) == match


def test_a_failed_statement_never_shows_the_seed(database_url: str) -> None:
    # The database turns every write down, as one that is full can: the
    # error, which goes to the server's log, leaves the values out.
    engine = create_engine(
        database_url + "?options=-c%20default_transaction_read_only%3Don"
    )
    try:
        with pytest.raises(DBAPIError) as error:
            PostgresMatchStore(engine).create(
                ("humans", "robots"), SECRET_SEED, (), owner=None, now=NOW
            )
    finally:
        engine.dispose()

    assert str(SECRET_SEED) not in str(error.value)
    assert "parameters hidden" in str(error.value)


def test_a_row_that_breaks_a_check_never_shows_the_seed(
    postgres_store: PostgresMatchStore,
) -> None:
    # PostgreSQL's detail lists the whole row, seed and all ("Failing row
    # contains ..."): a bug that writes a result the table turns down must not
    # put it in the server's log, in any error of the chain.
    match = postgres_store.create(
        ("humans", "robots"), SECRET_SEED, (), owner=None, now=NOW
    )
    weird = MatchResult(outcome="weird", rounds=(), ended_at=NOW)  # type: ignore[arg-type]

    with pytest.raises(IntegrityError, match="outcome_is_known") as error:
        postgres_store.add_actions(match.id, match.version, (), weird)

    log = "".join(traceback.format_exception(error.value))
    assert str(SECRET_SEED) not in log
    assert "Failing row" not in log


def test_stats_come_in_the_order_of_the_decks_ids_whatever_the_collation(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # Under a language's collation (ICU's here), "a_b" comes before "a-b";
    # in the order of the characters' codes, as in Python, after.
    engine = create_engine(database_url)
    collate = "ALTER TABLE matches ALTER COLUMN player_deck TYPE varchar COLLATE {}"
    try:
        with engine.begin() as connection:
            connection.execute(text(collate.format('"und-x-icu"')))
        owner = PostgresAccountStore(engine).create_account("rui", "hash")
        assert owner is not None
        won = MatchResult(outcome="won", rounds=((1, 0), (1, 0)), ended_at=NOW)
        for deck in ["a_b", "a-b"]:
            match = postgres_store.create(
                (deck, "robots"), 1, (), owner=owner.id, now=NOW
            )
            postgres_store.add_actions(match.id, match.version, (), won)

        decks = [stats.deck for stats in postgres_store.stats(owner.id)]
    finally:
        with engine.begin() as connection:
            connection.execute(text(collate.format('"default"')))
            connection.execute(text("TRUNCATE matches, accounts CASCADE"))
        engine.dispose()

    assert decks == sorted(decks) == ["a-b", "a_b"]


def test_a_move_says_when_the_match_was_last_played(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # created_at is the time the API gives, updated_at the database's own.
    match = postgres_store.create(
        ("humans", "robots"), 1, (), owner=None, now=datetime.now(UTC)
    )
    postgres_store.add_actions(match.id, match.version, (Pass(),))

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            created, updated = connection.execute(
                text("SELECT created_at, updated_at FROM matches WHERE id = :id"),
                {"id": match.id},
            ).one()
    finally:
        engine.dispose()

    assert updated > created


def test_the_migrations_make_the_tables_the_models_describe(
    migrations: Config,
) -> None:
    # As "alembic check": it fails if a model changed with no migration.
    command.check(migrations)


def test_the_migrations_can_be_undone_and_done_again(migrations: Config) -> None:
    command.downgrade(migrations, "base")
    command.upgrade(migrations, "head")

    command.check(migrations)


def test_going_down_stops_before_it_loses_a_built_decks_copy(
    migrations: Config,
    postgres_store: PostgresMatchStore,
) -> None:
    # Without its copy, the match would play again from the faction's deck.
    built = DeckCopy(name="Mine", copies={"soldier": 3})
    kept = postgres_store.create(
        ("humans", "robots"), 1, (), owner=None, now=NOW, built=built
    )

    with pytest.raises(RuntimeError, match="built deck"):
        command.downgrade(migrations, "35aff864c3d9")

    assert postgres_store.get(kept.id) == kept


def test_going_down_stops_before_it_loses_a_matchs_owner(
    migrations: Config,
    postgres_store: PostgresMatchStore,
    postgres_accounts: PostgresAccountStore,
) -> None:
    # Without its owner, a player's match would be anyone's.
    account = postgres_accounts.create_account("rui", "a hash")
    assert account is not None
    kept = postgres_store.create(("humans", "robots"), 1, (), owner=account.id, now=NOW)

    with pytest.raises(RuntimeError, match="owner"):
        command.downgrade(migrations, "517136ed7eac")

    assert postgres_store.get(kept.id) == kept


def test_going_down_stops_before_it_loses_a_matchs_result(
    migrations: Config,
    postgres_store: PostgresMatchStore,
) -> None:
    # A guest's match keeps its result too.
    started = postgres_store.create(("humans", "robots"), 1, (), owner=None, now=NOW)
    won = MatchResult(outcome="won", rounds=((1, 0), (1, 0)), ended_at=NOW)
    kept = postgres_store.add_actions(started.id, started.version, (Pass(),), won)

    with pytest.raises(RuntimeError, match="result"):
        command.downgrade(migrations, "517136ed7eac")

    assert postgres_store.get(started.id) == kept


@pytest.fixture
def client(postgres_store: PostgresMatchStore) -> Iterator[TestClient]:
    """Return a test client for the app, with its matches in PostgreSQL."""
    app.dependency_overrides[get_store] = lambda: postgres_store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_a_match_survives_a_restart_of_the_api(
    client: TestClient, database_url: str
) -> None:
    # A match is started and played.
    app.dependency_overrides[new_seed] = lambda: 1
    started = client.post("/matches", json={"deck": "humans"})
    move = {
        "version": started.json()["version"],
        "action": started.json()["view"]["legal_actions"][0],
    }
    played = client.post(f"/matches/{started.json()['id']}/actions", json=move)
    assert played.status_code == 200

    # The API starts again, with a new store on new connections.
    engine = create_engine(database_url)
    app.dependency_overrides[get_store] = lambda: PostgresMatchStore(engine)
    try:
        seen = client.get(f"/matches/{started.json()['id']}")
        move = {
            "version": seen.json()["version"],
            "action": seen.json()["view"]["legal_actions"][0],
        }
        again = client.post(f"/matches/{started.json()['id']}/actions", json=move)
    finally:
        engine.dispose()

    assert seen.status_code == 200
    assert seen.json()["view"] == played.json()["view"]
    assert seen.json()["version"] == played.json()["version"]
    assert again.status_code == 200
    assert UUID(again.json()["id"]) == UUID(started.json()["id"])


def test_the_apis_role_may_delete_sessions_and_decks_and_not_move_a_migration(
    migrations: Config, database_url: str
) -> None:
    # As online: rowen_app reads, adds and changes rows (docs/deploy.md), and
    # the migrations let it delete sessions, to log out, and decks. Roles belong to the
    # whole server, not to one database, so the test makes it only if it
    # isn't there.
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DO $$ BEGIN"
                    " IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rowen_app')"
                    " THEN CREATE ROLE rowen_app; END IF; END $$"
                )
            )
            # As the default privileges online give it.
            connection.execute(
                text("GRANT INSERT, UPDATE ON alembic_version TO rowen_app")
            )
        command.downgrade(migrations, "a398e9df25d3")
        command.upgrade(migrations, "head")
        with engine.connect() as connection:
            may_delete: dict[str, bool] = {
                table: connection.execute(
                    text("SELECT has_table_privilege('rowen_app', :table, 'DELETE')"),
                    {"table": table},
                ).scalar_one()
                for table in ("matches", "accounts", "sessions", "player_decks")
            }
            may_move_the_migration: bool = connection.execute(
                text(
                    "SELECT has_table_privilege('rowen_app', 'alembic_version',"
                    " 'INSERT, UPDATE')"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert may_delete == {
        "matches": False,
        "accounts": False,
        "sessions": True,
        "player_decks": True,
    }
    assert not may_move_the_migration


def test_deleting_an_account_deletes_its_sessions(
    postgres_accounts: PostgresAccountStore, database_url: str
) -> None:
    account = postgres_accounts.create_account("rui", "a hash")
    assert account is not None
    now = datetime(2026, 10, 22, tzinfo=UTC)
    postgres_accounts.create_session(account, b"token", now + timedelta(days=1), now)

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM accounts WHERE id = :id"), {"id": account.id}
            )
    finally:
        engine.dispose()

    assert postgres_accounts.find_session(b"token", now) is None


def test_a_session_survives_a_restart_of_the_api(
    postgres_accounts: PostgresAccountStore, database_url: str
) -> None:
    app.dependency_overrides[get_accounts] = lambda: postgres_accounts
    client = TestClient(app, base_url="https://testserver")
    engine = create_engine(database_url)
    try:
        registered = client.post(
            "/accounts", json={"username": "rui", "password": "dragon123"}
        )
        # The API starts again, with a new store on new connections.
        app.dependency_overrides[get_accounts] = lambda: PostgresAccountStore(engine)
        seen = client.get("/session")
        logged_out = client.delete("/session")
        after = client.get("/session")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert registered.status_code == 201
    assert seen.json() == {"username": "rui"}
    assert logged_out.status_code == 204
    assert after.status_code == 401


def test_deleting_an_account_deletes_its_decks(
    postgres_accounts: PostgresAccountStore, database_url: str
) -> None:
    account = postgres_accounts.create_account("rui", "a hash")
    assert account is not None
    decks = PostgresDeckStore(postgres_accounts._engine)
    decks.create_deck(account.id, "Mine", "humans", {"human": 5}, NOW)

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM accounts WHERE id = :id"), {"id": account.id}
            )
            left = connection.execute(text("SELECT count(*) FROM player_decks"))
            assert left.scalar_one() == 0
    finally:
        engine.dispose()


def test_of_two_requests_at_once_for_the_last_deck_only_one_keeps_it(
    postgres_accounts: PostgresAccountStore, database_url: str
) -> None:
    # A player with nine decks builds a tenth twice at once. As with two
    # moves at once, the test holds the account's row (FOR UPDATE) until both
    # requests wait for it, then lets them go. A store that only counted the
    # decks would let both count nine and keep eleven.
    account = postgres_accounts.create_account("rui", "a hash")
    assert account is not None
    decks = PostgresDeckStore(postgres_accounts._engine)
    for n in range(MAX_DECKS - 1):
        decks.create_deck(account.id, str(n), "humans", {"human": 5}, NOW)
    results: list[StoredDeck | None] = []

    def build() -> None:
        results.append(
            decks.create_deck(account.id, "Last", "humans", {"human": 5}, NOW)
        )

    threads = [threading.Thread(target=build) for _ in range(2)]
    engine = create_engine(database_url)
    try:
        with engine.connect() as holder:
            holder.execute(
                text("SELECT 1 FROM accounts WHERE id = :id FOR UPDATE"),
                {"id": account.id},
            )
            for thread in threads:
                thread.start()
            wait_until_waiting_for_a_lock(engine, 2)
            holder.rollback()
        for thread in threads:
            thread.join()
    finally:
        engine.dispose()

    assert len(results) == 2
    assert len([deck for deck in results if deck is not None]) == 1
    assert len(decks.list_decks(account.id)) == MAX_DECKS
