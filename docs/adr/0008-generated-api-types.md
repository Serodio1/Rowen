# ADR 0008: Keep the OpenAPI document and the generated API types in the repository

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

[ADR 0001](0001-web-full-stack-architecture.md) decided that the frontend's
types are generated from the API's OpenAPI schema, so that the browser's code
and the API agree on every path and every field. FastAPI writes that schema
from the endpoints and the Pydantic models. What was left open is where the
document and the generated types live, when they are generated, and what calls
the API from the browser.

The forces: an API change should be visible in the pull request that makes it,
together with what it changes for the frontend; the frontend should build
without Python or a running server (in CI, and later in its Docker image); and
a stale copy must not go unnoticed.

## Decision

- **`backend/openapi.json` is in the repository.** `rowen.api.openapi` writes
  it (`uv run python -m rowen.api.openapi`, in `backend`), and a backend test
  fails while it differs from the document the API makes.
- **`frontend/src/api/schema.d.ts` is in the repository too.**
  `npm run generate:api` generates it from `backend/openapi.json` with
  openapi-typescript and formats it with Prettier. A `Check API types` step in
  the `Frontend` CI job generates it again and fails if the result differs
  from the committed file.
- **openapi-fetch** calls the API. It is a small client that takes the
  generated types, so a wrong path or method, a missing field or a field of
  the wrong type is a TypeScript error. `createApi()` in `src/api/client.ts`
  makes one, and tests give it a fake `fetch`.
- Each endpoint is named after its function in the document (`create_match`
  rather than FastAPI's `create_match_matches_post`), which the generated
  types use.

## Alternatives considered

- **Generate the types when the frontend builds**, from the backend or a
  running server. Nothing generated would be committed, but the frontend could
  not build without Python, and a pull request would not show what an API
  change does to the types.
- **Commit only `openapi.json` and generate the types in CI.** One generated
  file fewer, but the types the code is checked against would not be visible
  in the repository or in the editor before running the generator.
- **Write the types by hand.** No tools, but they drift from the API without
  anything noticing.
- **A generator that also writes the client**, such as `@hey-api/openapi-ts`.
  It writes much more code, and it is still before its 1.0 release, with
  frequent breaking changes. openapi-typescript and openapi-fetch keep the
  generated part to types.

## Consequences

- A pull request that changes the API also changes `openapi.json` and
  `schema.d.ts`, so reviewers see both. `.gitattributes` marks them as
  generated, so GitHub collapses them in the diff.
- An API change takes two more commands. The backend test and the CI step say
  which one was forgotten.
- A Pydantic or FastAPI upgrade, or a new version number of the project, can
  change `openapi.json`: the test catches it, and the file is written again.
- openapi-typescript 7.13 asks for TypeScript 5. An `overrides` entry in
  `package.json` lets it use the project's TypeScript 6.0, with which it
  generates the same file. It cannot run on TypeScript 7, whose package no
  longer has the compiler API that openapi-typescript builds the file with,
  so moving to TypeScript 7 also waits for openapi-typescript.
- openapi-fetch turns tuples into arrays in the types of responses (such as
  the two `players` of a view). Code that reads responses uses the types the
  client returns (`MethodResponse`), not the schema's types.
