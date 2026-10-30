/**
 * How the page plays out moves: the steps of their animation, worked out from
 * the events the server sent and the view after each move.
 *
 * The page plays the moves' events one at a time: each card played comes up
 * large on the right of the screen, then goes to its place, which only then
 * shows it. While a card comes up, the board is still as it was before; once
 * it goes, the board is as the server left it after that card's move, with
 * the cards that move put there still to come held back. A player passing
 * and a round ending show on the board as it was; the next round, on the
 * board after. So the player sees the AI's moves one after another, and each
 * score as it was then. Nothing here knows the rules (ADR 0002): where a card
 * goes, and every score, are where and what the server's views say.
 */
import { useEffect, useState } from "react";
import type { Card, Event, MovePlayed, View } from "./api/client.ts";
import { cardsById, eventText } from "./text.ts";

/** How long each part of a step takes, in milliseconds. */
export const TIMES = {
  /** A card played, large on the right, before it goes. */
  show: 1500,
  /** A card played, on its way to its place. */
  fly: 500,
  /** A unit that a Muster brings: it pops up in its place, with no showing. */
  muster: 350,
  /** A unit destroyed, burning away. */
  burn: 700,
  /** A big message over the whole screen, such as "The AI passed." */
  announce: 2000,
} as const;

/**
 * One step of a move's animation, and the view of the match the board shows
 * then.
 *
 * - `play`: a card played from a hand (or revived from a discard pile)
 *   shows large on the right, then goes to `cell`.
 * - `muster`: a unit a Muster brings pops up in `cell`.
 * - `burn`: a unit destroyed burns away, in its row: `cell` is the row's.
 *
 * @property cell - Where the card goes on the board, as its `data-cell`
 *   (see {@link cellOf}); `undefined` if it isn't on the board any more,
 *   such as a card played just before the round ended.
 * @property hides - Whether the board holds the card back in `cell` until
 *   the step is done: a unit, a War Horn or a weather card. (A Scarecrow, Clear
 *   Skies or Wildfire go to a place that shows more than them.) A weather
 *   card held back doesn't hit its rows yet either.
 * @property cleared - For Clear Skies, the weather cards it clears: the
 *   board still shows them, and their rows under them, until it lands.
 * @property burnt - For a unit destroyed, where it was in its row and its
 *   strength then, as the view before showed them.
 * @property view - The view the board shows during the step: the one after
 *   the card's move.
 * @property waiting - The view the board shows while a card played comes up
 *   large, before it goes: the one before.
 */
export interface CardStep {
  kind: "play" | "muster" | "burn";
  card: Card;
  cell: string | undefined;
  hides: boolean;
  cleared?: readonly WeatherCard[];
  burnt?: Burnt;
  view: View;
  waiting: View;
}

/** A unit destroyed: its place in its row, and its strength, before. */
export interface Burnt {
  index: number;
  strength: number;
}

/** A weather card in play, as a side of the view lists it. */
export type WeatherCard = View["players"][number]["weather"][number];

/**
 * A step with no card: a big message over the whole screen, for what has no
 * card to show (a player passing, a round ending, the next one beginning).
 */
export interface Announcement {
  kind: "announce";
  text: string;
  view: View;
}

/** One step of a move's animation: a card's, or a big message. */
export type Step = CardStep | Announcement;

/**
 * The names of the places on the board a card can go to, as the board marks
 * them with `data-cell`. A side is the index of a player in the view.
 */
export const cellOf = {
  /** The `index`-th unit of a row. */
  unit: (side: number, row: string, index: number) =>
    `${String(side)}:${row}:${String(index)}`,
  /** The War Horn of a row. */
  horn: (side: number, row: string) => `${String(side)}:${row}:horn`,
  /** A whole row. */
  row: (side: number, row: string) => `${String(side)}:${row}`,
  /** The `index`-th weather card that a player played. */
  weather: (side: number, index: number) =>
    `weather:${String(side)}:${String(index)}`,
  /** A player's discard pile. */
  discard: (side: number) => `discard:${String(side)}`,
};

/**
 * Return the steps of the animation of `events`, which took the match from
 * the view `before` to the view `after`. Without a view before (the start of
 * the match), the board was empty.
 *
 * A player passing and a round ending are big messages, in the words of the
 * log, and so is the next round beginning. Round 1 begins once both players
 * are done swapping cards: its message says who goes first. Other events that change no card
 * on the board, such as drawing, have no step; nor has the end of the match,
 * which the page shows once the steps are over.
 */
export function stepsOf(
  events: readonly Event[],
  before: View | undefined,
  after: View,
): Step[] {
  const cards = cardsById([...(before === undefined ? [] : [before]), after]);
  // The places on the board that hold a card the move put there, not yet
  // given to an event: for each row, the units' indexes.
  const fresh = new Map<string, number[]>();
  const freshWeather = new Map<number, number[]>();
  after.players.forEach((side, index) => {
    const old = before?.players[index];
    for (const row of ["melee", "ranged", "siege"] as const) {
      fresh.set(
        cellOf.row(index, row),
        newIndexes(
          old?.rows[row].units.map((unit) => unit.card.id) ?? [],
          side.rows[row].units.map((unit) => unit.card.id),
        ),
      );
    }
    freshWeather.set(
      index,
      newIndexes(
        old?.weather.map((card) => card.id) ?? [],
        side.weather.map((card) => card.id),
      ),
    );
  });

  /** Return the place of a unit the move put in a row, and take it. */
  function unitCell(side: number, row: string, id: string) {
    const indexes = fresh.get(cellOf.row(side, row)) ?? [];
    const found = indexes.findIndex(
      (index) =>
        after.players[side]?.rows[row as "melee"].units[index]?.card.id === id,
    );
    if (found === -1) {
      return undefined;
    }
    const [index] = indexes.splice(found, 1);
    return index === undefined ? undefined : cellOf.unit(side, row, index);
  }

  /** Return the place of a weather card the move put in play, and take it. */
  function weatherCell(side: number, id: string) {
    const indexes = freshWeather.get(side) ?? [];
    const found = indexes.findIndex(
      (index) => after.players[side]?.weather[index]?.id === id,
    );
    if (found === -1) {
      return undefined;
    }
    const [index] = indexes.splice(found, 1);
    return index === undefined ? undefined : cellOf.weather(side, index);
  }

  // The units destroyed so far in each row of the view before, by index.
  const destroyed = new Map<string, number[]>();
  /** Return where a unit destroyed was, and its strength, and take it. */
  function burntUnit(side: number, row: string, id: string) {
    const taken = destroyed.get(cellOf.row(side, row)) ?? [];
    const units = before?.players[side]?.rows[row as "melee"].units ?? [];
    const index = units.findIndex(
      (unit, at) => unit.card.id === id && !taken.includes(at),
    );
    const unit = units[index];
    if (unit === undefined) {
      return undefined;
    }
    destroyed.set(cellOf.row(side, row), [...taken, index]);
    return { index, strength: unit.strength };
  }

  const steps: Step[] = [];
  const names = new Map([...cards].map(([id, card]) => [id, card.name]));
  let round = before?.round ?? after.round;
  // The view the board shows: the one before the move until a card of the
  // move goes to its place, or the next round begins. (At the start of the
  // match there is none before: the board shows the view after.)
  let board = before ?? after;
  function add(
    kind: CardStep["kind"],
    id: string,
    cell: string | undefined,
    hides: boolean,
  ) {
    const card = cards.get(id);
    // A card no view shows can't be drawn: it has no step.
    if (card !== undefined) {
      steps.push({
        kind,
        card,
        cell,
        hides: hides && cell !== undefined,
        view: after,
        waiting: board,
      });
      board = after;
    }
  }
  for (const event of events) {
    switch (event.type) {
      case "unit_played":
      case "unit_revived":
        add(
          "play",
          event.card,
          unitCell(event.side, event.row, event.card),
          true,
        );
        break;
      case "unit_mustered":
        add(
          "muster",
          event.card,
          unitCell(event.player, event.row, event.card),
          true,
        );
        break;
      case "horn_played":
        add("play", event.card, cellOf.horn(event.player, event.row), true);
        break;
      case "scarecrow_played":
        add("play", event.card, cellOf.row(event.player, event.row), false);
        break;
      case "weather_played":
        add("play", event.card, weatherCell(event.player, event.card), true);
        break;
      case "weather_cleared": {
        add("play", event.card, cellOf.discard(event.player), false);
        const step = steps.at(-1);
        if (step?.kind === "play") {
          step.cleared = before?.players.flatMap((side) => side.weather) ?? [];
        }
        break;
      }
      case "wildfire_played":
        add("play", event.card, cellOf.discard(event.player), false);
        break;
      case "unit_destroyed": {
        add("burn", event.card, cellOf.row(event.side, event.row), false);
        const step = steps.at(-1);
        const burnt = burntUnit(event.side, event.row, event.card);
        if (step?.kind === "burn" && burnt !== undefined) {
          step.burnt = burnt;
        }
        break;
      }
      case "player_passed":
        steps.push({
          kind: "announce",
          text: eventText(event, after.player, names, round),
          view: board,
        });
        break;
      case "round_ended":
        steps.push({
          kind: "announce",
          text: eventText(event, after.player, names, round),
          view: board,
        });
        round += 1;
        // The next round begins, unless the match is over.
        if (!events.some((later) => later.type === "match_ended")) {
          board = after;
          steps.push({
            kind: "announce",
            text: `Round ${String(round)}`,
            view: board,
          });
        }
        break;
      case "redraw_ended":
        if (after.players.every((side) => side.redraws_left === 0)) {
          board = after;
          steps.push({
            kind: "announce",
            text: `Round 1 · ${after.current === after.player ? "You go" : "The AI goes"} first.`,
            view: board,
          });
        }
        break;
      default:
        // Drawing, swapping and the end of the match change no card on the
        // board.
        break;
    }
  }
  return steps;
}

/**
 * Return the big message a new match starts with, in its first `view`: the
 * player swaps cards, as many as the server says they may.
 */
export function startOf(view: View): Announcement {
  const swaps = view.players[view.player]?.redraws_left ?? 0;
  return {
    kind: "announce",
    text: `Swap up to ${String(swaps)} card${swaps === 1 ? "" : "s"}.`,
    view,
  };
}

/**
 * Return the steps of the animation of `moves`, one after the other, from the
 * view `before` the first one (none at the start of the match).
 */
export function stepsOfMoves(
  moves: readonly MovePlayed[],
  before: View | undefined,
): Step[] {
  return moves.flatMap((move, index) =>
    stepsOf(
      move.events,
      index === 0 ? before : moves[index - 1]?.view,
      move.view,
    ),
  );
}

/**
 * Return the view the board shows at `progress` in `steps`, or `undefined`
 * once they are over: the board then shows the match as it is.
 */
export function viewAt(
  steps: readonly Step[],
  progress: Progress,
): View | undefined {
  const step = steps[progress.step];
  if (step?.kind === "play" && !progress.flying) {
    return step.waiting;
  }
  return step?.view;
}

/**
 * Where the animation of a move is: the step it is at (the number of steps
 * when it is over), and, for a card played, whether it is on its way.
 */
export interface Progress {
  step: number;
  flying: boolean;
}

/** Return where the animation is after `progress`, and how long until then. */
export function nextOf(
  steps: readonly Step[],
  progress: Progress,
): { progress: Progress; after: number } | undefined {
  const step = steps[progress.step];
  if (step === undefined) {
    return undefined;
  }
  if (step.kind === "play" && !progress.flying) {
    return {
      progress: { step: progress.step, flying: true },
      after: TIMES.show,
    };
  }
  const after = {
    play: TIMES.fly,
    muster: TIMES.muster,
    burn: TIMES.burn,
    announce: TIMES.announce,
  }[step.kind];
  return { progress: { step: progress.step + 1, flying: false }, after };
}

/**
 * A unit destroyed, still drawn in its row until it has burned.
 *
 * @property burning - Whether it is burning now.
 * @property burnt - Where it was in its row and its strength, if the view
 *   before showed it.
 */
export interface Ghost {
  card: Card;
  burning: boolean;
  burnt?: Burnt | undefined;
}

/**
 * What the board shows while a move plays out.
 *
 * @property hidden - The places whose cards are held back.
 * @property ghosts - By row (as {@link cellOf.row}), the units destroyed
 *   that are still drawn there.
 * @property lingering - The weather cards a Clear Skies still on its way
 *   will clear, which the board shows instead of the weather in the view.
 */
export interface Stage {
  hidden: ReadonlySet<string>;
  ghosts: ReadonlyMap<string, readonly Ghost[]>;
  lingering?: readonly WeatherCard[] | undefined;
}

/**
 * Return what the board shows at `progress` in `steps`, in the view it shows
 * then ({@link viewAt}): only the steps still to come in that view hold its
 * cards back, as the places they name are in it.
 */
export function stageOf(steps: readonly Step[], progress: Progress): Stage {
  const hidden = new Set<string>();
  const ghosts = new Map<string, Ghost[]>();
  let lingering: readonly WeatherCard[] | undefined;
  const view = viewAt(steps, progress);
  steps.forEach((step, index) => {
    if (
      index < progress.step ||
      step.kind === "announce" ||
      step.view !== view
    ) {
      return;
    }
    // The first Clear Skies still to land: the weather it clears stays.
    lingering ??= step.cleared;
    if (step.cell === undefined) {
      return;
    }
    if (step.hides) {
      hidden.add(step.cell);
    }
    if (step.kind === "burn") {
      const row = ghosts.get(step.cell) ?? [];
      row.push({
        card: step.card,
        burning: index === progress.step,
        burnt: step.burnt,
      });
      ghosts.set(step.cell, row);
    }
  });
  return { hidden, ghosts, lingering };
}

/** No step: nothing plays out. */
export const NO_STEPS: readonly Step[] = [];

/**
 * Return whether the page may move things: not if the player asked their
 * system for reduced motion (nor where the page can't ask, as in the tests).
 */
export function mayMove(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Play out `steps`, one after the other, and return where they are. New
 * steps start over from the first; the old ones are left where they were,
 * so a move made while the last one plays out shows at once.
 */
export function usePlayOut(steps: readonly Step[]): Progress {
  const [run, setRun] = useState({ steps, progress: START });
  if (run.steps !== steps) {
    // New steps: start them over, in this render (React's way to reset
    // state when a prop changes).
    setRun({ steps, progress: START });
  }
  useEffect(() => {
    const next = nextOf(run.steps, run.progress);
    if (next === undefined) {
      return;
    }
    const timer = setTimeout(() => {
      setRun({ steps: run.steps, progress: next.progress });
    }, next.after);
    return () => {
      clearTimeout(timer);
    };
  }, [run]);
  return run.steps === steps ? run.progress : START;
}

const START: Progress = { step: 0, flying: false };

/** What the board shows when no move is playing out. */
export const STILL: Stage = { hidden: new Set(), ghosts: new Map() };

/**
 * Return the indexes in `after` of the ids that aren't in `before`: the
 * cards a move added to a list, when it may also have taken some away.
 * Copies of a card are the same, so the first copies count as the old ones.
 */
export function newIndexes(
  before: readonly string[],
  after: readonly string[],
): number[] {
  const left = new Map<string, number>();
  for (const id of before) {
    left.set(id, (left.get(id) ?? 0) + 1);
  }
  const added: number[] = [];
  after.forEach((id, index) => {
    const count = left.get(id) ?? 0;
    if (count > 0) {
      left.set(id, count - 1);
    } else {
      added.push(index);
    }
  });
  return added;
}
