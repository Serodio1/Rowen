import { expect, test } from "vitest";
import type { Action, Card } from "./api/client.ts";
import { HOARFROST, SOLDIER, side, view } from "./test-data.ts";
import { actionText, cardNames, cardText, resultText } from "./text.ts";

test.each<[Card, string]>([
  [SOLDIER, "Soldier (4 melee/ranged, agile)"],
  [HOARFROST, "Hoarfrost (special)"],
  [
    { ...SOLDIER, name: "Captain", strength: 10, legend: true, ability: null },
    "Captain (10 melee/ranged, legend)",
  ],
  [
    {
      ...SOLDIER,
      name: "Healer",
      rows: ["siege"],
      legend: true,
      ability: "medic",
    },
    "Healer (4 siege, legend, medic)",
  ],
])("a card is shown with what a player needs to know: %j", (card, text) => {
  expect(cardText(card)).toBe(text);
});

const NAMES = new Map([
  ["sniper", "Sniper"],
  ["war-horn", "War Horn"],
  ["scarecrow", "Scarecrow"],
  ["medic", "Medic"],
]);

test.each<[Action, string]>([
  [
    { type: "play_unit", card: "sniper", row: "ranged" },
    "Play Sniper in the ranged row",
  ],
  [{ type: "play_special", card: "scarecrow" }, "Play Scarecrow"],
  [
    { type: "play_horn", card: "war-horn", row: "siege" },
    "Play War Horn in the siege row",
  ],
  [
    { type: "play_scarecrow", card: "scarecrow", row: "melee", unit: "medic" },
    "Play Scarecrow in the melee row, taking back Medic",
  ],
  [{ type: "pass" }, "Pass"],
  [
    { type: "revive", card: "medic", row: "melee" },
    "Revive Medic in the melee row",
  ],
  [{ type: "redraw", card: "sniper" }, "Swap Sniper"],
  [{ type: "end_redraw" }, "Keep this hand"],
])("an action is shown as a choice of the player: %j", (action, text) => {
  expect(actionText(action, NAMES)).toBe(text);
});

test("a card the view doesn't show is named by its id", () => {
  expect(actionText({ type: "redraw", card: "drone" }, NAMES)).toBe(
    "Swap drone",
  );
});

test("the names of the cards are those in the hand, the discard piles and on the board", () => {
  const card = (id: string) => ({
    ...SOLDIER,
    id,
    name: id.toUpperCase(),
  });
  const row = side().rows.melee;
  const names = cardNames(
    view({
      hand: [card("in-hand")],
      players: [
        side({
          discard: [card("discarded")],
          rows: {
            melee: { ...row, units: [{ card: card("melee"), strength: 4 }] },
            ranged: { ...row, units: [{ card: card("ranged"), strength: 4 }] },
            siege: { ...row, units: [{ card: card("siege"), strength: 4 }] },
          },
        }),
        side({
          discard: [card("their-discarded")],
          rows: {
            ...side().rows,
            melee: { ...row, units: [{ card: card("theirs"), strength: 4 }] },
          },
        }),
      ],
    }),
  );

  expect(Object.fromEntries(names)).toEqual({
    "in-hand": "IN-HAND",
    discarded: "DISCARDED",
    melee: "MELEE",
    ranged: "RANGED",
    siege: "SIEGE",
    "their-discarded": "THEIR-DISCARDED",
    theirs: "THEIRS",
  });
});

test.each<[number | null, string]>([
  [0, "You won the match!"],
  [1, "The AI won the match."],
  [null, "The match is a draw."],
])("the result says who won, for the player 0: winner %s", (winner, text) => {
  expect(resultText(view({ match_over: true, winner }))).toBe(text);
});

test("the result is for the player of the view", () => {
  const over = view({ player: 1, match_over: true, winner: 1 });

  expect(resultText(over)).toBe("You won the match!");
});
