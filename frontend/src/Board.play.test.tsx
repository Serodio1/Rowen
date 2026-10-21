import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { expect, test } from "vitest";
import type { Action, Card, View } from "./api/client.ts";
import { Board } from "./Board.tsx";
import type { Chosen } from "./plays.ts";
import { CAPTAIN, HOARFROST, SOLDIER, side, view } from "./test-data.ts";

const SNIPER = {
  ...SOLDIER,
  id: "sniper",
  name: "Sniper",
  rows: ["ranged"],
  strength: 6,
  ability: null,
} satisfies Card;

// A Spy: the API says it goes on the AI's side.
const INFORMANT = {
  ...SOLDIER,
  id: "informant",
  name: "Informant",
  rows: ["melee"],
  strength: 3,
  ability: "spy",
  opponent_side: true,
} satisfies Card;

const SCARECROW = {
  type: "special",
  id: "scarecrow",
  name: "Scarecrow",
  kind: "scarecrow",
  weather_row: null,
} satisfies Card;

// A turn with a Soldier (melee or ranged), Hoarfrost, and passing.
const TURN = view({
  hand: [SOLDIER, HOARFROST, SOLDIER],
  legal_actions: [
    { type: "play_unit", card: "soldier", row: "melee" },
    { type: "play_unit", card: "soldier", row: "ranged" },
    { type: "play_special", card: "hoarfrost" },
    { type: "pass" },
  ],
});

/**
 * Draw the board of `played` so the player may play on it, as the page
 * does, and return the actions played, in order.
 */
function renderPlaying(shown: View, disabled = false) {
  const played: Action[] = [];
  function Playing() {
    const [chosen, setChosen] = useState<Chosen | null>(null);
    return (
      <Board
        view={shown}
        playing={{
          actions: shown.legal_actions,
          chosen,
          disabled,
          onChoose: setChosen,
          onPlay: (action) => played.push(action),
        }}
      />
    );
  }
  render(<Playing />);
  return played;
}

/** Return the cards in a list (the hand) the player may choose. */
function buttonsIn(list: string) {
  return within(screen.getByRole("list", { name: list })).queryAllByRole(
    "button",
  );
}

/** Return the button of the first Soldier in the hand. */
function soldier() {
  const [first] = screen.getAllByRole("button", { name: /^Soldier/ });
  return first as HTMLElement;
}

test("the cards the player may play are buttons", () => {
  renderPlaying(TURN);

  expect(buttonsIn("Your hand").map((button) => button.ariaLabel)).toEqual([
    "Soldier (4 melee/ranged, agile)",
    "Hoarfrost (weather on melee)",
    "Soldier (4 melee/ranged, agile)",
  ]);
  // No place lights up before a card is chosen.
  expect(
    screen.queryByRole("button", { name: /row$/ }),
  ).not.toBeInTheDocument();
});

test("choosing a card lights up the rows it may go in, and the focus goes to the first", () => {
  const played = renderPlaying(TURN);

  fireEvent.click(soldier());

  expect(soldier()).toHaveAttribute("aria-pressed", "true");
  const melee = screen.getByRole("button", {
    name: "Play Soldier in the melee row",
  });
  expect(melee).toHaveFocus();
  expect(melee).toHaveAttribute("aria-keyshortcuts", "1");
  expect(
    screen.queryByRole("button", { name: "Play Soldier in the siege row" }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Play Soldier in the ranged row" }),
  );

  expect(played).toEqual([
    { type: "play_unit", card: "soldier", row: "ranged" },
  ]);
});

test("a Spy lights up the AI's row, where it goes, and not the player's", () => {
  const played = renderPlaying(
    view({
      hand: [INFORMANT],
      legal_actions: [
        { type: "play_unit", card: "informant", row: "melee" },
        { type: "pass" },
      ],
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: /^Informant/ }));

  const theirs = within(
    screen.getByRole("group", { name: /^The AI's melee row/ }),
  ).getByRole("button", { name: "Play Informant in the AI's melee row" });
  expect(theirs).toHaveFocus();
  expect(
    within(screen.getByRole("group", { name: /^Your melee row/ })).queryByRole(
      "button",
    ),
  ).not.toBeInTheDocument();

  fireEvent.keyDown(theirs, { key: "1" });

  expect(played).toEqual([
    { type: "play_unit", card: "informant", row: "melee" },
  ]);
});

test("only the copy clicked rises", () => {
  renderPlaying(TURN);

  const [, second] = screen.getAllByRole("button", { name: /^Soldier/ });
  fireEvent.click(second as HTMLElement);

  expect(soldier()).toHaveAttribute("aria-pressed", "false");
  expect(second).toHaveAttribute("aria-pressed", "true");
});

test("a card with nowhere to choose is played by clicking it again", () => {
  const played = renderPlaying(TURN);

  fireEvent.click(
    screen.getByRole("button", { name: "Hoarfrost (weather on melee)" }),
  );
  const hoarfrost = screen.getByRole("button", { name: "Play Hoarfrost" });
  expect(hoarfrost).toHaveFocus();
  fireEvent.click(hoarfrost);

  expect(played).toEqual([{ type: "play_special", card: "hoarfrost" }]);
});

test("clicking the card chosen again lets it go", () => {
  const played = renderPlaying(TURN);

  fireEvent.click(soldier());
  fireEvent.click(soldier());

  expect(soldier()).toHaveAttribute("aria-pressed", "false");
  expect(
    screen.queryByRole("button", { name: /row$/ }),
  ).not.toBeInTheDocument();
  expect(played).toEqual([]);
});

test("Escape lets the card go, and the focus goes back to it", () => {
  renderPlaying(TURN);
  fireEvent.click(soldier());

  fireEvent.keyDown(document.activeElement as Element, { key: "Escape" });

  expect(soldier()).toHaveAttribute("aria-pressed", "false");
  expect(soldier()).toHaveFocus();
});

test.each<[string, Action[]]>([
  ["1", [{ type: "play_unit", card: "soldier", row: "melee" }]],
  ["2", [{ type: "play_unit", card: "soldier", row: "ranged" }]],
  // The Soldier can't go in the siege row.
  ["3", []],
  ["4", []],
])(
  "pressing %s plays the card chosen in that row, if it may go there",
  (key, actions) => {
    const played = renderPlaying(TURN);
    fireEvent.click(soldier());

    fireEvent.keyDown(document.activeElement as Element, { key });

    expect(played).toEqual(actions);
  },
);

test("a number with Ctrl plays nothing", () => {
  const played = renderPlaying(TURN);
  fireEvent.click(soldier());

  fireEvent.keyDown(document.activeElement as Element, {
    key: "1",
    ctrlKey: true,
  });

  expect(played).toEqual([]);
});

test("the arrow keys go from card to card, and around", () => {
  renderPlaying(TURN);
  const [first, second, third] = buttonsIn("Your hand");
  first?.focus();

  fireEvent.keyDown(first as Element, { key: "ArrowRight" });
  expect(second).toHaveFocus();
  fireEvent.keyDown(second as Element, { key: "ArrowRight" });
  fireEvent.keyDown(third as Element, { key: "ArrowRight" });
  expect(first).toHaveFocus();
  fireEvent.keyDown(first as Element, { key: "ArrowLeft" });
  expect(third).toHaveFocus();
});

test("a Scarecrow goes over one of the player's units, which become buttons", () => {
  const units = [{ card: SNIPER, strength: 6 }];
  const played = renderPlaying(
    view({
      hand: [SCARECROW],
      players: [
        side({
          rows: { ...side().rows, ranged: { ...side().rows.ranged, units } },
        }),
        side(),
      ],
      legal_actions: [
        {
          type: "play_scarecrow",
          card: "scarecrow",
          row: "ranged",
          unit: "sniper",
        },
        { type: "pass" },
      ],
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: /^Scarecrow/ }));
  fireEvent.click(
    screen.getByRole("button", {
      name: "Play Scarecrow in the ranged row, taking back Sniper",
    }),
  );

  expect(played).toEqual([
    {
      type: "play_scarecrow",
      card: "scarecrow",
      row: "ranged",
      unit: "sniper",
    },
  ]);
});

test("after a Medic, the units to revive are chosen from the discard pile, not the hand", () => {
  const played = renderPlaying(
    view({
      reviving: true,
      // A Sniper in the hand too: only the discard pile's may be revived.
      hand: [SNIPER, SOLDIER],
      // Two copies, and a Legend that can't be revived.
      players: [side({ discard: [SNIPER, SNIPER, CAPTAIN] }), side()],
      legal_actions: [{ type: "revive", card: "sniper", row: "ranged" }],
    }),
  );

  expect(buttonsIn("Your hand")).toHaveLength(0);
  const revivable = buttonsIn("Revive a unit from your discard pile");
  expect(revivable.map((button) => button.ariaLabel)).toEqual([
    "Sniper (6 ranged)",
  ]);

  fireEvent.click(revivable[0] as HTMLElement);
  fireEvent.click(
    screen.getByRole("button", { name: "Revive Sniper in the ranged row" }),
  );

  expect(played).toEqual([{ type: "revive", card: "sniper", row: "ranged" }]);
});

test("a Spy revived after a Medic goes on the AI's side too", () => {
  const played = renderPlaying(
    view({
      reviving: true,
      players: [side({ discard: [INFORMANT] }), side()],
      legal_actions: [{ type: "revive", card: "informant", row: "melee" }],
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: /^Informant/ }));
  fireEvent.click(
    within(
      screen.getByRole("group", { name: /^The AI's melee row/ }),
    ).getByRole("button", { name: "Revive Informant in the AI's melee row" }),
  );

  expect(played).toEqual([{ type: "revive", card: "informant", row: "melee" }]);
});

test("while nothing can be played, no card can be chosen", () => {
  renderPlaying(TURN, true);

  for (const button of buttonsIn("Your hand")) {
    expect(button).toBeDisabled();
  }
});

test("without playing, the board has no buttons", () => {
  render(<Board view={TURN} />);

  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
