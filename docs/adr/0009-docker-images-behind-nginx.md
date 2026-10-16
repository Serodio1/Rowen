# ADR 0009: Run the game in two Docker images, with nginx in front of the API

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Phase 2 puts the game online. A server has none of what a developer's computer
has (Python 3.14, uv, Node 24, the dependencies), and setting it up by hand
would make the server and the computers drift apart. The plan and
[ADR 0001](0001-web-full-stack-architecture.md) count on Docker: when
everything runs in it, the game can move between hosting providers. ADR 0001
also expected Docker Compose for local development.

The page calls the API under `/api` on its own address (`src/api/client.ts`).
During development, Vite's server passes those requests on to the API, so the
API needs no CORS. Once the page is built, something else has to serve its files
and pass `/api` on.

## Decision

- **Two images.** `backend/Dockerfile` runs the API with uvicorn;
  `frontend/Dockerfile` builds the page with Node and serves the built files
  with nginx. Both are built in two stages, so the final images keep only
  what runs: no uv in the API's, no Node and no page source in the page's.
- **nginx passes `/api/` on to the API**, without the `/api`, as Vite's server
  does (`frontend/nginx.conf`). The page and the API keep one address, so the
  page does not change and the API still needs no CORS.
- **No root.** The API runs as its own user, and nginx comes from
  `nginxinc/nginx-unprivileged`, which runs as a user with no special rights.
  `compose.yaml` also makes the containers' files read-only, drops all Linux
  capabilities (neither needs one) and forbids gaining new rights
  (`no-new-privileges`).
- **`compose.yaml` runs the images a server would run**:
  `docker compose up --build` starts the game at <http://localhost:8080>. Only
  the page's port is published, and only to the computer itself; the API is
  reached through nginx. For development, the API and the page still run
  without Docker, with uvicorn's `--reload` and Vite's server. This changes
  what ADR 0001 expected: Compose runs the images a server would run, not a
  development setup.
- **A `Docker` job in CI** builds both images on every pull request, starts
  them, and through nginx asks for the page and its JavaScript, then plays a
  whole match with `curl` and reads it back.

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
  Windows, containers see changes to code on the Windows drive late or not at
  all, so `--reload` and Vite would have to poll for them. The current
  development setup already works.
- **Only build the images in CI.** Faster, but a wrong `nginx.conf` or a
  container that cannot reach the other would still build.
- **Play the match in a browser in CI** (Playwright). Closer to a player, but
  Playwright comes in Phase 3; `curl` already goes through nginx and the API.

## Consequences

- One command starts the whole game on any computer with Docker, and the same
  images can be deployed.
- `nginx.conf` is one more file to understand. It mirrors the proxy in
  `vite.config.ts`, so a change to how the page reaches the API changes both.
- The API still runs as one process, since matches are kept in its memory;
  more processes wait for the database (#55). The CI's match fails if a
  second process answers some of its moves.
- nginx looks up the API's address only when it starts, so Compose restarts
  nginx when the API's container is replaced (`restart: true`).
- The images follow tags such as `python:3.14-slim-trixie`, which get security
  fixes but can change between two builds. Pinning them to an exact digest,
  with a bot that updates it, is left for later.
- Behind nginx, the API does not know that it lives under `/api`: the
  `Location` header of a new match lacks it, and `/api/docs` cannot load
  `/openapi.json`. The page uses neither; both are fixed with the deployment
  (#54), together with the security headers that matter once the game is
  public.
