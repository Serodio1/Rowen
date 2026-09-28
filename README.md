# Rowen

[![CI](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml/badge.svg)](https://github.com/Serodio1/Rowen/actions/workflows/ci.yml)

A turn-based card game inspired by the Gwent minigame from *The Witcher 3*, built
as a full-stack web application: a pure Python rules engine behind a FastAPI API,
PostgreSQL, and a React + TypeScript frontend.

> **Status:** early development (Phase 0, foundations). Not playable yet.

## Documentation

- [Project plan](docs/plan.md): goals, architecture, tech stack and roadmap.
- [Game rules](docs/rules.md)

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
```

Every push and pull request runs the same checks on GitHub Actions.

## License

The code is released under the [MIT License](LICENSE).
