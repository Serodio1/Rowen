"""Tests for the store in PostgreSQL, beyond those both stores share.

They run only when TEST_DATABASE_URL is set (tests/conftest.py).
"""

import threading
from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

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
    postgres_store: PostgresMatchStore,
) -> None:
    # Two requests chose a move from the same version, and reach the
    # database at the same moment, each on a connection of its own.
    match = postgres_store.create(("humans", "robots"), 1, ())
    start = threading.Barrier(2)
    results: list[StoredMatch | None] = []

    def add(action: Action) -> None:
        start.wait()
        results.append(postgres_store.add_actions(match.id, match.version, (action,)))

    threads = [
        threading.Thread(target=add, args=(action,)) for action in EVERY_KIND[:2]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    kept = [result for result in results if result is not None]
    assert len(results) == 2
    assert len(kept) == 1
    assert kept[0].version == FIRST_VERSION + 1
    assert postgres_store.get(match.id) == kept[0]


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
