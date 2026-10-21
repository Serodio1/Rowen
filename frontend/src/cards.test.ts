import { expect, test } from "vitest";
import type { Card } from "./api/client.ts";
import { artOf, cardIcons, placeholderLook } from "./cards.ts";
import type { IconName } from "./icons.tsx";
import { CAPTAIN, HOARFROST, SOLDIER, WAR_HORN } from "./test-data.ts";

test("a card's art is the file named by its id", () => {
  const art = { "./art/soldier.webp": "/assets/soldier-1a2b3c.webp" };

  expect(artOf(SOLDIER, art)).toBe("/assets/soldier-1a2b3c.webp");
  expect(artOf(CAPTAIN, art)).toBeUndefined();
});

test.each<[Card, IconName[]]>([
  [{ ...SOLDIER, rows: ["siege"], ability: "muster" }, ["siege", "muster"]],
  [{ ...SOLDIER, rows: ["ranged"], ability: null }, ["ranged"]],
  // Only what it does: Agile already says it goes in two rows.
  [SOLDIER, ["agile"]],
  [{ ...SOLDIER, ability: null }, []],
  [HOARFROST, ["hoarfrost", "melee"]],
  [WAR_HORN, ["war-horn"]],
])(
  "a card shows icons for where it goes and what it does: %j",
  (card, icons) => {
    expect(cardIcons(card)).toEqual(icons);
  },
);

test.each<[Card, string]>([
  [SOLDIER, "melee"],
  [CAPTAIN, "siege"],
  [HOARFROST, "hoarfrost"],
  [WAR_HORN, "war-horn"],
])(
  "a card with no art looks like its first row, or its kind: %j",
  (card, look) => {
    expect(placeholderLook(card)).toBe(look);
  },
);
