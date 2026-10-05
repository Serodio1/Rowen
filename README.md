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

Every push and pull request runs the same checks on GitHub Actions.

## License

The code is released under the [MIT License](LICENSE).
