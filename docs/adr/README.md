# Architecture Decision Records

An architecture decision record (ADR) is a short document that captures one
significant decision: the situation that required it, what was decided, which
alternatives were rejected and what follows from it. Together they explain *why*
the code looks the way it does, which the code itself cannot tell you.

The format follows Michael Nygard's
[original proposal](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
plus a section on the alternatives that were considered.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-web-full-stack-architecture.md) | Build Rowen as a full-stack web application | Accepted |
| [0002](0002-server-authoritative-game.md) | Run the game on the server | Accepted |
| [0003](0003-pure-immutable-engine.md) | Keep the engine pure, immutable and deterministic | Accepted |
| [0004](0004-monorepo-with-uv.md) | Use a monorepo and manage the backend with uv | Accepted |
| [0005](0005-ai-tries-moves-in-the-engine.md) | Let the AI judge each move by trying it in the engine | Superseded by ADR 0006 |
| [0006](0006-ai-plays-out-passed-rounds.md) | Let the AI try moves in the engine, and play out passed rounds | Accepted |
| [0007](0007-frontend-tooling.md) | Use npm, ESLint and Prettier for the frontend, and guard against malicious packages | Accepted |
| [0008](0008-generated-api-types.md) | Keep the OpenAPI document and the generated API types in the repository | Accepted |
| [0009](0009-docker-images-behind-nginx.md) | Run the game in two Docker images, with nginx in front of the API | Accepted |
| [0010](0010-deploy-on-cloud-run.md) | Deploy the game on Google Cloud Run, nginx and the API in one service | Accepted |
| [0011](0011-limit-requests-per-address.md) | Limit the API's requests per visitor's address, in nginx | Accepted |
| [0012](0012-deploy-from-ci.md) | Deploy from CI on every merge, signed in to Google with no stored key | Accepted |
| [0013](0013-keep-matches-in-postgresql.md) | Keep each match in PostgreSQL as its seed and actions | Accepted |
| [0014](0014-accounts-with-sessions-in-postgresql.md) | Log players in with Argon2id passwords and sessions kept in PostgreSQL | Accepted |
| [0015](0015-players-own-their-matches.md) | Give a logged-in player's matches an owner, keep their results and list them by cursor | Accepted |
| [0016](0016-check-a-revision-before-it-gets-the-requests.md) | Check a new revision before it gets the requests, built from fixed base images | Accepted |
| [0017](0017-keep-a-copy-of-a-built-deck-in-each-match.md) | Keep a copy of a player's built deck in each match they play with it | Accepted |
| [0018](0018-monte-carlo-ai-guesses-the-hidden-cards.md) | Let a Monte Carlo AI guess the hidden cards | Accepted |
| [0019](0019-faction-passives-belong-to-the-deck.md) | Give each faction a passive, kept with its deck and carried out by the engine | Accepted |

## Writing a new ADR

1. Copy [`template.md`](template.md) to `NNNN-short-title.md`, using the next
   free number.
2. Fill it in and add it to the index above.
3. Open a pull request. The ADR is `Accepted` once it is merged.

An accepted ADR is not rewritten. When a decision changes, write a new ADR that
replaces it and set the old one's status to `Superseded by ADR NNNN`, so the
history of the decision stays readable.
