# Tutorial, PR 1: the script and the recorded match — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the tutorial's script in the backend and record it, played by the real engine, into `frontend/src/tutorial.json`, with a test that fails when the file is out of date.

**Architecture:** A new module `rowen.api.tutorial` holds the script (13 steps), a fixed seed, and a generator that plays the match with `start_match` and `apply` and writes, for each step, the player's view and the moves played after it, in the API's own JSON shapes (`schemas.py`). It is written like `rowen.api.openapi`: `document()` returns the text, `main()` writes the file, and a test compares the two.

**Tech Stack:** Python 3.14, Pydantic (the API's `schemas.Schema`), pytest.

**Spec:** `docs/superpowers/specs/2026-11-03-tutorial-design.md`

## Global Constraints

- The rules stay in the engine (ADR 0002): the generator decides nothing; every action goes through `apply`.
- The API imports from the engine only `rowen.engine.public` (import-linter contract); `rowen.data` is allowed, as `app.py` already does.
- The player is player 0, the Humans' deck; the AI is player 1, the Robots' deck; the player starts round 1.
- Each step's recorded view has exactly the asked action in `legal_actions`, or none on a Next step.
- The texts are the spec's, in English; card names in them must match the cards the seed deals.
- Coverage stays at 100% (`uv run pytest --cov`); `main()` is covered as in `test_api_openapi.py`.
- `frontend/src/tutorial.json` is written with `"\n"` line ends (`newline="\n"`), as `openapi.json` is.
- Commits in Conventional Commits, ending with `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Review Focus

1. **A step's card is not in the hand at that step** (the seed dealt another card): the generator must fail with a message naming the step, not record a balloon pointing at nothing — test in Task 2.
2. **The AI's hand leaks into the file:** the recorded view must be `player_view(state, 0)`, never the state — test in Task 2.
3. **The redraw phase** before round 1: both players end it without swaps, and it is not a step the player sees — test in Task 2.
4. **The Robots' passive** keeps a unit on the AI's side for round 2: round 2 must still be won by the player — test in Task 2 (the winner and the round count).
5. **The file goes stale** after a rule or card change: the up-to-date test fails with the command to run — test in Task 3.

---

### Task 1: The script's shapes and the seed search

**Files:**
- Create: `backend/src/rowen/api/tutorial.py`
- Test: `backend/tests/test_api_tutorial.py`

**Interfaces:**
- Produces:
  - `Target = str`: one of `"rows"`, `"hand"`, `"total"`, `"lives"`, `"leader"`, `"discard"`, `"weather"`, `"row:<melee|ranged|siege>"`, `"card:<card id>"`.
  - `@dataclass(frozen=True) class ScriptStep: text: str; target: Target; action: engine.Action | None; ai: tuple[engine.Action, ...] = ()` — `action` is the player's asked action (`None` on a Next step); `ai` are the AI's actions played after it.
  - `SCRIPT: tuple[ScriptStep, ...]` — the spec's 13 steps, round 1 and round 2, with the spec's texts.
  - `SEED: int` — found once by the search below, then fixed.
  - Pydantic: `class TutorialStep(schemas.Schema): text: str; target: str; view: schemas.PlayerView; moves: tuple[schemas.MovePlayed, ...]` and `class Tutorial(schemas.Schema): steps: tuple[TutorialStep, ...]`.

- [ ] **Step 1: Find the seed (throwaway, not committed).** In a scratch script, loop over seeds from 0: `start_match((load_deck("humans"), load_deck("robots")), seed=s)` after both players' `EndRedraw()`; keep the first seed where player 0 is `current` and its hand holds `soldier`, `sniper`, `informant`, `clear-skies` and `medic`, and player 1's hand holds `hoarfrost`. Write it down as `SEED`.

- [ ] **Step 2: Write the script in `tutorial.py`**, with the spec's texts and the actions for that seed's hand (the AI's answers picked from player 1's hand at that point, as `PlayUnit`/`PlaySpecial`/`Pass`). The spec's card names (Soldier, Sniper, Informant, Clear Skies, Medic, Hoarfrost) stay as they are.

- [ ] **Step 3: Commit**

```bash
git add backend/src/rowen/api/tutorial.py
git commit -m "feat(api): write the tutorial's script"
```

### Task 2: The generator

**Files:**
- Modify: `backend/src/rowen/api/tutorial.py`
- Test: `backend/tests/test_api_tutorial.py`

**Interfaces:**
- Consumes: `SCRIPT`, `SEED`, `ScriptStep`, `Tutorial`, `TutorialStep` (Task 1); `schemas.from_view`, `schemas.from_events`, `schemas.MovePlayed`; `engine.start_match`, `apply`, `player_view`, `player_events`, `EndRedraw` from `rowen.engine.public`.
- Produces: `def generate(script: tuple[ScriptStep, ...] = SCRIPT, seed: int = SEED) -> Tutorial` and `class ScriptError(ValueError)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_each_step_lights_only_the_asked_action() -> None:
    for script_step, step in zip(SCRIPT, generate().steps, strict=True):
        asked = () if script_step.action is None else (from_action(script_step.action),)
        assert step.view.legal_actions == asked

def test_the_player_wins_the_match_in_two_rounds() -> None:
    last = generate().steps[-1].moves[-1].view
    assert last.match_over and last.winner == 0
    assert last.round == 2

def test_the_views_show_only_the_players_hand() -> None:
    for step in generate().steps:
        assert step.view.player == 0
        # The AI's side shows how many cards it holds, never which.
        assert "hand" not in step.view.players[1].model_dump()

def test_the_redraw_is_not_a_step() -> None:
    first = generate().steps[0].view
    assert first.round == 1 and first.current == 0
    assert not any(action.type == "end_redraw" for action in first.legal_actions)

def test_a_card_not_in_the_hand_fails_with_the_step() -> None:
    wrong = (replace(SCRIPT[0], target="card:president"),)
    with pytest.raises(ScriptError, match="step 1"):
        generate(wrong)

def test_an_illegal_action_fails_with_the_step() -> None:
    wrong = (replace(SCRIPT[2], action=PlayUnit(card="president", row=Row.SIEGE)),)
    with pytest.raises(ScriptError, match="step 1"):
        generate(wrong)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_api_tutorial.py -q`
Expected: FAIL, `generate` is not defined.

- [ ] **Step 3: Implement `generate`.** End the redraw for both players; then for each step: check a `card:` target is in the player's hand (else `ScriptError(f"step {n}: ...")`); record `from_view(view)` with `legal_actions` replaced by the asked action, if it is among the view's legal actions (else `ScriptError`); apply the player's action, then each AI action, each as a `MovePlayed(events=from_events(player_events(events, 0)...), view=from_view(player_view(state, 0)))`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_api_tutorial.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/rowen/api/tutorial.py backend/tests/test_api_tutorial.py
git commit -m "feat(api): record the tutorial's match from the engine"
```

### Task 3: The file, its up-to-date test and ADR 0020

**Files:**
- Modify: `backend/src/rowen/api/tutorial.py`
- Create: `frontend/src/tutorial.json` (generated)
- Create: `docs/adr/0020-the-tutorial-is-a-recorded-match.md`
- Modify: `docs/adr/README.md` (index row)
- Test: `backend/tests/test_api_tutorial.py`

**Interfaces:**
- Consumes: `generate()` (Task 2).
- Produces: `TUTORIAL_JSON: Path` (`frontend/src/tutorial.json`, `Path(__file__).parents[4] / "frontend" / "src" / "tutorial.json"`), `def document() -> str` (`generate().model_dump_json(indent=2) + "\n"`), `def main() -> None`.

- [ ] **Step 1: Write the failing tests**, as in `tests/test_api_openapi.py`:

```python
def test_tutorial_json_is_the_recorded_match() -> None:
    assert TUTORIAL_JSON.read_text(encoding="utf-8") == tutorial.document(), (
        "frontend/src/tutorial.json is out of date with the engine. In backend, "
        "run: uv run python -m rowen.api.tutorial"
    )

def test_main_writes_the_document(tmp_path, monkeypatch) -> None:
    written = tmp_path / "tutorial.json"
    monkeypatch.setattr(tutorial, "TUTORIAL_JSON", written)
    tutorial.main()
    assert written.read_bytes() == tutorial.document().encode()
```

- [ ] **Step 2: Implement `document()` and `main()`**, with the `if __name__ == "__main__":  # pragma: no cover` guard, and generate the file: `uv run python -m rowen.api.tutorial`.

- [ ] **Step 3: Write ADR 0020** from `docs/adr/template.md`: the context (#159, a recruiter has seconds), the decision (a recorded match played back in the page, the table of the spec's decisions), the options set aside (a scripted match on the server, a "How to play" page), the consequences (no API calls or cost; a stale file fails CI; the page gets a second mode of the board, in PR 2). Add its row to `docs/adr/README.md`.

- [ ] **Step 4: Run the whole backend check, as the CI does**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run lint-imports && uv run pytest --cov -q`
Expected: all pass, coverage 100%. Report the size of `frontend/src/tutorial.json` (`wc -c`) in the PR.

- [ ] **Step 5: Commit**

```bash
git add backend frontend/src/tutorial.json docs/adr
git commit -m "feat(api): write the recorded tutorial to frontend/src/tutorial.json"
```
