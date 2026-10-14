import { expect, test } from "vitest";
import type { Action, Card, Event } from "./api/client.ts";
import { HOARFROST, SOLDIER, WAR_HORN, side, view } from "./test-data.ts";
import {
  actionText,
  cardLabels,
  cardNames,
  cardText,
  eventText,
  happened,
  resultText,
  unitText,
} from "./text.ts";

test.each<[Card, string]>([
  [SOLDIER, "Soldier (4 melee/ranged, agile)"],
  [HOARFROST, "Hoarfrost (weather on melee)"],
  [WAR_HORN, "War Horn (special)"],
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

test("the names of the cards are those in the hand, the discard piles, the weather and on the board", () => {
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
          weather: [{ ...HOARFROST, id: "weather", name: "WEATHER" }],
          rows: {
            ...side().rows,
            melee: { ...row, units: [{ card: card("theirs"), strength: 4 }] },
            ranged: {
              ...row,
              horn: { ...WAR_HORN, id: "horn", name: "HORN" },
              scarecrows: [{ ...WAR_HORN, id: "scarecrow", name: "SCARECROW" }],
            },
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
    weather: "WEATHER",
    horn: "HORN",
    scarecrow: "SCARECROW",
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

test.each<[number, string]>([
  [4, "Soldier (4 melee/ranged, agile)"],
  [1, "Soldier (4 melee/ranged, agile), now 1"],
  [8, "Soldier (4 melee/ranged, agile), now 8"],
])(
  "a unit on the board says its strength now, if it isn't its own: %i",
  (strength, text) => {
    expect(unitText({ card: SOLDIER, strength })).toBe(text);
  },
);

test.each<[Card, string[]]>([
  [{ ...SOLDIER, rows: ["siege"], ability: "muster" }, ["Siege", "Muster"]],
  [{ ...SOLDIER, rows: ["ranged"], ability: null }, ["Ranged"]],
  // Only what it does: "Melee/Ranged" doesn't fit on the card.
  [SOLDIER, ["Agile"]],
  [{ ...SOLDIER, ability: null }, []],
  [HOARFROST, ["Weather", "Melee"]],
  [WAR_HORN, ["Special"]],
])("a card shows short words on what it is: %j", (card, labels) => {
  expect(cardLabels(card)).toEqual(labels);
});

const CARD_NAMES = new Map([
  ["soldier", "Soldier"],
  ["informant", "Informant"],
  ["medic", "Medic"],
  ["hoarfrost", "Hoarfrost"],
  ["clear-skies", "Clear Skies"],
  ["war-horn", "War Horn"],
  ["scarecrow", "Scarecrow"],
  ["wildfire", "Wildfire"],
]);

// The player of the view is player 0, and the AI player 1.
test.each<[Event, string]>([
  [
    { type: "unit_played", player: 0, card: "soldier", row: "melee", side: 0 },
    "You played Soldier in the melee row.",
  ],
  [
    { type: "unit_played", player: 1, card: "soldier", row: "ranged", side: 1 },
    "The AI played Soldier in the ranged row.",
  ],
  // A Spy goes on the other player's side.
  [
    {
      type: "unit_played",
      player: 0,
      card: "informant",
      row: "melee",
      side: 1,
    },
    "You played Informant in the AI's melee row.",
  ],
  [
    {
      type: "unit_played",
      player: 1,
      card: "informant",
      row: "melee",
      side: 0,
    },
    "The AI played Informant in your melee row.",
  ],
  [
    { type: "unit_revived", player: 1, card: "soldier", row: "siege", side: 1 },
    "The AI revived Soldier in the siege row.",
  ],
  [
    {
      type: "unit_revived",
      player: 0,
      card: "informant",
      row: "melee",
      side: 1,
    },
    "You revived Informant in the AI's melee row.",
  ],
  [
    {
      type: "unit_mustered",
      player: 0,
      card: "soldier",
      row: "melee",
      from_hand: false,
    },
    "Soldier came from your deck to the melee row.",
  ],
  [
    {
      type: "unit_mustered",
      player: 1,
      card: "soldier",
      row: "melee",
      from_hand: true,
    },
    "Soldier came from the AI's hand to the melee row.",
  ],
  [
    { type: "cards_drawn", player: 0, cards: ["soldier", "medic"] },
    "You drew Soldier, Medic.",
  ],
  [{ type: "opponent_drew", player: 1, count: 1 }, "The AI drew 1 card."],
  [{ type: "opponent_drew", player: 1, count: 2 }, "The AI drew 2 cards."],
  [
    { type: "weather_played", player: 1, card: "hoarfrost", row: "melee" },
    "The AI played Hoarfrost: weather on both melee rows.",
  ],
  [
    { type: "weather_cleared", player: 0, card: "clear-skies" },
    "You played Clear Skies and cleared all weather.",
  ],
  [
    { type: "horn_played", player: 0, card: "war-horn", row: "siege" },
    "You played War Horn in the siege row.",
  ],
  [
    {
      type: "scarecrow_played",
      player: 1,
      card: "scarecrow",
      row: "melee",
      unit: "medic",
    },
    "The AI played Scarecrow in the melee row and took back Medic.",
  ],
  [
    { type: "wildfire_played", player: 0, card: "wildfire" },
    "You played Wildfire.",
  ],
  [
    { type: "unit_destroyed", side: 1, row: "siege", card: "soldier" },
    "Soldier was destroyed in the AI's siege row.",
  ],
  [
    { type: "unit_destroyed", side: 0, row: "melee", card: "medic" },
    "Medic was destroyed in your melee row.",
  ],
  [{ type: "player_passed", player: 1 }, "The AI passed."],
  [{ type: "player_passed", player: 0 }, "You passed."],
  [
    { type: "round_ended", scores: [34, 28], winner: 0 },
    "Round 2: you won, 34 to 28.",
  ],
  // The winner's score first.
  [
    { type: "round_ended", scores: [28, 34], winner: 1 },
    "Round 2: the AI won, 34 to 28.",
  ],
  [
    { type: "round_ended", scores: [30, 30], winner: null },
    "Round 2: a tie, 30 to 30.",
  ],
  [{ type: "match_ended", winner: 0 }, "Match over. You won the match."],
  [{ type: "match_ended", winner: 1 }, "Match over. The AI won the match."],
  [{ type: "match_ended", winner: null }, "Match over. It's a draw."],
  [
    { type: "card_redrawn", player: 0, card: "soldier", drawn: "medic" },
    "You swapped Soldier for Medic.",
  ],
  [{ type: "opponent_redrew", player: 1 }, "The AI swapped a card."],
  [{ type: "redraw_ended", player: 1 }, "The AI finished swapping."],
  [{ type: "redraw_ended", player: 0 }, "You finished swapping."],
])("an event is told in one sentence: %j", (event, sentence) => {
  expect(eventText(event, 0, CARD_NAMES, 2)).toBe(sentence);
});

test("an event is told for the player of the view, whichever player they are", () => {
  expect(
    eventText(
      {
        type: "unit_played",
        player: 1,
        card: "informant",
        row: "melee",
        side: 0,
      },
      1,
      CARD_NAMES,
      1,
    ),
  ).toBe("You played Informant in the AI's melee row.");
  expect(
    eventText(
      { type: "round_ended", scores: [34, 28], winner: 0 },
      1,
      CARD_NAMES,
      1,
    ),
  ).toBe("Round 1: the AI won, 34 to 28.");
});

test("an event names a card the names don't know by its id", () => {
  expect(eventText({ type: "player_passed", player: 0 }, 0, new Map(), 1)).toBe(
    "You passed.",
  );
  expect(
    eventText(
      { type: "unit_played", player: 1, card: "drone", row: "ranged", side: 1 },
      0,
      new Map(),
      1,
    ),
  ).toBe("The AI played drone in the ranged row.");
});

test("what happened is the sentence of each event, in order, with no round over", () => {
  expect(
    happened(
      [
        {
          type: "unit_played",
          player: 0,
          card: "soldier",
          row: "melee",
          side: 0,
        },
        { type: "player_passed", player: 1 },
      ],
      0,
      CARD_NAMES,
      1,
    ),
  ).toEqual({
    sentences: ["You played Soldier in the melee row.", "The AI passed."],
    round: null,
  });
});

test("each round that ends in what happened is the next one, and the last one is how the round went", () => {
  // The AI passed long ago: the player passes, and the AI plays on alone
  // until the next round ends too.
  expect(
    happened(
      [
        { type: "player_passed", player: 0 },
        { type: "round_ended", scores: [10, 12], winner: 1 },
        {
          type: "unit_played",
          player: 1,
          card: "soldier",
          row: "melee",
          side: 1,
        },
        { type: "player_passed", player: 1 },
        { type: "round_ended", scores: [0, 4], winner: 1 },
        { type: "match_ended", winner: 1 },
      ],
      0,
      CARD_NAMES,
      2,
    ),
  ).toEqual({
    sentences: [
      "You passed.",
      "Round 2: the AI won, 12 to 10.",
      "The AI played Soldier in the melee row.",
      "The AI passed.",
      "Round 3: the AI won, 4 to 0.",
      "Match over. The AI won the match.",
    ],
    round: "Round 3: the AI won, 4 to 0.",
  });
});
