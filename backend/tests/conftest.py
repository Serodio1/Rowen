"""What several test files share: the PostgreSQL database to test against.

The tests that need PostgreSQL run only when ``TEST_DATABASE_URL`` gives the
address of a database they may empty, as CI does; otherwise they are skipped
(pytest lists them). The README says how to run one with Docker.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from rowen.api.accounts import AccountStore, MemoryAccountStore
from rowen.api.database import PostgresAccountStore, PostgresMatchStore, create_engine
from rowen.api.store import MatchStore, MemoryMatchStore

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"

# The API picks its store from DATABASE_URL as it is imported, which the test
# files do after this one. A database set in the terminal to run the API must
# never be the one the tests write to.
os.environ.pop("DATABASE_URL", None)


def alembic_config(url: str) -> Config:
    """Return Alembic's settings, for the database at ``url``."""
    config = Config(ALEMBIC_INI)
    config.attributes["url"] = url
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return the address of the test database, brought up to date.

    The migrations run once, as a deployment runs them.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set: no PostgreSQL to test against")
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture
def migrations(database_url: str) -> Config:
    """Return Alembic's settings for the test database, to run migrations."""
    return alembic_config(database_url)


@pytest.fixture
def postgres_store(database_url: str) -> Iterator[PostgresMatchStore]:
    """Return a store in the test database, with no matches in it."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE matches"))
    yield PostgresMatchStore(engine)
    engine.dispose()


@pytest.fixture(params=["memory", "postgres"])
def any_store(request: pytest.FixtureRequest) -> MatchStore:
    """Return each store in turn, empty: a test using it runs once for each."""
    if request.param == "memory":
        return MemoryMatchStore()
    store: MatchStore = request.getfixturevalue("postgres_store")
    return store


@pytest.fixture
def postgres_accounts(database_url: str) -> Iterator[PostgresAccountStore]:
    """Return a store of accounts in the test database, with none in it."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE accounts, sessions"))
    yield PostgresAccountStore(engine)
    engine.dispose()


@pytest.fixture(params=["memory", "postgres"])
def any_accounts(request: pytest.FixtureRequest) -> AccountStore:
    """Return each store of accounts in turn, empty, as ``any_store`` does."""
    if request.param == "memory":
        return MemoryAccountStore()
    store: AccountStore = request.getfixturevalue("postgres_accounts")
    return store
