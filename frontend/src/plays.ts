/**
 * How the player makes a move with the cards: first a card, then where it
 * goes. Only the legal actions the server sent can be made (ADR 0002): these
 * functions only sort them by card and by target.
 */
import type { Action } from "./api/client.ts";

/** A row of the board. */
export type Row = "melee" | "ranged" | "siege";

/** The rows, in the order of their keyboard shortcuts: 1, 2 and 3. */
export const ROWS: readonly Row[] = ["melee", "ranged", "siege"];

/** An action that starts with a card: every one but passing and keeping the hand. */
export type CardAction = Extract<Action, { card: string }>;

/**
 * Where an action puts its card, once the card is chosen: in one of the
 * player's rows (a unit, a War Horn, a unit revived), over one of their
 * units (a Scarecrow, which takes it back), or nowhere to choose (weather,
 * Clear Skies, Wildfire, or a card swapped before round 1).
 */
export type Target =
  | { kind: "row"; row: Row }
  | { kind: "unit"; row: Row; unit: string }
  | { kind: "self" };

/** Whether an action starts with a card. */
export function isCardAction(action: Action): action is CardAction {
  return "card" in action;
}

/** Return where an action puts its card. */
export function targetOf(action: CardAction): Target {
  switch (action.type) {
    case "play_unit":
    case "play_horn":
    case "revive":
      return { kind: "row", row: action.row };
    case "play_scarecrow":
      return { kind: "unit", row: action.row, unit: action.unit };
    case "play_special":
    case "redraw":
      return { kind: "self" };
  }
}

/**
 * Return the id of every card the player may choose, in the order of the
 * actions: those in the hand, or those in the discard pile while reviving.
 */
export function choosable(actions: readonly Action[]): Set<string> {
  return new Set(actions.filter(isCardAction).map((action) => action.card));
}

/** Return the actions that start with the card `card`. */
export function playsOf(
  actions: readonly Action[],
  card: string,
): CardAction[] {
  return actions.filter(isCardAction).filter((action) => action.card === card);
}

/** Return the play among `plays` that puts the card in `row`, if any. */
export function rowPlay(
  plays: readonly CardAction[],
  row: Row,
): CardAction | undefined {
  return plays.find((play) => {
    const target = targetOf(play);
    return target.kind === "row" && target.row === row;
  });
}

/** Return the play among `plays` that goes over the unit `unit` in `row`, if any. */
export function unitPlay(
  plays: readonly CardAction[],
  row: Row,
  unit: string,
): CardAction | undefined {
  return plays.find((play) => {
    const target = targetOf(play);
    return target.kind === "unit" && target.row === row && target.unit === unit;
  });
}

/** Return the play among `plays` with nowhere to choose, if any. */
export function selfPlay(plays: readonly CardAction[]): CardAction | undefined {
  return plays.find((play) => targetOf(play).kind === "self");
}

/** Return the actions with no card: passing, or keeping the hand. */
export function otherActions(actions: readonly Action[]): Action[] {
  return actions.filter((action) => !isCardAction(action));
}

/**
 * The card the player chose, before choosing where it goes: its id, where
 * it is (the hand, or the discard pile while reviving), and its place there,
 * so the page lifts the copy clicked.
 */
export interface Chosen {
  card: string;
  from: "hand" | "discard";
  index: number;
}

/**
 * What the board needs so the player can play on it.
 *
 * @property actions - The view's legal actions.
 * @property chosen - The card chosen, or null.
 * @property disabled - Whether nothing can be played now: a move is on its
 *   way, or the page is asking for the match.
 * @property onChoose - Called with the card chosen, or null to choose none.
 * @property onPlay - Called with the action the player made.
 */
export interface Playing {
  actions: readonly Action[];
  chosen: Chosen | null;
  disabled: boolean;
  onChoose: (chosen: Chosen | null) => void;
  onPlay: (action: Action) => void;
}
