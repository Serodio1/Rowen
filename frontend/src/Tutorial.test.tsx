import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, onTestFinished, test, vi } from "vitest";
import { TIMES } from "./stage.ts";
import { loadTutorial } from "./tutorial.ts";
import { Tutorial } from "./Tutorial.tsx";

// jsdom has no scrollIntoView, which the balloon calls on its target.
beforeEach(() => {
  Element.prototype.scrollIntoView = () => undefined;
});

const { steps } = await loadTutorial();

/** Open the tutorial and wait for its first step. */
async function open() {
  const onLeave = vi.fn();
  const onPlay = vi.fn();
  render(
    <Tutorial onLeave={onLeave} onPlay={onPlay} onEnded={() => undefined} />,
  );
  expect(screen.getByText("Loading the tutorial…")).toBeInTheDocument();
  await screen.findByRole("note");
  return { onLeave, onPlay };
}

/** The balloon's text, as the page shows it. */
function balloon() {
  return screen.getByRole("note");
}

/**
 * Do what the balloon asks, as a player would: click Next, or Pass, or the
 * lit card and then where it goes (Clear Skies: the card again).
 */
function doStep() {
  const next = screen.queryByRole("button", { name: "Next" });
  if (next !== null) {
    fireEvent.click(next);
    return;
  }
  const pass = screen.queryByRole("button", { name: "Pass" });
  if (pass !== null) {
    fireEvent.click(pass);
    return;
  }
  const board = screen.getByRole("region", { name: "Board" });
  const [card, ...others] = board.querySelectorAll<HTMLElement>(
    "[data-choosable]:not(:disabled)",
  );
  expect(others).toHaveLength(0);
  if (card === undefined) {
    throw new Error("no card to play");
  }
  fireEvent.click(card);
  const target = board.querySelector<HTMLElement>("[data-target]");
  if (target === null) {
    throw new Error("nowhere to play the card");
  }
  fireEvent.click(target);
}

/**
 * Let the page move things, and make its clock the test's (jsdom has no
 * `matchMedia`: without it the page moves nothing).
 */
function withMotion() {
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  vi.useFakeTimers({ shouldAdvanceTime: true });
  onTestFinished(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
}

test("the first balloon says the first step", async () => {
  await open();
  expect(balloon()).toHaveTextContent(steps[0]?.text ?? "");
  expect(screen.getByRole("status")).toHaveTextContent(steps[0]?.text ?? "");
});

test("only the asked card can be played, and playing it moves on", async () => {
  await open();
  doStep();
  doStep();
  // Step 3: the Soldier.
  expect(balloon()).toHaveTextContent(steps[2]?.text ?? "");
  const hand = within(
    document.querySelector<HTMLElement>('[data-tutorial="hand"]') ??
      document.body,
  );
  const soldier = within(
    document.querySelector<HTMLElement>('[data-tutorial="card:soldier"]') ??
      document.body,
  ).getByRole("button");
  expect(soldier).toBeEnabled();
  // The other cards in the hand are no buttons: they can't be chosen.
  expect(hand.getAllByRole("button")).toEqual([soldier]);
  const scrolledTo = vi.fn();
  Element.prototype.scrollIntoView = scrolledTo;
  fireEvent.click(soldier);
  // Chosen, the balloon points at the row it goes in, not at the card.
  expect(scrolledTo.mock.contexts.at(-1)).toBe(
    screen.getByRole("button", { name: "Play Soldier in the melee row" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Play Soldier in the melee row" }),
  );
  expect(balloon()).toHaveTextContent(steps[3]?.text ?? "");
});

test("Next moves on", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(balloon()).toHaveTextContent(steps[1]?.text ?? "");
});

test("the second click of a double click on Next does nothing", async () => {
  await open();
  const next = screen.getByRole("button", { name: "Next" });
  fireEvent.click(next, { detail: 1 });
  fireEvent.click(next, { detail: 2 });
  expect(balloon()).toHaveTextContent(steps[1]?.text ?? "");
});

test("a step that only explains has no hint under the board", async () => {
  await open();
  expect(screen.queryByText("Choose a card to play, or pass.")).toBeNull();
  doStep();
  doStep();
  expect(
    screen.getByText("Choose a card to play, or pass."),
  ).toBeInTheDocument();
});

test("after a lit move, the focus goes to the next step's lit card", async () => {
  await open();
  for (let step = 0; step < 5; step += 1) {
    doStep();
  }
  // Step 6: the Informant, with no Next to take the focus.
  expect(balloon()).toHaveTextContent(steps[5]?.text ?? "");
  expect(
    within(
      document.querySelector<HTMLElement>('[data-tutorial="card:informant"]') ??
        document.body,
    ).getByRole("button"),
  ).toHaveFocus();
});

test("a second click while a move plays out does nothing", async () => {
  await open();
  for (let step = 0; step < 4; step += 1) {
    doStep();
  }
  // Step 5: the Sniper, with its move and the AI's played out.
  withMotion();
  doStep();
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
  const informant = within(
    document.querySelector<HTMLElement>('[data-tutorial="card:informant"]') ??
      document.body,
  ).getByRole("button");
  expect(informant).toBeDisabled();
  fireEvent.click(informant);
  // The Sniper, then the AI's unit: each comes up large, then goes.
  for (let card = 0; card < 2; card += 1) {
    await act(() => vi.advanceTimersByTimeAsync(TIMES.show));
    await act(() => vi.advanceTimersByTimeAsync(TIMES.fly));
  }
  expect(balloon()).toHaveTextContent(steps[5]?.text ?? "");
  expect(informant).toHaveAttribute("aria-pressed", "false");
});

test("every step's target is on the page, and the end offers a match or the menu", async () => {
  const { onLeave, onPlay } = await open();
  for (const step of steps) {
    expect(
      document.querySelector(`[data-tutorial="${step.target}"]`),
    ).not.toBeNull();
    expect(balloon()).toHaveTextContent(step.text);
    doStep();
  }
  const end = screen.getByRole("dialog", { name: "Tutorial complete" });
  // Two rounds, both won by the player.
  expect(within(end).getAllByRole("row")).toHaveLength(3);
  fireEvent.click(within(end).getByRole("button", { name: "Play a match" }));
  expect(onPlay).toHaveBeenCalledOnce();
  fireEvent.click(
    within(end).getByRole("button", { name: "Return to main menu" }),
  );
  expect(onLeave).toHaveBeenCalledOnce();
});

test("Leave tutorial goes back", async () => {
  const { onLeave } = await open();
  fireEvent.click(screen.getByRole("button", { name: "Leave tutorial" }));
  expect(onLeave).toHaveBeenCalledOnce();
});
