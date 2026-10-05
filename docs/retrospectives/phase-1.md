# Phase 1 retrospective: the game engine

Phase 1 ends with the first release, `v0.1.0`. It ran from 28 September to
5 October 2026, in 29 pull requests, and also covers the foundations of
Phase 0: the rules, the tooling and CI. This document looks back at what was
built, which decisions shaped it and why, and what to change next.

## What was built

| Part | What it does |
|---|---|
| Rules ([`rules.md`](../rules.md), [`cards.md`](../cards.md)) | The rules, approved before any engine code, and two decks (Humans and Robots, 33 cards each). Eight rule questions were decided by Rui and logged as D1–D8. |
| Engine (`rowen.engine`) | Every MVP rule: cards loaded from JSON and validated, a seeded setup with redraw, turns, passing, rounds and scoring, every ability and special card, and what each player may see. |
| AI (`rowen.ai`) | A baseline opponent that tries each legal move in the engine and plays the best one. |
| CLI (`rowen.cli`) | A full match against the AI in the terminal: `uv run rowen`. |
| Tooling | uv, ruff, mypy in strict mode, pytest with coverage, Hypothesis and import-linter, all run by GitHub Actions on every push and pull request. |

## Decisions and why

The full reasoning is in the [ADRs](../adr/README.md). In short:

- **A web application, not a desktop game** (ADR 0001). The project is a
  portfolio for full-stack roles, so it needs an API, a database and a browser
  client.
- **The server runs the game** (ADR 0002). Clients hold no rules: the engine
  works out strengths, scores and legal moves, and a client only shows them.
  The CLI is the first client built this way; the web frontend will be the
  second.
- **A pure, immutable, deterministic engine** (ADR 0003). The game is driven by
  two functions, `legal_actions(state)` and `apply(state, action)`, and `apply`
  returns a new state instead of changing the old one. All randomness comes
  from a seed stored in the state. This kept the tests short, gave the AI
  look-ahead for free, and lets any match be replayed from its seed and its
  actions.
- **Architecture rules checked by CI.** Import-linter contracts, written as
  allow lists, keep the engine free of I/O and third-party packages, let the
  AI import only the engine, and let the CLI import only the parts of the
  engine it needs.
- **The AI asks the engine** (ADRs 0005 and 0006). A formula for each kind of
  card would repeat the rules. Instead, the AI imagines the match from its own
  player view, with an unknown card for each hidden card, and tries each move
  with `apply`, so a new card needs no change to the AI. Once the opponent has
  passed, the AI plays out the rest of the round in the imagined match before
  it chooses.

Smaller choices in the code:

- **Tables for abilities and special cards** (`ON_PLAY`, `EFFECTS`). A new
  ability is one function and one entry in a table, and the code that looks it
  up does not change. Spy, Muster and Medic were each added this way, in their
  own pull request.
- **Hidden information by allow list.** `player_view` and `player_events`
  build their own types and copy only what a player may see, so a new field in
  the game state stays hidden until someone decides to show it. The seed stays
  secret too, because it gives away the order of every deck.
- **Pending choices live in the state.** After a Medic, the state records that
  a unit is to be revived, and `legal_actions` offers only `Revive` actions, so
  the choice goes through `apply` like any other move.
- **Find first, then change.** Wildfire finds every unit to destroy before it
  destroys any, so a Bond unit that would get weaker once another one goes is
  still destroyed.
- **Exhaustive `match` statements on events.** When a new kind of event is
  added, mypy reports every `match` that doesn't handle it yet, in the player
  view and in the CLI.

## Testing

- **398 tests, covering 100% of statements and branches.** CI fails below
  100% (`fail_under`), so new code arrives with its tests.
- **Unit tests for every rule**, built on small, hand-made game states.
- **Invariants on random matches**, with Hypothesis: no card is ever lost or
  duplicated, every score equals the sum of its units, Legends keep their
  strength, lives never go up, a player's view shows the size of the
  opponent's hand but never its cards or the random number generator, and
  every match ends.
- **Mutation testing by hand.** On many pull requests, a script broke the code
  on purpose, one change at a time, and checked that a test failed. A change
  that no test caught either got a new test or was shown to make no difference.
- **The AI was measured.** Versions of the AI played thousands of seeded
  matches against each other. The AI in this release wins 68.8% of the
  decisive matches against the version before it.

## What went well

- **Rules before code.** The rules were written and approved first, so the
  engine was built against a fixed target. Questions that came up while coding
  (D7 and D8) were decided and logged, not guessed in the code.
- **Immutability paid off.** The AI's look-ahead, the Hypothesis tests and the
  player view all rely on states that never change.
- **Small pull requests.** Each one was explained, reviewed and understood
  before it was merged.
- **Rules of the architecture as failing checks.** The import contracts and the
  coverage threshold catch in CI what would otherwise depend on someone
  noticing in a review.

## What could be better

- **No pre-commit hooks.** They were planned for Phase 0 and never added. CI
  runs the same checks, but only after a push.
- **A gap in the CLI contract.** The CLI imports `rowen.engine.game` to start a
  match and apply moves, and that module also holds `legal_actions`. The
  contract can't stop the CLI from calling it, so only review does.
- **The AI only guesses the hidden cards.** It treats them as unknown cards, so
  it misjudges a Muster, which calls no units from the deck in the imagined
  match, and the cards a Spy draws. Its play-out is greedy, its weights were
  chosen by hand, and decks with several Medics would need a limit on its
  search (ADR 0006).
- **Small seeds in the CLI.** The CLI picks seeds below 1,000,000. From the
  opening hand, a seed that small can be found by trying every one, and with it
  the AI's hand. In the terminal, a player who did that would only cheat
  themselves, but online the seed has to be large and secret.
- **PR descriptions can close issues.** A description that mentioned "the
  second PR, which closes #21" closed the issue when the first of the two PRs
  was merged. Descriptions now say "Part of #N" until the last PR.

## Next

- **Phase 2:** large, secret seeds (for example, `secrets.randbits(64)`),
  never sent in a response or an event.
- **Phase 2, to decide:** a public engine module with only `start_match`,
  `apply`, `player_view` and `player_events`, for the API and the CLI. It
  would close the gap in the CLI contract.
- **To decide:** whether to add pre-commit hooks.
- **Phase 3:** a note on the license of the card art, planned in Phase 0, when
  the first images are added.
