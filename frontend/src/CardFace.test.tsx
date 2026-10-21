import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { CardFace } from "./CardFace.tsx";
import { CAPTAIN, HOARFROST, SOLDIER, WAR_HORN } from "./test-data.ts";

// The Soldier has art, as if src/art/soldier.webp were there; the other
// cards don't.
vi.mock("./cards.ts", async (original) => {
  const cards = await original<typeof import("./cards.ts")>();
  return {
    ...cards,
    artOf: (card: Parameters<typeof cards.artOf>[0]) =>
      cards.artOf(card, {
        "./art/soldier.webp": "/assets/soldier-1a2b3c.webp",
      }),
  };
});

/** Return the circle with a unit's strength, in the card on the page. */
function strengthCircle(strength: number) {
  return screen.getByText(String(strength), { selector: "span" });
}

/** Return the names of the icons on the card on the page, in order. */
function icons(card: HTMLElement) {
  return [...card.querySelectorAll("[data-icon]")].map((icon) =>
    icon.getAttribute("data-icon"),
  );
}

test("a card shows its strength and its name; screen readers read the name given", () => {
  render(<CardFace card={SOLDIER} name="Soldier (4 melee/ranged, agile)" />);

  expect(
    screen.getByRole("img", { name: "Soldier (4 melee/ranged, agile)" }),
  ).toHaveTextContent(/^4Soldier$/);
});

test("a card with art shows it, and no placeholder", () => {
  render(<CardFace card={SOLDIER} name="Soldier" />);

  const card = screen.getByRole("img");
  // The art is only a picture: the card's name says what it is.
  expect(card.querySelector("img")).toHaveAttribute(
    "src",
    "/assets/soldier-1a2b3c.webp",
  );
  expect(card.querySelector("img")).toHaveAttribute("alt", "");
  expect(card.querySelector("[data-placeholder]")).toBeNull();
  // By its strength: Agile (it goes in either row).
  expect(icons(card)).toEqual(["agile"]);
});

test("a unit with no art shows its row's colour and its row's big icon", () => {
  render(<CardFace card={CAPTAIN} name="Captain" />);

  const card = screen.getByRole("img");
  expect(card.querySelector("img")).toBeNull();
  const placeholder = card.querySelector("[data-placeholder]");
  expect(placeholder).toHaveClass("from-siege", "to-siege");
  // The big icon, then the one by its strength.
  expect(icons(card)).toEqual(["siege", "siege"]);
});

test("a unit that may go in two rows fades from the first to the second", () => {
  render(<CardFace card={{ ...SOLDIER, id: "scout" }} name="Scout" />);

  expect(
    screen.getByRole("img").querySelector("[data-placeholder]"),
  ).toHaveClass("from-melee", "to-ranged");
});

test("a weather card shows its kind and the row it hits, and no strength", () => {
  render(<CardFace card={HOARFROST} name="Hoarfrost (weather on melee)" />);

  const card = screen.getByRole("img");
  expect(card).toHaveTextContent(/^Hoarfrost$/);
  expect(card.querySelector("[data-placeholder]")).toHaveClass(
    "from-hoarfrost",
  );
  expect(icons(card)).toEqual(["hoarfrost", "hoarfrost", "melee"]);
});

test("a special card has a dark frame; a unit, a gold one", () => {
  const { unmount } = render(<CardFace card={WAR_HORN} name="War Horn" />);
  expect(screen.getByRole("img")).toHaveClass("border-wood-950");
  unmount();

  render(<CardFace card={CAPTAIN} name="Captain" />);
  expect(screen.getByRole("img")).not.toHaveClass("border-wood-950");
});

test.each([
  [5, "text-green-800", "up"],
  [4, "text-ink", null],
  [1, "text-red-700", "down"],
])(
  "a unit's strength of %s now, against its own 4, is in %s, with an arrow %s",
  (strength, colour, arrow) => {
    render(<CardFace card={SOLDIER} strength={strength} name="Soldier" />);

    expect(strengthCircle(strength)).toHaveClass(colour);
    // More than the colour says it: an arrow, which screen readers skip.
    expect(
      strengthCircle(strength)
        .querySelector("[data-change]")
        ?.getAttribute("data-change") ?? null,
    ).toBe(arrow);
  },
);

test("a Legend has a gold frame, and its strength is gold on dark", () => {
  render(<CardFace card={CAPTAIN} name="Captain (10 siege, legend)" />);

  expect(screen.getByRole("img")).toHaveClass("border-gold-300", "ring-2");
  expect(strengthCircle(10)).toHaveClass("bg-ink", "text-gold-200");
});
