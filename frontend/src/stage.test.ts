import { expect, test } from "vitest";
import type { Card, Event, View } from "./api/client.ts";
import {
  cellOf,
  newIndexes,
  nextOf,
  stageOf,
  stepsOf,
  TIMES,
  type CardStep,
  type Step,
} from "./stage.ts";
import { HOARFROST, SOLDIER, WAR_HORN, side, view } from "./test-data.ts";

const SPY = {
  ...SOLDIER,
  id: "spy",
  name: "Spy",
  rows: ["melee"],
  ability: "spy",
  opponent_side: true,
} satisfies Card;

const WILDFIRE = {
  type: "special",
  id: "wildfire",
  name: "Wildfire",
  kind: "wildfire",
  weather_row: null,
  description: [],
} satisfies Card;

type Side = View["players"][number];

/** Return the steps of cards among `steps`, leaving the big messages out. */
function cardSteps(steps: readonly Step[]): CardStep[] {
  return steps.filter((step) => step.kind !== "announce");
}

/** Return a side with `units` in its melee row. */
function withMelee(units: Card[], changes: Partial<Side> = {}): Side {
  const empty = side();
  return {
    ...empty,
    rows: {
      ...empty.rows,
      melee: {
        ...empty.rows.melee,
        units: units.map((card) => ({
          card: card as Side["rows"]["melee"]["units"][number]["card"],
          strength: 4,
        })),
      },
    },
    ...changes,
  };
}

test.each<[string[], string[], number[]]>([
  [[], ["a", "b"], [0, 1]],
  [["a"], ["a", "a"], [1]],
  // A card taken away and another added: only the new one.
  [["a", "b"], ["b", "c"], [1]],
  [["a", "b"], ["a", "b"], []],
])("the new cards of %j → %j are at %j", (before, after, added) => {
  expect(newIndexes(before, after)).toEqual(added);
});

test("a unit played goes to its new place in its row, which is held back", () => {
  const before = view({ players: [withMelee([SOLDIER]), side()] });
  const after = view({ players: [withMelee([SOLDIER, SOLDIER]), side()] });
  const events: Event[] = [
    { type: "unit_played", player: 0, card: "soldier", row: "melee", side: 0 },
  ];

  expect(stepsOf(events, before, after)).toEqual<Step[]>([
    {
      kind: "play",
      card: SOLDIER,
      cell: cellOf.unit(0, "melee", 1),
      hides: true,
    },
  ]);
});

test("a Spy goes to the side its event names, which may be the other player's", () => {
  const after = view({ players: [side(), withMelee([SPY])] });
  const events: Event[] = [
    { type: "unit_played", player: 0, card: "spy", row: "melee", side: 1 },
  ];

  expect(cardSteps(stepsOf(events, undefined, after))[0]?.cell).toBe(
    cellOf.unit(1, "melee", 0),
  );
});

test("two copies played in one move go to two places, in order", () => {
  const after = view({ players: [side(), withMelee([SOLDIER, SOLDIER])] });
  const events: Event[] = [
    { type: "unit_played", player: 1, card: "soldier", row: "melee", side: 1 },
    {
      type: "unit_mustered",
      player: 1,
      card: "soldier",
      row: "melee",
      from_hand: false,
    },
  ];

  expect(
    cardSteps(stepsOf(events, undefined, after)).map((step) => [
      step.kind,
      step.cell,
    ]),
  ).toEqual([
    ["play", cellOf.unit(1, "melee", 0)],
    ["muster", cellOf.unit(1, "melee", 1)],
  ]);
});

test("special cards go to the War Horn's place, the weather, a row or the discard pile", () => {
  const before = view({ hand: [WAR_HORN, HOARFROST, WILDFIRE] });
  const after = view({
    players: [side({ weather: [HOARFROST], discard: [WILDFIRE] }), side()],
  });
  const events: Event[] = [
    { type: "horn_played", player: 0, card: "war-horn", row: "siege" },
    { type: "weather_played", player: 0, card: "hoarfrost", row: "melee" },
    { type: "wildfire_played", player: 0, card: "wildfire" },
    { type: "weather_cleared", player: 1, card: "wildfire" },
  ];

  expect(
    cardSteps(stepsOf(events, before, after)).map((step) => [
      step.cell,
      step.hides,
    ]),
  ).toEqual([
    [cellOf.horn(0, "siege"), true],
    [cellOf.weather(0, 0), true],
    [cellOf.discard(0), false],
    [cellOf.discard(1), false],
  ]);
});

test("a Scarecrow goes to its row, which isn't held back", () => {
  const scarecrow = {
    ...WAR_HORN,
    id: "scarecrow",
    kind: "scarecrow",
  } satisfies Card;
  const before = view({ hand: [scarecrow] });
  const events: Event[] = [
    {
      type: "scarecrow_played",
      player: 0,
      card: "scarecrow",
      row: "melee",
      unit: "soldier",
    },
  ];

  expect(stepsOf(events, before, view())).toEqual<Step[]>([
    {
      kind: "play",
      card: scarecrow,
      cell: cellOf.row(0, "melee"),
      hides: false,
    },
  ]);
});

test("a card no longer on the board, as after the round ended, has no place; the round's end and the next one are big messages", () => {
  const after = view({ players: [side({ discard: [SOLDIER] }), side()] });
  const events: Event[] = [
    { type: "unit_played", player: 0, card: "soldier", row: "melee", side: 0 },
    { type: "round_ended", scores: [4, 0], winner: 0 },
  ];

  expect(stepsOf(events, undefined, after)).toEqual<Step[]>([
    { kind: "play", card: SOLDIER, cell: undefined, hides: false },
    { kind: "announce", text: "Round 1: you won, 4 to 0." },
    { kind: "announce", text: "Round 2" },
  ]);
});

test("after the last round, no next round begins", () => {
  const after = view({ round: 2, match_over: true, winner: 1 });
  const events: Event[] = [
    { type: "player_passed", player: 0 },
    { type: "round_ended", scores: [3, 9], winner: 1 },
    { type: "match_ended", winner: 1 },
  ];

  expect(stepsOf(events, view({ round: 2 }), after)).toEqual<Step[]>([
    { kind: "announce", text: "You passed." },
    { kind: "announce", text: "Round 2: the AI won, 9 to 3." },
  ]);
});

test("a unit destroyed burns in its row; a player passing is a big message; a card no view shows has no step", () => {
  const before = view({ players: [withMelee([SOLDIER]), side()] });
  const events: Event[] = [
    { type: "unit_destroyed", side: 0, row: "melee", card: "soldier" },
    { type: "player_passed", player: 1 },
    // A card no view shows: it can't be drawn.
    { type: "wildfire_played", player: 1, card: "unknown" },
  ];

  expect(stepsOf(events, before, view())).toEqual<Step[]>([
    { kind: "burn", card: SOLDIER, cell: cellOf.row(0, "melee"), hides: false },
    { kind: "announce", text: "The AI passed." },
  ]);
});

const STEPS: Step[] = [
  { kind: "play", card: SOLDIER, cell: "0:melee:0", hides: true },
  { kind: "muster", card: SOLDIER, cell: "0:melee:1", hides: true },
  { kind: "burn", card: SPY, cell: "1:melee", hides: false },
  { kind: "announce", text: "The AI passed." },
];

test("a card played shows, then flies; a muster, a burn and a big message each take one wait", () => {
  expect(nextOf(STEPS, { step: 0, flying: false })).toEqual({
    progress: { step: 0, flying: true },
    after: TIMES.show,
  });
  expect(nextOf(STEPS, { step: 0, flying: true })).toEqual({
    progress: { step: 1, flying: false },
    after: TIMES.fly,
  });
  expect(nextOf(STEPS, { step: 1, flying: false })).toEqual({
    progress: { step: 2, flying: false },
    after: TIMES.muster,
  });
  expect(nextOf(STEPS, { step: 2, flying: false })).toEqual({
    progress: { step: 3, flying: false },
    after: TIMES.burn,
  });
  expect(nextOf(STEPS, { step: 3, flying: false })).toEqual({
    progress: { step: 4, flying: false },
    after: TIMES.announce,
  });
  expect(nextOf(STEPS, { step: 4, flying: false })).toBeUndefined();
});

test("the board holds back the cards of the steps not done, and shows the units still burning", () => {
  const start = stageOf(STEPS, { step: 0, flying: false });
  expect([...start.hidden]).toEqual(["0:melee:0", "0:melee:1"]);
  expect(start.ghosts.get("1:melee")).toEqual([{ card: SPY, burning: false }]);

  const burning = stageOf(STEPS, { step: 2, flying: false });
  expect([...burning.hidden]).toEqual([]);
  expect(burning.ghosts.get("1:melee")).toEqual([{ card: SPY, burning: true }]);

  const over = stageOf(STEPS, { step: 3, flying: false });
  expect(over.ghosts.size).toBe(0);
});
