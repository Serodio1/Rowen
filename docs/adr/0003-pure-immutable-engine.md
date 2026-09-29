# ADR 0003: Keep the engine pure, immutable and deterministic

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

The engine (`rowen.engine`) holds every rule of the game, and it is the part of
the code with the most edge cases: the order of strength modifiers, abilities
that interact, rounds that carry cards over. It will be used by the API, the AI
opponent, a terminal CLI and a headless simulator, and the Monte Carlo AI
(Phase 5) will simulate thousands of moves ahead.

That requires an engine that is easy to test in isolation, that can be
reused without the web stack, where simulating a move cannot corrupt the real
game, and where any bug can be reproduced exactly.

## Decision

1. **Pure.** `rowen.engine` depends only on the Python standard library and
   performs no I/O: no web, no database, no printing, no clock. The card
   definitions (JSON) are parsed once by a loader, and the rule functions only
   receive the resulting card objects; they never touch files.
2. **Enforced layering.** An import-linter contract, checked in CI, forbids
   `rowen.engine` from importing the API, the database layer, the AI or any
   third-party package, and allows the AI to depend only on the engine. The
   contract is added together with the engine package in Phase 1.
3. **Immutable state.** The game state is built from frozen dataclasses and
   tuples. It is never modified: every change produces a new state.
4. **Pure transitions.** The core API is two functions:
   - `legal_actions(state)` returns every action the player to move can take.
   - `apply(state, action)` returns `(new_state, events)`. The events describe
     what happened ("unit played", "strength changed", "round won"), so the
     frontend can animate them. An illegal action raises an error.
5. **Deterministic.** All randomness (shuffles, coin flip) comes from a random
   number generator whose state is stored in the game state, starting from a
   seed. The engine never uses the global `random` functions or the current
   time. The same seed and the same actions always produce the same match.

## Alternatives considered

- **Mutable object model** (`game.play(card)` changing `Player` and `Row`
  objects in place). Familiar and slightly faster, but changes are spread
  across many objects, so tests need more setup and checking; the AI must
  deep-copy the whole game before simulating a move; and an action that fails
  halfway can leave the game half-changed.
- **Rules inside the web layer** (in FastAPI endpoints, or in Pydantic or
  SQLAlchemy models). Quicker to start, but the rules could not be tested or
  reused by the CLI, the AI or the simulator without the web stack and the
  database, and changing framework would mean rewriting the rules.

## Consequences

- Tests are short: build a state, apply an action, check the result. Hypothesis
  can generate random sequences of legal actions and check invariants, for
  example that no card is ever lost or duplicated, that the score always equals
  the sum of the board, and that every match ends.
- Undo and AI look-ahead are free (keep the previous state). Replays and bug
  reports are cheap: the initial seed plus the list of actions rebuilds any
  match.
- Every action creates a new state object. The state is small (a few dozen
  cards per player), and `dataclasses.replace` reuses every part that did not
  change, so the cost is low. If the Monte Carlo AI turns out to be too slow,
  it is optimised later, based on measurements.
- Code that updates nested immutable data is more verbose than assigning to an
  attribute. Small helper functions keep it readable.
- Python cannot fully guarantee immutability (a frozen dataclass can still be
  bypassed), so the rule is kept by convention, `frozen=True`, tuple types and
  mypy in strict mode.
