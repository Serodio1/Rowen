import { expect, test } from "vitest";
import type { Action } from "./api/client.ts";
import {
  choosable,
  otherActions,
  playsOf,
  rowPlay,
  selfPlay,
  targetOf,
  unitPlay,
  type CardAction,
  type Target,
} from "./plays.ts";

// The legal actions of a turn with a Soldier (Agile), a War Horn, a
// Scarecrow, Hoarfrost, and passing.
const ACTIONS: Action[] = [
  { type: "play_unit", card: "soldier", row: "melee" },
  { type: "play_unit", card: "soldier", row: "ranged" },
  { type: "play_horn", card: "war-horn", row: "siege" },
  { type: "play_scarecrow", card: "scarecrow", row: "melee", unit: "sniper" },
  { type: "play_special", card: "hoarfrost" },
  { type: "pass" },
];

test.each<[CardAction, Target]>([
  [
    { type: "play_unit", card: "soldier", row: "melee" },
    { kind: "row", row: "melee" },
  ],
  [
    { type: "play_horn", card: "war-horn", row: "siege" },
    { kind: "row", row: "siege" },
  ],
  [
    { type: "revive", card: "soldier", row: "ranged" },
    { kind: "row", row: "ranged" },
  ],
  [
    { type: "play_scarecrow", card: "scarecrow", row: "melee", unit: "sniper" },
    { kind: "unit", row: "melee", unit: "sniper" },
  ],
  [{ type: "play_special", card: "hoarfrost" }, { kind: "self" }],
  [{ type: "redraw", card: "soldier" }, { kind: "self" }],
])("an action puts its card somewhere: %j", (action, target) => {
  expect(targetOf(action)).toEqual(target);
});

test("the cards the player may choose are those the actions start with", () => {
  expect([...choosable(ACTIONS)]).toEqual([
    "soldier",
    "war-horn",
    "scarecrow",
    "hoarfrost",
  ]);
});

test("a card's plays are the actions that start with it", () => {
  expect(playsOf(ACTIONS, "soldier")).toEqual([ACTIONS[0], ACTIONS[1]]);
  expect(playsOf(ACTIONS, "sniper")).toEqual([]);
});

test("a card's play in a row, over a unit, or with nowhere to choose", () => {
  const soldier = playsOf(ACTIONS, "soldier");
  expect(rowPlay(soldier, "ranged")).toBe(ACTIONS[1]);
  expect(rowPlay(soldier, "siege")).toBeUndefined();
  expect(selfPlay(soldier)).toBeUndefined();

  const scarecrow = playsOf(ACTIONS, "scarecrow");
  expect(unitPlay(scarecrow, "melee", "sniper")).toBe(ACTIONS[3]);
  expect(unitPlay(scarecrow, "ranged", "sniper")).toBeUndefined();
  expect(unitPlay(scarecrow, "melee", "soldier")).toBeUndefined();
  // A Scarecrow goes over a unit, not in a row.
  expect(rowPlay(scarecrow, "melee")).toBeUndefined();

  expect(selfPlay(playsOf(ACTIONS, "hoarfrost"))).toBe(ACTIONS[4]);
});

test("the other actions are those with no card", () => {
  expect(otherActions(ACTIONS)).toEqual([{ type: "pass" }]);
  expect(
    otherActions([{ type: "redraw", card: "soldier" }, { type: "end_redraw" }]),
  ).toEqual([{ type: "end_redraw" }]);
});
