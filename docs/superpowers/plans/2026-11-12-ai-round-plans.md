# Round plans for the Hard AI: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Hard, compare three plans for the rest of the round (Minimal,
Give up, Wait) with the legal actions, and keep the change only if
`rowen-arena` measures it stronger.

**Architecture:** All in `rowen.ai.montecarlo`. A plan is a function
`(state, player) -> Action`. A candidate is a first action plus an optional
plan; `_play_out` follows the plan on the AI's turns for the rest of the
round, and `_next` everywhere else.

**Tech Stack:** Python 3.14, pytest, Hypothesis, `rowen-arena`.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-round-plans-design.md`

## Global Constraints

- The AI imports only `rowen.engine` and `dataclasses` (import-linter contract).
- Same view + same seed = same action.
- Easy and Normal unchanged; `_rule_of_thumb` and the baseline cases unchanged.
- Kept only if: new Hard beats current Hard by more than the margin (source
  decks and `docs/decks/spies.json`), doesn't lose to Easy; time judged by PR 2 (≤ 5–7 s online).
- Coverage 100 % (`uv run pytest --cov`).

## Review Focus

- A plan whose first move is Pass: same as the legal action Pass; the tie keeps the action.
- A plan when the opponent passes mid-round: the AI switches to `baseline.next_play`.
- A plan after a Medic (reviving): `_next` chooses the revive, not the plan.
- The round ends on the AI's own move: the plan stops at the next round.
- No plays left (empty hand): every plan passes.

---

### Task 1: Spike and measure (before tests)

Measuring first avoids writing tests for code that may not be kept.

**Files:** Modify `backend/src/rowen/ai/montecarlo.py`.

**Interfaces:** Produces `_minimal`, `_give_up`, `_wait: (GameState, int) -> Action`,
`PLANS`, and `_play_out(state, action, *, hard=False, plan=None) -> int`.

- [ ] Implement the three plans as in the spec's table; "gain" = the lead after
  the action (`baseline._lead_after`).
- [ ] In `choose_action`, with `hard`, add a candidate `(plan(imagine(view), me), plan)`
  per plan after the legal actions; return the winning candidate's first action.
- [ ] Copy `origin/main`'s `rowen.ai` to the scratchpad as the old Hard and run
  the arena (new vs old with the source decks and with `spies.json`; new vs Easy).
- [ ] If it fails the rule: stop, write the numbers into ADR 0018 and
  `docs/balance.md`, no code merged.

### Task 2: Tests

**Files:** Test `backend/tests/test_ai_montecarlo.py`.

- [ ] `test_minimal_plays_the_weakest_card_that_leads` (3 behind, cards 2/5/9 → 5).
- [ ] `test_minimal_passes_when_ahead`, `test_minimal_plays_the_best_when_none_leads`.
- [ ] `test_give_up_plays_a_spy` / `test_give_up_passes_without_one`.
- [ ] `test_wait_plays_the_cheapest_card`; every plan passes with an empty hand.
- [ ] `test_play_out_follows_the_plan_only_this_round` and only while the opponent plays.
- [ ] `test_hard_gives_up_a_lost_round` (well behind in round 1, a life to spare).
- [ ] Run `uv run pytest --cov`, ruff, mypy, lint-imports; mutations on the plans.

### Task 3: Docs and pull request

- [ ] ADR 0018 update and `docs/balance.md` with the measured numbers.
- [ ] Open the PR (Security / Efficiency / Regressions / Tests), remove the session link.
