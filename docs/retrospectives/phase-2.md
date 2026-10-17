# Phase 2 retrospective: playable online

Phase 2 ends with the release `v0.2.0`. It ran from 12 to 17 October 2026,
in 24 pull requests (#58 to #81). At the end of it, anyone with the link can
play a whole match against the AI in the browser, with nothing to install, and
a match being played survives a restart of the server and a new deployment.
This document looks back at what was built, which decisions shaped it and why,
and what to change next.

## What was built

| Part | What it does |
|---|---|
| Web API (`rowen.api`) | FastAPI endpoints to list the decks, start a match against the AI, read the player's view and play a move. The AI answers before the server responds. Errors are always a `code` and a `message`. |
| Match store | Each match is kept as its decks, seed, actions and version, in PostgreSQL (or in memory, to run the API alone). The API plays the actions again on each request. Tables are made by Alembic migrations. |
| Frontend (`frontend/`) | A React and TypeScript page: choose a deck, see the board, play a move, and read what happened. The look is drawn with CSS (Tailwind CSS), with no art from the original game. |
| API contract | The API's OpenAPI document is kept in the repository, and the frontend's TypeScript types are generated from it. |
| Docker | Two images, nginx serving the page in front of the API, and Docker Compose running the whole game with PostgreSQL. |
| Online | Google Cloud Run, with nginx and the API in one service; the database on Neon's free plan. nginx limits the requests of each visitor. |
| CD | Every merge to `main` builds the images, migrates the database, deploys and checks the game online, signed in to Google with no stored key. |

## Decisions and why

The full reasoning is in the [ADRs](../adr/README.md), 0007 to 0013. In short:

- **Guard the frontend against malicious packages** (ADR 0007). npm installs
  only versions published at least 14 days earlier and never runs the install
  scripts of packages. Most malicious releases are found and removed within
  days, so they never reach the project.
- **The API's contract is generated, not written twice** (ADR 0008). The
  OpenAPI document comes from the API's own types, and the frontend's types
  from that document. A backend test fails when the document is out of date,
  and CI fails when the generated types are, so the two sides can't drift
  apart.
- **nginx in front of the API** (ADR 0009). The browser reaches one address:
  nginx serves the page and passes `/api` on to the API. The page and the API
  share an origin, so there is no CORS to configure, and the security headers
  are set in one place.
- **Cloud Run, with both containers in one service** (ADR 0010). It costs
  nothing at this traffic and stops when nobody plays. nginx and the API run
  side by side and talk over `127.0.0.1`, as they do in Docker Compose.
- **Limits per visitor, in nginx** (ADR 0011). Anyone can start a match, so
  nginx limits each address: 5 requests a second, and 10 new matches a
  minute. An IPv6 visitor is counted by their /64 block, since one connection
  can have many addresses in it.
- **Deploy from CI with no stored key** (ADR 0012). GitHub signs a short-lived
  token for each run, and Google trusts it only for this repository, its
  `production` environment and the `main` branch. There is no password or key
  file to leak.
- **A match is its seed and its actions** (ADR 0013). The engine is
  deterministic, so the API keeps the decks, the seed and every action, and
  plays them again on each request (a millisecond or two). Turning a whole
  game state into JSON and back would have been much more code. PostgreSQL
  runs on Neon's free plan, in Frankfurt, near Cloud Run's region; Cloud SQL
  would have cost every month.

Smaller choices in the code:

- **One public module for the engine** (`rowen.engine.public`). The API and
  the CLI import the engine only through it, an import-linter contract
  checks it, and so the gap in the CLI contract from Phase 1 is closed.
- **The API's own JSON shapes.** Pydantic models are filled in field by field
  from the player's view, as an allow list, so a new field in the engine
  never reaches a player by accident. Every field is required, so the
  generated TypeScript types have no optional fields to forget.
- **A version on each match** (optimistic locking). Each move says which
  version of the match it was chosen from, and the database adds it with
  `UPDATE ... WHERE id = :id AND version = :version`. A move that arrives late,
  after the browser gave up on it and the player played again, is turned down
  with a 409 instead of being played twice.
- **The seed stays secret.** It is 63 random bits from the operating system
  (`secrets`), and no response or event contains it: whoever knew it could
  work out the AI's hand.
- **Least privilege throughout.** The containers run as users with no root
  rights (in Docker Compose, also on read-only file systems with no extra
  capabilities). The service account the game runs as
  has no roles but reading one secret, and the database user the API uses
  can only read, add and change matches, not change the tables.
- **Migrations before the deployment.** CI brings the database up to date
  before the new version goes online. If a migration fails, nothing is
  deployed, and the version already online keeps working.

## Testing

- **630 backend tests, covering 100% of statements and branches**, as in
  Phase 1. The tests of the PostgreSQL store run against a real PostgreSQL
  in CI; with 100% required, CI fails if they are ever skipped there.
- **The same tests for both stores.** The store in memory and the store in
  PostgreSQL pass the same tests, including two requests racing to play from
  the same version, made deterministic by holding a lock on the row.
- **134 frontend tests**, with Vitest and Testing Library, written against what
  a player sees and does (roles and labels, not CSS classes). Any
  `console.error` fails a test.
- **A smoke test of the real images.** CI builds the Docker images, starts the
  game with Docker Compose and plays a whole match through nginx with `curl`.
  It also checks the security headers and the limits, resends a move to get
  `match_changed`, and restarts the API in the middle to check that the match
  is still there.
- **A check online after each deployment.** CI starts a match on the live
  site and reads it back from the database.
- **Mutation testing by hand,** as in Phase 1. The larger pull requests were
  also reviewed by several independent AI reviewers, and each finding was
  checked before it was fixed.
- **The survival of a match, checked by hand online.** A match was started,
  a new revision was deployed with all the traffic, and the same match went on.

## What went well

- **A walking skeleton first.** The first page was plain text, but it played a whole
  match through the real API. Each later pull request improved one layer of
  a game that already worked end to end.
- **The deterministic engine paid off again.** Keeping a match as its seed and
  actions was only possible because the same actions always give the same
  game, as ADR 0003 promised in Phase 1.
- **Generated types.** When the API changed, as when moves started carrying a
  version, the type checker showed every place in the frontend to update.
- **Production in CI.** The smoke test runs the same images as the server, so
  problems with nginx, the proxy or the database showed up in pull requests,
  not online.
- **No monthly cost.** Cloud Run, Artifact Registry and Neon stay within their
  free plans, with a budget alert at €1 and a cap at €2.

## What could be better

- **The first deployment from CI failed twice.** For repositories created
  after 15 July 2026, GitHub names them by ID in its tokens, and Google trusted
  the name. The fix and the reason are in `docs/deploy.md` (#77).
- **Running the workflow again is not a restart.** Deploying the same commit
  again changes nothing, so Cloud Run keeps the same revision. To check that a
  match survives, a new revision had to be deployed from Google's console.
- **The first visit after a quiet while is slow,** about 6 seconds, while Cloud
  Run starts the service. Keeping one instance running would cost every month.
- **A change to the rules can break a match being played.** Its actions are
  played again under the new rules, and if one is no longer legal, every
  request for it fails with a 500.
- **Nothing deletes old matches,** including those that CI's check starts
  online. At about 2 KB each, Neon's free 1 GB holds hundreds of thousands.
- **Neon's free plan can delete a project left idle for 90 days.**
- **The board and the moves don't fit on one screen,** and the page has not
  yet been tried with a screen reader (#69).
- **No test in a real browser.** The page is tested in jsdom, and the code that
  starts it, `main.tsx`, is not tested at all. Playwright comes in Phase 3.
- **The 14-day wait has a cost.** A fix for the Vite development server came
  out on 6 October, and the project only takes it from 20 October, like any
  other release.
- **The most important commands have to be pasted by hand.** Setting up Google
  Cloud and the database is a list of PowerShell commands in
  `docs/deploy.md`; long lines were cut when pasted, and a folder name with an
  accent broke one of them. Both are fixed in the document.

## Next

- **Phase 3:** the board and the moves on one screen, tested with a screen
  reader (#69); card art, with a note on its license; animations driven by the
  engine's events; and Playwright tests in a real browser.
- **Vite 8.3.3,** once it is 14 days old.
- **Later, to decide:** answering a match that can no longer be played with
  "not found" instead of a 500; deleting matches left alone for long; fewer
  round trips to the database per request, once the time online is measured.
- **Still to decide, from Phase 1:** whether to add pre-commit hooks.
