"""Run the migrations against the database at DATABASE_URL.

Alembic runs this file for each command, such as ``alembic upgrade head``. It
compares the database with the models in ``rowen.api.database`` for
``alembic check`` and ``alembic revision --autogenerate``. A test may give
the address as ``config.attributes["url"]`` instead.
"""

import os
from logging.config import fileConfig

from alembic import context

from rowen.api.database import Base, create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

if context.is_offline_mode():
    raise SystemExit("The migrations only run against a database (no --sql).")

url = config.attributes.get("url") or os.environ["DATABASE_URL"]
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
