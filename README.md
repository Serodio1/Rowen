# Rowen

[![CI](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml/badge.svg)](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml)

A turn-based card game inspired by the Gwent minigame from *The Witcher 3*, built
as a full-stack web application: a pure Python rules engine behind a FastAPI API,
PostgreSQL, and a React + TypeScript frontend.

> **Status:** Phase 4 is done and released as
> [`v0.4.0`](https://github.com/Serodio1/Rowen/releases): a match against the
> AI can be played online, on a board with card art, animations and the
> keyboard, as a guest or with an account. A player with an account finds
> their matches under "My matches", resumes an unfinished one, sees how many
> they won, lost and drew with each deck, and builds decks of their own under
> "My decks". Phase 5, a smarter AI and the rest of the rules, comes next.

![A match in Rowen: the AI's rows above, the player's below, Hoarfrost on both
melee rows, and a Plane shown large with what it does](docs/screenshot.webp)

## Play online

**<https://rowen-806785616593.europe-west1.run.app>**: choose the AI's level
(Easy, Normal or Hard) and a deck, and play against the AI, with nothing to
install, as a guest or with an account. After
a quiet while the server is stopped, so the first visit can take a few seconds
more while it starts (about 6 when measured). Matches are kept in a database,
so a match goes on after the server sleeps, and when a new version goes
online.

## Documentation

- [Project plan](docs/plan.md): goals, architecture, tech stack and roadmap.
- [Game rules](docs/rules.md)
- [Architecture decision records](docs/adr/README.md): why the main
  technical decisions were made.
- [Deploying to Google Cloud Run](docs/deploy.md)
- [The cards' art](docs/art.md): where it comes from, and how to add more.
- [Phase 1 retrospective](docs/retrospectives/phase-1.md): what the game
  engine release built, and what it taught.
- [Phase 2 retrospective](docs/retrospectives/phase-2.md): what the first
  version online built, and what it taught.
- [Phase 3 retrospective](docs/retrospectives/phase-3.md): what the real
  interface built, and what it taught.
- [Phase 4 retrospective](docs/retrospectives/phase-4.md): what accounts,
  match history and the deck builder built, and what they taught.

## Play with Docker

The quickest way to play: with [Docker](https://docs.docker.com/get-started/get-docker/)
running (Docker Desktop on Windows and macOS), run this in the repository's
folder:

```sh
docker compose up --build    # build the images, then start the game
```

Then open <http://localhost:8080> and choose a deck. `Ctrl+C` stops the game,
and `docker compose down` removes its containers. The matches are kept in
PostgreSQL, on this computer: a match goes on after the game starts again,
until `docker compose down -v` deletes them. The first build downloads
the base images and takes a few minutes; later ones reuse what did not change.
If `docker` says it cannot find `dockerDesktopLinuxEngine`, Docker Desktop is
not running: start it and wait until it says the engine is running. Every 5
seconds, the API's log shows a `GET /api/decks`: that is Docker checking that
the API answers.

Three containers run (`compose.yaml`, [ADR
0009](docs/adr/0009-docker-images-behind-nginx.md)): `web`, where nginx serves
the page and passes its requests for `/api` on to the API; `api`, the web API,
whose endpoints are listed at <http://localhost:8080/api/docs>; and `db`,
PostgreSQL. Before the API starts, a fourth one, `migrate`, brings the
database's tables up to date and stops ([ADR
0013](docs/adr/0013-keep-matches-in-postgresql.md)). These are the images a
server would run; for development, run the API and the page without Docker, as
below.

## Play in the terminal

A match against the AI can also be played in the terminal (see
[Development](#development) for uv):

```sh
cd backend
uv run rowen              # choose a faction, then play against the AI
uv run rowen --seed 42    # play the match with seed 42 again
```

Each turn shows the board and a numbered list of what you can do: type a number
to choose. When the match ends, the seed is shown: the same seed and the same
choices always give the same match.

## Run the web API

The web API is what the browser plays through. It also lets you play a whole
match against the AI, as JSON:

```sh
cd backend
uv run uvicorn rowen.api.app:app --reload --reload-dir src
```

Then open <http://127.0.0.1:8000/docs>: it lists the endpoints and lets you
try them. `GET /decks` lists the decks, and `POST /matches` with
`{"deck": "humans"}` starts a match (if the AI starts, it swaps its cards first,
and the response says so). To play, send one of the `legal_actions`
of the view, as it is, with the match's `version`, to
`POST /matches/{id}/actions`: `{"version": 1, "action": {"type": "pass"}}`.
A move from an old version is turned down (`match_changed`). If it is then the AI's
turn, the AI plays before the server responds, and the response holds the new
view and what happened. A player may also make an account: `POST /accounts`
with `{"username": "rui", "password": "at least 8 characters"}` logs them in
with a session cookie, `POST /session` logs in again, `GET /session` says who
is logged in and `DELETE /session` logs out
([ADR 0014](docs/adr/0014-accounts-with-sessions-in-postgresql.md)). A match
started while logged in is the player's alone: `GET /matches` lists theirs,
newest first, 20 at a time (`?before=<id>` for the next page), and
`GET /stats` counts their wins, losses and draws with each deck. On the page,
"My matches" shows both, and "Resume" plays on a match that isn't over:
`GET /matches/{id}` gives it with the `rounds` that ended so far
([ADR 0015](docs/adr/0015-players-own-their-matches.md)). A player who is
logged in may also build decks of their own: `GET /decks/{id}/choices` says
which cards a deck of that faction may hold and how many copies of each, and
`/my-decks` lists their decks (`GET`), builds one (`POST`, with
`{"name": "Mine", "deck": "humans", "copies": {"human": 5, ...}}`), changes
one (`PUT /my-decks/{id}`) or deletes one (`DELETE /my-decks/{id}`), up to
10. `POST /matches` with `{"my_deck": "<id>"}` starts a match with one; the
match keeps a copy of it, so changing the deck later doesn't change the match
([ADR 0017](docs/adr/0017-keep-a-copy-of-a-built-deck-in-each-match.md)). When the API turns a request down, it answers with a
`code` and a `message`, such as `illegal_action`. `--reload` restarts the
server whenever the Python code in `src` changes.
Run like this, the API keeps its matches in memory, so they are lost when it
stops or restarts. With `DATABASE_URL` set to a PostgreSQL database
(`postgresql+psycopg://user:password@host/database`), whose tables
`uv run alembic upgrade head` made, it keeps them there, as in Docker Compose
and online.

## Run the frontend

The browser interface is a React app in `frontend/`. It needs
[Node.js](https://nodejs.org/) 24.15.0 or later, which comes with npm 11.10 or
later:

```sh
cd frontend
npm ci          # install the exact versions in package-lock.json
npm run dev     # start the development server
```

With the web API running too (above, in another terminal), open
<http://localhost:5173> and choose a deck: a match against the AI starts. Click
a card in your hand to choose it: the places it may go light up, and clicking
one plays it (a card with nowhere to choose, such as weather, is played by
clicking it again). The AI answers at once, until the match is over. With the
keyboard: Tab and the arrow keys go from card to card, Enter chooses, 1, 2 and
3 play the card chosen in the melee, ranged or siege row, and Escape lets it
go. The page
shows the board: the AI's rows on top and yours below, with their scores, the
weather, each player's lives, cards in hand, deck and discard pile, and your hand
under your rows. Over the board, it says how the last round went, and under the
moves what happened in the match so far, the latest move first. The look follows
the card game in The Witcher 3, but it is drawn with CSS, and the cards' art
was made for Rowen with AI tools ([where it comes from](docs/art.md)): no
art, icon or font comes from the game. The CSS is made with Tailwind CSS 4, so the page needs a
recent browser: Chrome or Edge 111, Safari 16.4 or Firefox 128, or later. The
development server passes the page's requests for
`/api` on to the web API at 127.0.0.1:8000, where uvicorn listens by default
(`vite.config.ts`), and updates the page whenever the code changes. If the page
says "Could not reach the server.", start the API and try again. Restarting the
API ends the match being played, since without `DATABASE_URL` matches are kept
in memory.

On Windows, if PowerShell says that running scripts is disabled, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Development

The backend needs [uv](https://docs.astral.sh/uv/), which also installs the
right Python version (3.14) automatically.

```sh
cd backend
uv sync                 # create the virtual environment and install dependencies
uv run pytest           # run the tests (those that need PostgreSQL are skipped)
uv run ruff check       # lint
uv run ruff format      # format the code
uv run mypy             # type-check
uv run lint-imports     # check which modules may import which
```

The tests of the store in PostgreSQL run only when `TEST_DATABASE_URL` gives
a database they may wipe, as in CI. With Docker, in PowerShell, wait until
the database is ready (the first time, PostgreSQL starts twice):

```powershell
docker run --rm -d --name rowen-test-db -p 127.0.0.1:5433:5432 -e POSTGRES_PASSWORD=test --health-cmd "pg_isready --host=127.0.0.1 --username=postgres" --health-interval 1s postgres:18-alpine
while ((docker inspect --format "{{.State.Health.Status}}" rowen-test-db) -ne "healthy") { Start-Sleep 1 }
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:test@127.0.0.1:5433/postgres"
uv run pytest
docker stop rowen-test-db
Remove-Item Env:TEST_DATABASE_URL
```

A change to the tables is a migration (Alembic, in `backend/migrations`):
change the model in `rowen/api/database.py`; then, with `DATABASE_URL` set to
a database brought up to date (`uv run alembic upgrade head`), write the
migration with `uv run alembic revision --autogenerate -m "What it does"`.
Read it, and commit it with the change. With `TEST_DATABASE_URL` set, as in
CI, the tests fail if the models and the migrations make different tables.

The frontend has the same kind of checks, run with npm:

```sh
cd frontend
npm ci                  # install the dependencies (again after package-lock.json changes)
npm run lint            # lint with ESLint (Tailwind classes too)
npm run format          # format the code with Prettier
npm run typecheck       # type-check with TypeScript
npm test                # run the tests with Vitest
npm run build           # build the production files into dist/
```

The end-to-end tests (`frontend/e2e`) play the game in a real browser with
[Playwright](https://playwright.dev/), against the game in Docker, as CI does:
a whole match, the layout on a laptop and a phone, an account, a player's
matches, and a deck built, played and deleted. In PowerShell, from the
repository's folder:

```powershell
docker compose up --build --detach --wait   # start the game, as in "Play with Docker"
cd frontend
npx playwright install chromium             # once, and again after Playwright is updated
npm run test:e2e                            # run them in Chromium
docker compose down                         # stop the game
```

`npm run test:e2e -- --headed` shows the browser while it plays. To test
another copy of the game, set `BASE_URL` (`$env:BASE_URL = "http://localhost:5173"`
for the development server, with the API running).

To install a new package, use `npm install <package>`, which also updates
`package-lock.json`. In `frontend/`, npm only picks versions published at least
14 days earlier, and never runs the install scripts of packages (see
`frontend/.npmrc` and [ADR 0007](docs/adr/0007-frontend-tooling.md)): a release
that turns out to be malicious is usually found and removed before it can reach
the project. `npm ci` installs exactly what `package-lock.json` says. If
`npm install <package>@<version>` seems stuck, stop it and check with
`npm view <package> time` that the version exists and is at least 14 days old.

When the API changes, its OpenAPI document and the frontend's types, which
are generated from it, change too ([ADR 0008](docs/adr/0008-generated-api-types.md)).
Write both again and commit them with the change:

```sh
cd backend
uv run python -m rowen.api.openapi   # write backend/openapi.json
cd ../frontend
npm run generate:api                 # generate src/api/schema.d.ts from it
```

A backend test fails while `openapi.json` is out of date, and CI checks the
types. A new version number of the project, or a FastAPI or Pydantic upgrade,
can also change `openapi.json`: then run the first command again.

GitHub Actions runs the same checks on every pull request and every push to
`main`. It also builds the Docker images, starts them and checks, through
nginx, that the game answers.

## License

The code is released under the [MIT License](LICENSE). The cards' art is not
(see [NOTICE](NOTICE)): it was generated with Grok and Gemini, and
[docs/art.md](docs/art.md) says where it comes from and the tools' terms.
