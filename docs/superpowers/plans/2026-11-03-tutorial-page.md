# Tutorial, PR 2: the page that plays the recorded match — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A **Tutorial** button on the main menu opens a screen that plays `frontend/src/tutorial.json` on the real board, one step at a time, with a floating balloon beside each step's target, until "Tutorial complete".

**Architecture:** The page never calls the API. `tutorial.ts` loads the recording lazily and gives its types; `Balloon.tsx` positions a balloon with an arrow next to an element found by `data-tutorial`; `Board.tsx` gets those attributes; `Tutorial.tsx` is the screen: it shows each step's `view` on `Board`, lets the player make only the lit move (the recorded legal actions), plays the step's `moves` with the existing animations (`stage.ts`), and moves on. `App.tsx` adds the button and the way back.

**Tech Stack:** React 19, TypeScript 6 strict, Tailwind 4, `@floating-ui/react-dom` 2.1.9 (new), Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-03-tutorial-design.md`

## Global Constraints

- No API call from the tutorial: nothing in `Tutorial.tsx` uses `Api`, TanStack Query or `fetch`.
- The page decides no rule (ADR 0002): the lit move is the recorded `view.legal_actions`; boards and totals come from the recording.
- `tutorial.json` is loaded with a dynamic `import()` only when the tutorial opens.
- `@floating-ui/react-dom` at exactly `2.1.9` (published 2026-07-11, older than `min-release-age=14`); only `useFloating`, `offset`, `flip`, `shift`, `arrow`, `autoUpdate`.
- Targets, as the backend writes them: `rows`, `hand`, `total`, `lives`, `leader`, `ai-leader`, `discard`, `weather`, `row:<melee|ranged|siege>`, `card:<card id>`; each is a `data-tutorial` attribute with that exact text.
- The balloon's text also goes to a `role="status"` region; the Next button takes the focus.
- Texts on the page in English: **Tutorial**, **Next**, **Leave tutorial**, "Tutorial complete", **Play a match**, **Return to main menu**.
- `console.error` fails a Vitest test (the project's setup); ESLint `strictTypeChecked`; Prettier.
- Commits in Conventional Commits, ending with `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Review Focus

1. **A step's target is not in the page** (an attribute forgotten in `Board`, or a card the hand doesn't show): the balloon must not crash or float at (0, 0) — test in Task 3 that every step's target exists, and in Task 1 that a missing target renders the text in the status region with no balloon.
2. **A click during the animation** of the AI's moves: nothing must happen, and the next step must not start twice — test in Task 3.
3. **Reduced motion:** with `prefers-reduced-motion`, there is no animation, and the step must still advance — test in Task 3 (`mayMove()` false).
4. **Leaving in the middle of an animation:** back to the menu with no error and no timer left running (`console.error` would fail the test) — test in Task 4.
5. **Small screens:** the balloon stays on screen (`flip`, `shift`) — checked in the Playwright test at a phone size in Task 4.

---

### Task 1: The dependency and the balloon

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`
- Create: `frontend/src/Balloon.tsx`, `frontend/src/Balloon.test.tsx`

**Interfaces:**
- Produces: `export function Balloon(props: { target: string; text: string; onNext?: () => void }): JSX.Element` — finds `document.querySelector(`[data-tutorial="${target}"]`)`, attaches a floating panel with an arrow (`placement: "top"`, `offset(12)`, `flip()`, `shift({ padding: 8 })`, `arrow`), `whileElementsMounted: autoUpdate`; scrolls the target into view (`scrollIntoView({ block: "nearest" })`) before showing; renders `text` and, when `onNext` is given, a **Next** button that takes the focus. The text is also in a `role="status"` element (visually hidden), so screen readers read it even when no target is found; without a target, no floating panel is shown.

- [ ] **Step 1:** `npm install @floating-ui/react-dom@2.1.9 --save-exact` in `frontend` (the `.npmrc` rules apply; no `--min-release-age=0` needed).
- [ ] **Step 2: Write the failing tests** (`Balloon.test.tsx`): renders the text in `getByRole("status")`; with `onNext`, clicking **Next** calls it once and the button has the focus; with a target element in the document, a `role="dialog"` or `role="note"` panel (pick one, say which) shows the text; with no matching element, there is no panel and the status still has the text.
- [ ] **Step 3: Run them to see them fail:** `npx vitest run src/Balloon.test.tsx` — FAIL, module not found.
- [ ] **Step 4: Implement `Balloon`.** Styling with the existing tokens in `styles.ts`/`index.css` (gold border, dark wood background, like the end-of-match window).
- [ ] **Step 5: Run them:** PASS; `npm run lint`, `npm run typecheck`, `npm run format:check`.
- [ ] **Step 6: Commit:** `feat(frontend): add the tutorial's balloon`.

### Task 2: The targets on the board

**Files:**
- Modify: `frontend/src/Board.tsx`
- Test: `frontend/src/Board.test.tsx`

**Interfaces:**
- Produces: `data-tutorial` on: the player's three rows together (`rows`); each of the player's rows (`row:melee`, `row:ranged`, `row:siege`); the hand (`hand`); each card button in the hand (`card:<id>`, the first copy only when there are several); the player's total (`total`); the player's lives (`lives`); the player's leader (`leader`); the AI's leader (`ai-leader`); the player's discard pile (`discard`); the weather (`weather`).

- [ ] **Step 1: Write the failing test** `every tutorial target is on the board`: render `Board` with `test-data.ts`'s view and assert `container.querySelector('[data-tutorial="<t>"]')` is not null for each fixed target above, and for `card:<id>` of the first card in the hand; two copies of a card give one `card:` attribute.
- [ ] **Step 2: Run it:** FAIL.
- [ ] **Step 3: Add the attributes** on the existing elements (no new wrappers unless a target has no element; then say which).
- [ ] **Step 4: Run** `npx vitest run src/Board.test.tsx` — PASS; lint, typecheck, format.
- [ ] **Step 5: Commit:** `feat(frontend): mark the board's places for the tutorial`.

### Task 3: The tutorial screen

**Files:**
- Create: `frontend/src/tutorial.ts`, `frontend/src/Tutorial.tsx`, `frontend/src/Tutorial.test.tsx`

**Interfaces:**
- Consumes: `Balloon` (Task 1); the targets (Task 2); `Board`, `Playing` (`plays.ts`), `stepsOfMoves`, `usePlayOut`, `stageOf`, `viewAt`, `mayMove` (`stage.ts`), the `Rounds` table and the end window's look from `App.tsx` (move `Rounds` to its own export if needed, without changing it).
- Produces:
  - `tutorial.ts`: `export interface TutorialStep { text: string; target: string; view: View; moves: Played["moves"] }`, `export interface Tutorial { steps: TutorialStep[] }`, `export function loadTutorial(): Promise<Tutorial>` (`import("./tutorial.json")`, typed with `View`/`Played` from `api/client.ts`).
  - `Tutorial.tsx`: `export function Tutorial(props: { onLeave: () => void; onPlay: () => void }): JSX.Element`.

Behaviour:
- While loading, "Loading the tutorial…"; then step 0.
- A step shows `step.view` on `Board`, with `playing.actions = step.view.legal_actions` (one action, or none), `disabled` while an animation plays, and the balloon (`Balloon`, with `onNext` only when there is no action).
- `onPlay(action)` (the only lit action) or **Next**: play `step.moves` with `stepsOfMoves(step.moves, …)` and `usePlayOut` (no animation when `mayMove()` is false), then go to the next step; the board shows each move's view as the animation reaches it (`viewAt`).
- **Leave tutorial** is always shown and calls `onLeave`.
- After the last step's moves, when the last view has `match_over`: the end window, "Tutorial complete", the `Rounds` table from the `round_ended` events of the moves, and **Play a match** (`onPlay`) and **Return to main menu** (`onLeave`).

- [ ] **Step 1: Write the failing tests** (`Tutorial.test.tsx`, with the real `tutorial.json`; `mayMove` false through `matchMedia` as the other tests do): the first balloon's text is the first step's; only the asked card is enabled at step 3 (`card:soldier`), and the other hand cards are disabled; clicking it moves to step 4's text; **Next** moves on; a second click during an animation does nothing (with `mayMove` true and fake timers); playing all steps (a helper that clicks the lit button or Next) ends with "Tutorial complete" and both buttons, calling `onPlay`/`onLeave`; **Leave tutorial** calls `onLeave`; every step's target exists in the page when the step shows (loop over all steps with the helper).
- [ ] **Step 2: Run them:** FAIL.
- [ ] **Step 3: Implement** `tutorial.ts` and `Tutorial.tsx`, reusing the board's layout from `PlayMatch` (board, then controls) without copying its API code.
- [ ] **Step 4: Run** `npx vitest run src/Tutorial.test.tsx` — PASS; lint, typecheck, format, `npm run build` (report the size of the tutorial's chunk).
- [ ] **Step 5: Commit:** `feat(frontend): play the recorded tutorial on the board`.

### Task 4: The menu button and the browser test

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
- Create: `frontend/e2e/tutorial.spec.ts`

**Interfaces:**
- Consumes: `Tutorial` (Task 3).

- [ ] **Step 1: Write the failing tests** (`App.test.tsx`): the main menu has a **Tutorial** button; clicking it shows the tutorial's first balloon and no API call is made (the fake API's call log is unchanged); **Leave tutorial** goes back to the menu with the focus as after leaving a match; at the end, **Play a match** shows the decks to choose and **Return to main menu** the menu; leaving in the middle of an animation logs no error.
- [ ] **Step 2: Run them:** FAIL.
- [ ] **Step 3: Implement** in `App.tsx`: a `tutorial` state next to `match`; the button beside the deck choice; the screen in the match's place; nothing saved.
- [ ] **Step 4: Write `e2e/tutorial.spec.ts`:** open the page, click **Tutorial**, play every step (click the lit card/row/button or **Next**), see "Tutorial complete"; once more at 390×844, checking each balloon's box is inside the viewport.
- [ ] **Step 5: Run** `npx vitest run` (all), lint, typecheck, format, build; the e2e with the local config (`frontend/pw.local.config.ts`, deleted afterwards) against `npx vite`.
- [ ] **Step 6: Commit:** `feat(frontend): open the tutorial from the main menu`.
