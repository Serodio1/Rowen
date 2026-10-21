import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { Board } from "./Board.tsx";
import type { Card, View } from "./api/client.ts";
import {
  CAPTAIN,
  HOARFROST,
  SOLDIER,
  WAR_HORN,
  side,
  view,
} from "./test-data.ts";

type Side = View["players"][number];
type Row = Side["rows"]["melee"];

const SNIPER = {
  ...SOLDIER,
  id: "sniper",
  name: "Sniper",
  rows: ["ranged"],
  strength: 6,
  ability: null,
} satisfies Card;

const DOWNPOUR = {
  type: "special",
  id: "downpour",
  name: "Downpour",
  kind: "downpour",
  weather_row: "siege",
} satisfies Card;

const SCARECROW = {
  type: "special",
  id: "scarecrow",
  name: "Scarecrow",
  kind: "scarecrow",
  weather_row: null,
} satisfies Card;

/** Return a row with nothing in it, with any changes given. */
function row(changes: Partial<Row> = {}): Row {
  return {
    units: [],
    horn: null,
    scarecrows: [],
    weathered: false,
    score: 0,
    ...changes,
  };
}

// Round 1, after the redraw. The player played Hoarfrost, which hits both
// melee rows, the AI played Downpour, which hits both siege rows, and then
// passed. The numbers are the API's: nothing here works them out.
const YOURS = side({
  rows: {
    melee: row({
      units: [{ card: SOLDIER, strength: 1 }],
      weathered: true,
      score: 1,
    }),
    ranged: row({
      units: [{ card: SNIPER, strength: 12 }],
      horn: WAR_HORN,
      score: 12,
    }),
    siege: row({ scarecrows: [SCARECROW], weathered: true }),
  },
  weather: [HOARFROST],
  lives: 2,
  hand_size: 3,
  deck_size: 12,
  redraws_left: 0,
  total: 13,
});
const THEIRS = side({
  rows: {
    melee: row({ weathered: true }),
    ranged: row(),
    siege: row({
      units: [{ card: CAPTAIN, strength: 10 }],
      weathered: true,
      score: 10,
    }),
  },
  weather: [DOWNPOUR],
  discard: [SOLDIER, SNIPER],
  lives: 1,
  passed: true,
  hand_size: 7,
  deck_size: 9,
  redraws_left: 0,
  total: 10,
});
const MID = view({ hand: [SNIPER, HOARFROST], players: [YOURS, THEIRS] });

// The AI ahead, with two Soldiers, a War Horn and a Scarecrow in its melee
// row, under Hoarfrost: the row's score is the strength of no single card.
const AI_AHEAD = view({
  players: [
    side({ lives: 1, total: 0 }),
    side({
      rows: {
        melee: row({
          units: [
            { card: SOLDIER, strength: 2 },
            { card: SOLDIER, strength: 2 },
          ],
          horn: WAR_HORN,
          scarecrows: [SCARECROW],
          weathered: true,
          score: 4,
        }),
        ranged: row(),
        siege: row(),
      },
      weather: [HOARFROST],
      hand_size: 7,
      deck_size: 9,
      total: 4,
    }),
  ],
});

/** Return the name of each card in `element`, as screen readers read it. */
function cards(element: HTMLElement) {
  return within(element)
    .queryAllByRole("img")
    .map((card) => card.getAttribute("aria-label"));
}

/** Return what a group of the board says for `term`, such as "Total". */
function detail(group: HTMLElement, term: string) {
  return within(group).getByText(term, { selector: "dt" }).nextElementSibling;
}

test("the AI's rows are on top and the player's below, so the melee rows meet in the middle", () => {
  render(<Board view={MID} />);

  expect(
    screen
      .getAllByRole("group", { name: /row/ })
      .map((group) => group.getAttribute("aria-label")),
  ).toEqual([
    "The AI's siege row: 10, under Downpour",
    "The AI's ranged row: 0",
    "The AI's melee row: 0, under Hoarfrost",
    "Your melee row: 1, under Hoarfrost",
    "Your ranged row: 12",
    "Your siege row: 0, under Downpour",
  ]);
});

test("each row shows its icon next to its score: a sword, a bow or a tower", () => {
  render(<Board view={MID} />);

  expect(
    screen
      .getAllByRole("group", { name: /row/ })
      .map((group) =>
        group.querySelector("[data-icon]")?.getAttribute("data-icon"),
      ),
  ).toEqual(["siege", "ranged", "melee", "melee", "ranged", "siege"]);
});

test("a row shows its units with their strength now, its War Horn and its Scarecrows", () => {
  render(<Board view={MID} />);

  const melee = screen.getByRole("group", { name: /^Your melee row/ });
  expect(cards(melee)).toEqual(["Soldier (4 melee/ranged, agile), now 1"]);
  const soldier = within(melee).getByRole("img");
  // The circle shows the strength now, not the card's own.
  expect(within(soldier).getByText("1")).toBeInTheDocument();
  expect(within(soldier).queryByText("4")).not.toBeInTheDocument();
  expect(
    cards(screen.getByRole("group", { name: /^Your ranged row/ })),
  ).toEqual(["War Horn (special)", "Sniper (6 ranged), now 12"]);
  expect(cards(screen.getByRole("group", { name: /^Your siege row/ }))).toEqual(
    ["Scarecrow (special)"],
  );
  expect(
    cards(screen.getByRole("group", { name: /^The AI's siege row/ })),
  ).toEqual(["Captain (10 siege, legend)"]);
});

test("each player's panel shows their total, lives and cards in hand, and whether they passed", () => {
  render(<Board view={MID} />);

  const ai = screen.getByRole("group", { name: "The AI" });
  expect(detail(ai, "Total")).toHaveTextContent(/^10$/);
  expect(detail(ai, "Lives")).toHaveTextContent(/^1$/);
  expect(detail(ai, "Hand")).toHaveTextContent(/^7$/);
  expect(within(ai).getByText("Passed")).toBeInTheDocument();

  const you = screen.getByRole("group", { name: "You" });
  // The higher total is marked.
  expect(detail(you, "Total")).toHaveTextContent(/^13 \(ahead\)$/);
  expect(detail(you, "Lives")).toHaveTextContent(/^2$/);
  expect(detail(you, "Hand")).toHaveTextContent(/^3$/);
  expect(within(you).queryByText("Passed")).not.toBeInTheDocument();
  // No swaps once the redraw is over.
  expect(within(you).queryByText("Swaps left")).not.toBeInTheDocument();
});

test("with the same total, neither player is ahead", () => {
  const even = view({ players: [side({ total: 5 }), side({ total: 5 })] });
  render(<Board view={even} />);

  expect(
    detail(screen.getByRole("group", { name: "You" }), "Total"),
  ).toHaveTextContent(/^5$/);
  expect(
    detail(screen.getByRole("group", { name: "The AI" }), "Total"),
  ).toHaveTextContent(/^5$/);
});

test("a player with no lives left has a dash for lives, and 0 for screen readers", () => {
  const over = view({ players: [side({ lives: 0 }), side({ lives: 1 })] });
  render(<Board view={over} />);

  const lives = detail(screen.getByRole("group", { name: "You" }), "Lives");
  expect(lives).toHaveTextContent(/^–0$/);
  expect(within(lives as HTMLElement).getByText("0")).toHaveClass("sr-only");
});

test("during the redraw, each panel says how many swaps are left", () => {
  const redraw = view({
    players: [side({ redraws_left: 1 }), side({ redraws_left: 2 })],
  });
  render(<Board view={redraw} />);

  expect(
    detail(screen.getByRole("group", { name: "You" }), "Swaps left"),
  ).toHaveTextContent(/^1$/);
  expect(
    detail(screen.getByRole("group", { name: "The AI" }), "Swaps left"),
  ).toHaveTextContent(/^2$/);
});

test("the weather in play is shown once, for both sides", () => {
  render(<Board view={MID} />);

  // The AI's first, as its side is on top.
  expect(cards(screen.getByRole("group", { name: "Weather" }))).toEqual([
    "Downpour (weather on siege)",
    "Hoarfrost (weather on melee)",
  ]);
});

test("with no weather in play, the weather says none", () => {
  render(<Board view={view()} />);

  const weather = screen.getByRole("group", { name: "Weather" });
  expect(cards(weather)).toEqual([]);
  expect(within(weather).getByText("None")).toBeInTheDocument();
});

test("each player's deck and discard pile show how many cards they hold, and the top discarded card", () => {
  render(<Board view={MID} />);

  const ai = screen.getByRole("group", {
    name: "The AI's deck and discard pile",
  });
  expect(detail(ai, "Deck")).toContainElement(within(ai).getByText("9 cards"));
  expect(
    within(detail(ai, "Discard pile") as HTMLElement).getByText("2 cards"),
  ).toBeInTheDocument();
  // The last card discarded is on top.
  expect(cards(ai)).toEqual(["Sniper (6 ranged)"]);

  const you = screen.getByRole("group", { name: "Your deck and discard pile" });
  expect(detail(you, "Deck")).toContainElement(
    within(you).getByText("12 cards"),
  );
  expect(detail(you, "Discard pile")).toHaveTextContent(/^0 cards$/);
  expect(cards(you)).toEqual([]);
});

test("one card is a card, not cards", () => {
  const one = view({ players: [side({ deck_size: 1 }), side()] });
  render(<Board view={one} />);

  const you = screen.getByRole("group", { name: "Your deck and discard pile" });
  expect(detail(you, "Deck")).toContainElement(within(you).getByText("1 card"));
});

test("the player of the view is at the bottom, whichever player they are", () => {
  // The same match, seen by the other player.
  const theirs = view({ player: 1, players: [YOURS, THEIRS] });
  render(<Board view={theirs} />);

  expect(
    detail(screen.getByRole("group", { name: "You" }), "Total"),
  ).toHaveTextContent(/^10$/);
  expect(
    screen.getByRole("group", { name: "Your siege row: 10, under Downpour" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("group", { name: "The AI's ranged row: 12" }),
  ).toBeInTheDocument();
});

test("the hand shows the player's cards, or says it is empty", () => {
  const { rerender } = render(<Board view={MID} />);

  expect(cards(screen.getByRole("list", { name: "Your hand" }))).toEqual([
    "Sniper (6 ranged)",
    "Hoarfrost (weather on melee)",
  ]);

  rerender(<Board view={view({ hand: [] })} />);

  expect(
    screen.queryByRole("list", { name: "Your hand" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Your hand is empty.")).toBeInTheDocument();
});

test("a row under weather the page doesn't see in play still says so", () => {
  const odd = view({
    players: [
      side({
        rows: { melee: row({ weathered: true }), ranged: row(), siege: row() },
      }),
      side(),
    ],
  });
  render(<Board view={odd} />);

  expect(
    screen.getByRole("group", { name: "Your melee row: 0, under weather" }),
  ).toBeInTheDocument();
});

test("the AI's total is marked when it is the higher one", () => {
  render(<Board view={AI_AHEAD} />);

  expect(
    detail(screen.getByRole("group", { name: "The AI" }), "Total"),
  ).toHaveTextContent(/^4 \(ahead\)$/);
  expect(
    detail(screen.getByRole("group", { name: "You" }), "Total"),
  ).toHaveTextContent(/^0$/);
});

test("a row draws every card in it, its score in a bubble and the weather's name", () => {
  render(<Board view={AI_AHEAD} />);

  const melee = screen.getByRole("group", {
    name: "The AI's melee row: 4, under Hoarfrost",
  });
  // Both copies of the unit, not only the first.
  expect(cards(melee)).toEqual([
    "War Horn (special)",
    "Soldier (4 melee/ranged, agile), now 2",
    "Soldier (4 melee/ranged, agile), now 2",
    "Scarecrow (special)",
  ]);
  // The score and the weather's name are drawn for the eyes: screen readers
  // read them in the row's name.
  const score = within(melee).getByText("4");
  expect(score).toHaveAttribute("aria-hidden");
  expect(score).toHaveClass("bg-enemy");
  expect(within(melee).getByText("Hoarfrost")).toHaveAttribute("aria-hidden");
  // The player's bubbles are in their own colour.
  expect(
    within(screen.getByRole("group", { name: /^Your melee row/ })).getByText(
      "0",
    ),
  ).toHaveClass("bg-ally");
});

test("each player's lives are drawn one by one, for the eyes", () => {
  render(<Board view={AI_AHEAD} />);

  for (const [name, lives] of [
    ["You", 1],
    ["The AI", 2],
  ] as const) {
    const drawn = detail(
      screen.getByRole("group", { name }),
      "Lives",
    )?.firstElementChild;
    expect(drawn).toHaveAttribute("aria-hidden");
    expect(drawn?.children).toHaveLength(lives);
  }
});

test("a deck shows how many cards it holds on its back, for the eyes", () => {
  render(<Board view={AI_AHEAD} />);

  const ai = screen.getByRole("group", {
    name: "The AI's deck and discard pile",
  });
  expect(
    within(detail(ai, "Deck") as HTMLElement).getByText("9"),
  ).toHaveAttribute("aria-hidden");
  // On a narrow screen, where the two players' piles are side by side, each
  // says whose it is (only screen readers read it on a wide one).
  expect(
    within(ai).getByRole("heading", { name: "The AI's deck and discard pile" }),
  ).toHaveClass("lg:sr-only");
});

test("the same weather, played by both players, is shown twice", () => {
  const twice = view({
    players: [side({ weather: [HOARFROST] }), side({ weather: [HOARFROST] })],
  });
  render(<Board view={twice} />);

  // Both cards have the same id: the page must still tell them apart.
  expect(cards(screen.getByRole("group", { name: "Weather" }))).toEqual([
    "Hoarfrost (weather on melee)",
    "Hoarfrost (weather on melee)",
  ]);
});

test("while a move plays out, its cards are held back and the units destroyed burn in their rows", () => {
  render(
    <Board
      view={view({ players: [side({ weather: [HOARFROST] }), side()] })}
      stage={{
        hidden: new Set(["weather:0:0"]),
        ghosts: new Map([
          [
            "1:siege",
            [
              { card: SOLDIER, burning: true },
              { card: SOLDIER, burning: false },
            ],
          ],
        ]),
      }}
    />,
  );

  expect(document.querySelector('[data-cell="weather:0:0"]')).toHaveClass(
    "opacity-0",
  );
  const ghosts = [
    ...screen
      .getByRole("group", { name: /^The AI's siege row/ })
      .querySelectorAll("[data-ghost]"),
  ];
  expect(ghosts.map((ghost) => ghost.className)).toEqual(["animate-burn", ""]);
  // Only pictures: the log says what happened.
  expect(ghosts.every((ghost) => ghost.getAttribute("aria-hidden"))).toBe(true);
});
