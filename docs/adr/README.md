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

## Writing a new ADR

1. Copy [`template.md`](template.md) to `NNNN-short-title.md`, using the next
   free number.
2. Fill it in and add it to the index above.
3. Open a pull request. The ADR is `Accepted` once it is merged.

An accepted ADR is not rewritten. When a decision changes, write a new ADR that
replaces it and set the old one's status to `Superseded by ADR NNNN`, so the
history of the decision stays readable.
