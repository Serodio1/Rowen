# Rowen

[![CI](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml/badge.svg)](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml)

A turn-based card game inspired by the Gwent minigame from *The Witcher 3*, built
as a full-stack web application: a pure Python rules engine behind a FastAPI API,
PostgreSQL, and a React + TypeScript frontend.

> **Status:** Phase 1 is done and released as
> [`v0.1.0`](https://github.com/Serodio1/Rowen/releases): the game engine, a
> baseline AI and a full match against it in the terminal. Next is Phase 2, a
> first version that can be played online.

## Documentation

- [Project plan](docs/plan.md): goals, architecture, tech stack and roadmap.
- [Game rules](docs/rules.md)
- [Architecture decision records](docs/adr/README.md): why the main
  technical decisions were made.
- [Phase 1 retrospective](docs/retrospectives/phase-1.md): what the game
  engine release built, and what it taught.

## Play in the terminal

Until the web interface is ready, a match against the AI can be played in the
terminal (see [Development](#development) for uv):

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
`{"deck": "humans"}` starts a match (if the AI starts, it plays first, and the
response says what it did). To play, send one of the `legal_actions`
of the view, as it is, to `POST /matches/{id}/actions`: if it is then the AI's
turn, the AI plays before the server responds, and the response holds the new
view and what happened. When the API turns a request down, it answers with a
`code` and a `message`, such as `illegal_action`. `--reload` restarts the
server whenever the Python code in `src` changes.
Matches are kept in memory for now, so they are lost when the server stops or
restarts.

## Run the frontend

The browser interface is a React app in `frontend/`. It needs
[Node.js](https://nodejs.org/) 24.14.1 or later, which comes with npm 11.10 or
later:

```sh
cd frontend
npm ci          # install the exact versions in package-lock.json
npm run dev     # start the development server
```

With the web API running too (above, in another terminal), open
<http://localhost:5173> and choose a deck: a match against the AI starts. Click
a move to make it, and the AI answers at once, until the match is over. The page
shows the board: the AI's rows on top and yours below, with their scores, the
weather, each player's lives, cards in hand, deck and discard pile, and your hand
under your rows. Over the board, it says how the last round went, and under the
moves what happened in the match so far, the latest move first. The look follows
the card game in The Witcher 3, but it is all drawn with CSS: no art, icon or
font comes from the game. The CSS is made with Tailwind CSS 4, so the page needs a
recent browser: Chrome or Edge 111, Safari 16.4 or Firefox 128, or later. The
development server passes the page's requests for
`/api` on to the web API at 127.0.0.1:8000, where uvicorn listens by default
(`vite.config.ts`), and updates the page whenever the code changes. If the page
says "Could not reach the server.", start the API and try again. Restarting the
API ends the match being played, since matches are kept in memory.

On Windows, if PowerShell says that running scripts is disabled, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Development

The backend needs [uv](https://docs.astral.sh/uv/), which also installs the
right Python version (3.14) automatically.

```sh
cd backend
uv sync                 # create the virtual environment and install dependencies
uv run pytest           # run the tests
uv run ruff check       # lint
uv run ruff format      # format the code
uv run mypy             # type-check
uv run lint-imports     # check which modules may import which
```

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

Every push and pull request runs the same checks on GitHub Actions.

## License

The code is released under the [MIT License](LICENSE).
