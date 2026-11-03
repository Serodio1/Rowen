# Tutorial: a guided match — design

Issue: #159 (milestone v1.0.0). Approved in conversation on 3 November 2026.

## Goal

Someone who has never played, such as a recruiter opening the link, learns
enough to play a match in about three minutes: rows and strength, totals,
playing a unit, passing, rounds and lives, a Spy, weather and Clear Skies,
and a Medic. The tutorial is optional and never in the way of someone who
wants to play at once.

## Decisions

| Question | Decision |
|---|---|
| Format | A guided match: a short, always identical match on the real board |
| How it is reached | A **Tutorial** button on the main menu, optional |
| What it teaches | The essentials (above), in 2 rounds, about 3 minutes |
| How guided | Only the asked move: the other cards and rows are off |
| Where it runs | A recorded match, played back in the page: no API calls |
| Decks | The Humans' cards (the player) against the Robots' (the AI) |
| Explanations | Floating balloons with an arrow, beside the card or row |
| Positioning | `@floating-ui/react-dom` (positioning only) |
| Leaving | **Leave tutorial** at any time; at the end, **Play a match** and **Return to main menu**; nothing is saved |

Later, after v1.0.0: lessons for the other abilities (Ward, Muster, and the
ones new factions bring).

## The script

The match uses a fixed seed, chosen so that the player starts and their hand
holds what the script needs. The cards named below are an example; the seed
decides them. The texts are in English, as the game is.

Round 1:

1. **The board** (Next). On the player's rows: "Your rows are at the bottom:
   melee, ranged and siege. The AI's are at the top."
2. **The hand** (Next). On the hand: "These are your cards. A unit's number
   is its strength."
3. **A unit.** On the Soldier: "Play the Soldier in your melee row." The AI
   answers with a unit.
4. **Totals** (Next). On the player's total: "Each row adds up its units.
   Your total is the sum of your rows."
5. **Another row.** "Play the Sniper in your ranged row." The AI answers.
6. **A Spy.** "Play the Informant. It goes on the AI's side and gives it 3
   points, but you draw 2 cards." Then, on the hand: "Cards are what you play
   with all match: you don't draw new ones each round."
7. **Weather.** The AI plays Hoarfrost. On the row: "Hoarfrost: every unit in
   the melee row, on both sides, now has strength 1."
8. **Clear Skies.** "Play Clear Skies to remove all weather."
9. **Passing.** "You are ahead. Pass: you play no more cards this round, but
   the AI still can." The AI plays a card and passes; the player wins the
   round.
10. **Lives and the passive** (Next). On the lives: "You won the round: the
    AI loses a life. Win 2 rounds to win the match." On the leader: "Your
    leader, The Commander, gives you 1 card for each round you win."

Round 2:

11. The AI starts, plays a unit and passes. "The AI passed. Play just enough
    to win, and keep your other cards."
12. **A Medic.** On the Medic: "Play the Medic. It brings back a unit from
    your discard pile." Then, on the discard pile: "Choose the Sniper: it
    comes back to the board."
13. One more unit if needed, then Pass. The player wins the match: "Tutorial
    complete", with **Play a match** and **Return to main menu**.

## Architecture

The rules stay in the engine (ADR 0002): the page shows what the engine
recorded and decides nothing.

### Backend: `rowen.api.tutorial`

It lives in the API because it writes the API's own JSON shapes
(`schemas.py`).

- **The script:** a list of steps. Each has the balloon's text, its target
  (a card, a row, a total, the lives, the leader, the hand or the discard
  pile), and one of: the player's action, the AI's actions, or Next.
- **The generator**, run as `uv run python -m rowen.api.tutorial` (like
  `rowen.api.openapi`): it starts the match with `start_match` (Humans
  against Robots, the fixed seed) and carries out each action with `apply`,
  which checks it, so a step that is no longer legal makes it fail. After
  each step it records the player's view and events in the API's JSON
  shapes, with the view's legal actions cut down to the asked one.
- **The output:** `frontend/src/tutorial.json`.

### Frontend: the tutorial screen

- Opened by the **Tutorial** button on the main menu; `tutorial.json` is
  loaded only then (a lazy import), so the first page doesn't grow.
- It reuses `Board` and the animations in `stage.ts`, fed with the recorded
  views instead of the API's answers.
- Clicking the lit move goes to the next step and plays the AI's moves with
  the same animations as in a match.
- A small balloon component, positioned with `@floating-ui/react-dom`, is
  attached to its target by an attribute such as `data-tutorial="hand"`,
  with an arrow, and a Next button on the steps that only explain.
- **Leave tutorial** and the end window reuse the existing components.

Nothing changes in the rules, the API's endpoints, the database or nginx.

## Edge cases and accessibility

- **A click on anything else:** the other cards and rows are off, as when
  it isn't the player's turn; the balloon stays.
- **Small screens:** floating-ui flips the balloon to the side with room and
  keeps it on screen; the page scrolls to the target before showing it.
- **Resizing and animations:** the balloon follows its target, and appears
  only once the move's animation has finished.
- **Screen readers:** the balloon's text also goes to the existing
  `aria-live` region, and the Next button gets the keyboard focus.
- **Leaving:** no confirmation, since nothing is lost; nothing goes into the
  history or the stats.
- **A stale `tutorial.json`** (the rules or the cards changed): the backend
  test fails in CI, before the merge.
- **Size:** expected to be some tens of KB; measured in the first PR.

## Tests and pull requests

**PR 1, backend:** `rowen.api.tutorial` and the generated
`frontend/src/tutorial.json`, and ADR 0020, "The tutorial is a recorded
match". Tests: the file is up to date (generated again and compared); each
step's view has exactly one legal action, or none on a Next step; the match
ends with the player winning in 2 rounds; the recorded views don't show the
AI's hand.

**PR 2, frontend:** the `@floating-ui/react-dom` dependency (its version's
date checked against `min-release-age=14`), the balloon component, the
tutorial screen, the menu button, **Leave tutorial** and the end window.
Vitest: the button opens the tutorial; only the asked move is on; clicking
it moves to the next step; Next moves on; Leave goes back to the menu; the
end shows both buttons; the text goes to the `aria-live` region; each
step's target exists in the page. Playwright: one end-to-end test plays the
whole tutorial to "Tutorial complete".

One PR at a time: PR 2 starts after PR 1 is merged and understood.
