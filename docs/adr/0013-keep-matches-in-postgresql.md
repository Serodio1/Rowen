# ADR 0013: Keep each match in PostgreSQL as its seed and actions

- **Status:** Accepted
- **Date:** 2026-10-17

## Context

The API kept its matches in the memory of its one process
(`rowen.api.store`). A restart, a new deployment or Cloud Run stopping an idle
instance lost every match being played
([ADR 0010](0010-deploy-on-cloud-run.md)).
The project also means to show a backend with SQL and migrations.

Three things had to be chosen: what to keep for each match, which database,
and where the code goes. The author does not want a monthly cost.

The engine is deterministic ([ADR 0003](0003-pure-immutable-engine.md)): the
same decks, seed and actions always make the same state. Measured on a
laptop-sized container: a whole match has about 15 to 40 actions, and playing
them all again takes a few milliseconds.

## Decision

- **A match is kept as what it takes to play it again**: the ids of the two
  decks, the seed, every action played (the player's and the AI's, in order)
  and a version. The API plays the actions again on each request
  (`_play_again`). No `GameState` is ever stored.
- **PostgreSQL**, through SQLAlchemy 2 and psycopg 3, with the tables made by
  migrations (Alembic, `backend/migrations`). One table, `matches`: the actions
  are a JSONB list, each in the shape the API sends it.
- **The version does the optimistic locking** (#67): a move adds its actions
  with `UPDATE matches ... WHERE id = :id AND version = :version`, in one
  statement, so of two requests from the same version only one is kept.
- **Seeds have 63 bits**, not 64, so they fit a `BIGINT`, whose largest value
  is 2^63 − 1. 2^63 seeds are still far too many to try.
- **The code stays in `rowen.api`**: `rowen/api/database.py` next to the store
  in memory, using the API's shapes of the actions to turn them into JSON.
  The engine still imports nothing of it (import-linter).
- **Both stores stay**, behind the same `MatchStore` protocol and the same
  tests: with `DATABASE_URL` the API uses PostgreSQL (Docker Compose, CI,
  online); without it, memory (`uv run uvicorn` on a computer, and the fast
  API tests).
- **Online, the database is Neon's free plan, in Frankfurt**
  (`aws-eu-central-1`,
  near Cloud Run's `europe-west1`): 1 GB and 100 compute hours a month, at no
  cost. It sleeps after 5 idle minutes. Its password is in Google's Secret
  Manager, and the migrations run in CI before each deployment
  ([ADR 0012](0012-deploy-from-ci.md)); both come with the pull request that
  connects it.

## Alternatives considered

- **Keeping the whole state as JSON.** Nothing to play again on each request,
  but much more code: every part of the state turned into JSON and back, and
  tested. It breaks just the same when the shape of the state changes.
- **Both the state and the actions.** Twice the code, and two things that must
  agree.
- **A separate `rowen.db` package**, as the issue first said. It would either
  import the API's shapes, the database depending on the API, or repeat that
  code.
- **Only PostgreSQL, no store in memory.** One implementation, but every API
  test and every run on a computer would need a database.
- **Cloud SQL**, Google's own PostgreSQL. All in one place, but about
  8–11 USD a month, every month.
- **Supabase's free plan.** A real PostgreSQL at no cost, but a project with a
  week without use is paused until someone restores it by hand: a recruiter
  could find the game broken.
- **Aiven's free plan.** Its region cannot be chosen, and an idle service can
  be powered off.
- **PostgreSQL only in Docker Compose and CI, memory online.** Nothing outside
  Google, but matches online would still not survive a restart.

## Consequences

- A match survives a restart of the API: CI's smoke test restarts it in the
  middle and finds the match.
- Each request plays the match again: a few milliseconds more, and `apply`
  must keep depending on nothing but the state and the action (ADR 0003).
- Each request also waits on the database: reading a match is one statement,
  and a move one more, each in a transaction of its own (about 4 round trips
  each, with the check that the connection is still open). Doing without the
  transactions would halve them; that is for when the time online is
  measured.
- A whole match is at most about 2 KB of JSON (measured over 20 matches).
  Nothing deletes old matches yet, so the table only grows; at that size
  1 GB holds hundreds of thousands, and
  nginx's limit on new matches ([ADR 0011](0011-limit-requests-per-address.md))
  slows anyone filling it. Deleting matches left alone for long is for later.
- A change to the rules or the cards can make a match started before it play
  differently, once matches outlive a deployment, or fail on every request
  (a 500, since an action of its list is no longer legal): the match is then
  lost. Answering such a match with "not found" instead is for later.
- The API's image carries Alembic and the migrations, for Docker Compose's
  `migrate`. The API itself never runs them.
- A database that can't be reached makes a request fail after 5 seconds
  (`connect_timeout`), rather than hold the server for minutes; the health
  check (`GET /decks`) doesn't use the database, so it still answers.
- The tests of the store in PostgreSQL need a database (`TEST_DATABASE_URL`):
  CI has one, and on a computer they are skipped unless Docker runs one.
- Online, the first request after Neon slept waits about half a second more,
  on top of Cloud Run's own start.
