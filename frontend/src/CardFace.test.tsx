import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { CardFace } from "./CardFace.tsx";
import { CAPTAIN, HOARFROST, SOLDIER } from "./test-data.ts";

/** Return the circle with a unit's strength, in the card on the page. */
function strengthCircle(strength: number) {
  return screen.getByText(String(strength), { selector: "span" });
}

test("a card shows the first letter of its name, its strength, its name and what it does", () => {
  render(<CardFace card={SOLDIER} name="Soldier (4 melee/ranged, agile)" />);

  // Screen readers read the name given; the face shows it in short.
  expect(
    screen.getByRole("img", { name: "Soldier (4 melee/ranged, agile)" }),
  ).toHaveTextContent(/^S4SoldierAgile$/);
});

test("a card's words are kept apart by dots", () => {
  render(<CardFace card={HOARFROST} name="Hoarfrost (weather on melee)" />);

  expect(screen.getByRole("img")).toHaveTextContent(
    /^HHoarfrostWeather · Melee$/,
  );
});

test.each([
  [5, "text-green-800"],
  [4, "text-ink"],
  [1, "text-red-700"],
])(
  "a unit's strength of %s now, against its own 4, is in %s",
  (strength, colour) => {
    render(<CardFace card={SOLDIER} strength={strength} name="Soldier" />);

    expect(strengthCircle(strength)).toHaveClass(colour);
  },
);

test("a Legend has a gold frame, and its strength is gold on dark", () => {
  render(<CardFace card={CAPTAIN} name="Captain (10 siege, legend)" />);

  expect(screen.getByRole("img")).toHaveClass("ring-2");
  expect(strengthCircle(10)).toHaveClass("bg-ink", "text-gold-200");
});
