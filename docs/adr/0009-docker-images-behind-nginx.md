# ADR 0009: Run the game in two Docker images, with nginx in front of the API

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Phase 2 puts the game online. A server has none of what a developer's computer
has (Python 3.14, uv, Node 24, the dependencies), and setting it up by hand
would make the server and the computers drift apart.
[ADR 0001](0001-web-full-stack-architecture.md) chose Docker so that the same
images run everywhere and the game can move between hosting providers.

The page calls the API under `/api` on its own address
([ADR 0008](0008-generated-api-types.md), `src/api/client.ts`). During
development, Vite's server passes those requests on to the API, so the API
needs no CORS. Once the page is built, something else has to serve its files
and pass `/api` on.

## Decision

- **Two images.** `backend/Dockerfile` runs the API with uvicorn;
  `frontend/Dockerfile` builds the page with Node and serves the built files
  with nginx. Both are built in two stages, so the final images have neither
  the build tools nor the source code.
- **nginx passes `/api/` on to the API**, without the `/api`, as Vite's server
  does (`frontend/nginx.conf`). The page and the API keep one address, so the
  page does not change and the API still needs no CORS.
- **No root.** The API runs as its own user, and nginx comes from
  `nginxinc/nginx-unprivileged`, which runs as a user with no special rights.
  `compose.yaml` also makes the containers' files read-only and drops the
  Linux capabilities they do not need.
- **`compose.yaml` runs the images a server would run**:
  `docker compose up --build` starts the game at <http://localhost:8080>. Only
  the page's port is published, and only to the computer itself; the API is
  reached through nginx. For development, the API and the page still run
  without Docker, with uvicorn's `--reload` and Vite's server.
- **A `Docker` job in CI** builds both images on every pull request, starts
  them, and asks nginx for the page, the decks and a new match.

## Alternatives considered

- **The API also serves the page's files.** One image instead of two, but the
  frontend would live inside the backend, Python serves files more slowly
  than nginx, and a change to the CSS would mean building the API again.
- **The page and the API on two addresses.** The API would need CORS, one more
  security setting to get right, and `client.ts` would need to know the API's
  address, which differs between development and the server.
- **nginx's main image.** Better known, but its main process runs as root.
- **A Compose setup for development too**, with the code shared with the
  containers and reloaded on every change. More files and settings, and on
  Windows, changes made through WSL are not always seen quickly. The current
  development setup already works.
- **Only build the images in CI.** Faster, but a wrong `nginx.conf` or a
  container that cannot reach the other would still build.

## Consequences

- One command starts the whole game on any computer with Docker, and the same
  images can be deployed.
- `nginx.conf` is one more file to understand. It mirrors the proxy in
  `vite.config.ts`, so a change to how the page reaches the API changes both.
- The API still runs as one process, since matches are kept in its memory;
  more processes wait for the database (#55).
- The images follow tags such as `python:3.14-slim-trixie`, which get security
  fixes but can change between two builds. Pinning them to an exact digest,
  with a bot that updates it, is left for later.
- The `Location` header of a new match still lacks the `/api` (#54).
