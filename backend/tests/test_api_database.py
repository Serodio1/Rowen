"""Tests for the store in PostgreSQL, beyond those both stores share.

They run only when TEST_DATABASE_URL is set (tests/conftest.py).
"""

import threading
import time
from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from rowen.api.app import app, get_store, new_seed
from rowen.api.database import PostgresMatchStore, create_engine
from rowen.api.store import FIRST_VERSION, StoredMatch
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
    match = postgres_store.create(("humans", "robots"), 1, EVERY_KIND[:4])
    added = postgres_store.add_actions(match.id, match.version, EVERY_KIND[4:])

    assert added is not None
    assert added.actions == EVERY_KIND
    assert postgres_store.get(match.id) == added


@pytest.mark.parametrize("seed", [0, 2**63 - 1])
def test_seeds_of_63_bits_fit(postgres_store: PostgresMatchStore, seed: int) -> None:
    match = postgres_store.create(("humans", "robots"), seed, ())

    stored = postgres_store.get(match.id)

    assert stored is not None
    assert stored.seed == seed


def test_the_database_turns_down_a_negative_seed(
    postgres_store: PostgresMatchStore,
) -> None:
    with pytest.raises(IntegrityError, match="seed_not_negative"):
        postgres_store.create(("humans", "robots"), -1, ())


def test_a_match_outlives_the_store_that_kept_it(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    # A new store, with connections of its own, as after a restart.
    match = postgres_store.create(("humans", "robots"), 1, (Pass(),))
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
    match = postgres_store.create(("humans", "robots"), 1, ())
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
    match = postgres_store.create(("humans", "robots"), 1, ())
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
            PostgresMatchStore(engine).create(("humans", "robots"), SECRET_SEED, ())
    finally:
        engine.dispose()

    assert str(SECRET_SEED) not in str(error.value)
    assert "parameters hidden" in str(error.value)


def test_a_move_says_when_the_match_was_last_played(
    postgres_store: PostgresMatchStore, database_url: str
) -> None:
    match = postgres_store.create(("humans", "robots"), 1, ())
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
