# ADR 0004: Use a monorepo and manage the backend with uv

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

Rowen has a Python backend and, from Phase 2, a TypeScript frontend. The two are
tied together by the API contract: the frontend's types are generated from the
backend's OpenAPI schema ([ADR 0001](0001-web-full-stack-architecture.md)).

Two questions follow: whether both live in one repository or in two, and how
the backend's Python version, dependencies and virtual environment are managed
so that the environment is identical on the author's Windows machine, on Linux
in CI and later in Docker.

## Decision

- **One repository** with `backend/` and `frontend/` at the top level, next to
  `docs/` and `.github/`. Each folder is a self-contained project with its own
  tooling, and CI runs a separate job for each.
- **uv manages the backend:**
  - `pyproject.toml` declares the dependencies, with development tools (ruff,
    mypy, pytest) in a `dev` dependency group.
  - `uv.lock` pins the exact version of every package, including indirect
    dependencies, and is committed.
  - `.python-version` pins Python 3.14, which uv downloads if it is missing.
  - CI installs with `uv sync --locked`, which fails if `uv.lock` is out of date
    with `pyproject.toml`.
- **`src` layout** (`backend/src/rowen/`): tests import the installed package
  rather than whatever happens to be in the current directory, so packaging
  mistakes show up in the tests.

The frontend's tooling is chosen when the frontend is created in Phase 2.

## Alternatives considered

- **Two repositories** (backend and frontend). A clean separation, but an API
  change would need two coordinated pull requests, the generated types could
  fall out of sync, and the project would be split across two places.
- **pip, venv and `requirements.txt`.** Available everywhere, but it has no
  lockfile of the full dependency tree without extra tools (such as pip-tools),
  does not install Python itself and is much slower.
- **Poetry.** Mature and has a lockfile, but it does not install Python either,
  and uv covers the same needs (plus Python versions) in a single, much faster
  tool.

## Consequences

- One pull request can change the API, the generated types and the frontend
  together, and CI checks all of them before merging.
- Anyone, including CI, gets the same environment with two steps: install uv,
  then run `uv sync`.
- uv is younger than pip or Poetry and still changes quickly. The lockfile and
  the pinned range of the build backend (`uv_build>=0.12.19,<0.13.0`) protect
  the project from unexpected upgrades.
- CI time grows with each project in the repository. If it gets slow, jobs can
  be limited to the paths that changed.
