# ADR 0001: Build Rowen as a full-stack web application

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

Rowen started as the idea of a desktop game written with Pygame. Two goals from
the [project plan](../plan.md) point elsewhere:

- **Playable from a link.** Anyone should be able to play a full match within
  seconds, with nothing to install. A desktop game has to be downloaded, and an
  unsigned executable triggers security warnings on Windows and macOS.
- **A complete application, built to professional standards.** The project is
  meant to cover the whole stack of a typical web product: an HTTP API, a
  relational database, a typed frontend, containers, CI/CD and a live
  deployment.

Rowen is a turn-based card game. It needs no real-time rendering or physics, so
a web interface loses nothing compared with a game library.

## Decision

Rowen is a web application in three parts:

- **Backend (Python):** a pure rules engine ([ADR 0003](0003-pure-immutable-engine.md))
  exposed through a REST API built with FastAPI.
- **Database:** PostgreSQL, accessed with SQLAlchemy 2 and versioned with
  Alembic migrations.
- **Frontend:** React with TypeScript in strict mode, built with Vite.

The client and the server talk over HTTP with JSON. The game runs on the server
([ADR 0002](0002-server-authoritative-game.md)). The frontend's TypeScript types
are generated from the API's OpenAPI schema, so both sides share one contract.

## Alternatives considered

- **Desktop game with Pygame.** The quickest way to get something on screen,
  but it has to be installed, and it leaves out APIs, databases and web
  frontends entirely.
- **Browser-only game (TypeScript, no backend).** Cheap to host as static
  files, but it has no API and no database, and the client could not be trusted
  with hidden information (see ADR 0002).
- **Full-stack TypeScript (for example Next.js with API routes).** One language
  end to end, but it blurs the line between frontend and backend, which this
  project wants to keep explicit. Python also has excellent tools for testing a
  rules engine (pytest and Hypothesis).
- **Server-rendered HTML (for example HTMX with Jinja templates).** Fewer moving
  parts, but a card board with animations driven by game events is easier to
  build from components in a single-page app.

## Consequences

- Anyone with a browser can play, and each layer (engine, API, database,
  frontend) has a clear boundary and can be tested on its own.
- There are more moving parts than in a desktop game: two languages, two
  toolchains, a database and a deployment. Docker Compose for local development
  and CI on every pull request keep them manageable.
- Every move is an HTTP round trip. That is acceptable for a turn-based game.
- The project needs hosting. It is chosen in Phase 2 and recorded in its own ADR;
  free tiers bring limits such as cold starts, which running everything in
  Docker makes easier to move away from.
