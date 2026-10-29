/**
 * Data for the tests, written by hand in the shapes the API sends: the types
 * make TypeScript check that they still are.
 */
import type { Card, Deck, View } from "./api/client.ts";

export const DECKS: Deck[] = [
  {
    id: "humans",
    name: "Humans",
    passive: "Draws a card after winning a round.",
  },
  {
    id: "robots",
    name: "Robots",
    passive:
      "After each round, one random unit stays on the board, but not a Legend or a Spy.",
  },
];

export const SOLDIER = {
  type: "unit",
  id: "soldier",
  name: "Soldier",
  rows: ["melee", "ranged"],
  strength: 4,
  ability: "agile",
  group: null,
  legend: false,
  opponent_side: false,
  description: [],
} satisfies Card;

export const CAPTAIN = {
  ...SOLDIER,
  id: "captain",
  name: "Captain",
  rows: ["siege"],
  strength: 10,
  ability: null,
  legend: true,
} satisfies Card;

export const HOARFROST = {
  type: "special",
  id: "hoarfrost",
  name: "Hoarfrost",
  kind: "hoarfrost",
  weather_row: "melee",
  description: [],
} satisfies Card;

export const WAR_HORN = {
  type: "special",
  id: "war-horn",
  name: "War Horn",
  kind: "war-horn",
  weather_row: null,
  description: [],
} satisfies Card;

type Side = View["players"][number];

/** Return one player's side of the board at the start of a match. */
export function side(changes: Partial<Side> = {}): Side {
  const row: Side["rows"]["melee"] = {
    units: [],
    horn: null,
    scarecrows: [],
    scarecrow_places: [],
    weathered: false,
    score: 0,
  };
  return {
    rows: { melee: row, ranged: row, siege: row },
    weather: [],
    discard: [],
    lives: 2,
    passed: false,
    redraws_left: 2,
    hand_size: 10,
    deck_size: 12,
    total: 0,
    passive: null,
    ...changes,
  };
}

/**
 * Return the player's view at the start of a match, when they may swap
 * cards, with any changes given.
 */
export function view(changes: Partial<View> = {}): View {
  return {
    player: 0,
    hand: [SOLDIER, SOLDIER, HOARFROST],
    players: [side(), side()],
    current: 0,
    round: 1,
    reviving: false,
    legal_actions: [
      { type: "redraw", card: "soldier" },
      { type: "redraw", card: "hoarfrost" },
      { type: "end_redraw" },
    ],
    match_over: false,
    winner: null,
    ...changes,
  };
}
