import type { Page } from "@playwright/test";
import { expect, test } from "./test.ts";

/** Return how far the page scrolls each way, in pixels. */
function scrolls(page: Page) {
  return page.evaluate(() => ({
    across: document.documentElement.scrollWidth - window.innerWidth,
    down: document.documentElement.scrollHeight - window.innerHeight,
  }));
}

// One match for every size: nginx lets a visitor start only a few matches a
// minute (nginx.conf), and the Smoke test starts more after these tests.
test("the match fits a laptop's screen, and nothing sticks out on a phone", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByRole("button", { name: "Humans" }).click();
  await page.getByRole("button", { name: "Keep this hand" }).click();
  await expect(page.getByText("Choose a card to play, or pass.")).toBeVisible();

  // The ten cards of the hand at the start, without scrolling it.
  const hand = page.getByRole("list", { name: "Your hand" });
  await expect(hand.getByRole("listitem")).toHaveCount(10);
  expect(
    await hand.evaluate((list) => list.scrollWidth - list.clientWidth),
  ).toBe(0);

  // A few moves, so some rows have cards and others don't.
  const entries = page.getByRole("log").getByRole("listitem");
  for (let n = 0; n < 4; n++) {
    const count = await entries.count();
    await page.locator("[data-choosable]").first().click();
    await page.locator("[data-target]").first().click();
    await expect(entries).toHaveCount(count + 1);
  }
  // After a Medic, the units to revive take the hand's place until one is
  // chosen (and a revived Medic revives again): finish, so the hand is back.
  const revive = page.getByRole("list", {
    name: "Revive a unit from your discard pile",
  });
  while (await revive.isVisible()) {
    await revive.locator("[data-choosable]").first().click();
    await page.locator("[data-target]").first().click();
  }
  await expect(hand).toBeVisible();

  // A row is as high with cards as without: the board doesn't grow as the
  // rows fill up, so it still fits once they all have cards.
  const rows = page
    .getByRole("region", { name: "Board" })
    .getByRole("group", { name: /row: / });
  await expect(rows).toHaveCount(6);
  const heights = await rows.evaluateAll((all) =>
    all.map((row) => row.getBoundingClientRect().height),
  );
  expect(new Set(heights).size).toBe(1);

  // The board, the hand, the moves and what happened (once the player
  // opens it): all on one screen.
  await page.getByRole("button", { name: "Show log" }).click();
  expect(await scrolls(page)).toEqual({ across: 0, down: 0 });
  for (const shown of [
    page.getByRole("region", { name: "Board" }),
    hand,
    page.getByRole("button", { name: "Pass" }),
    page.getByRole("log"),
  ]) {
    await expect(shown).toBeInViewport({ ratio: 1 });
  }

  for (const [width, height] of [
    [390, 844],
    [320, 640],
  ] as const) {
    await page.setViewportSize({ width, height });
    expect((await scrolls(page)).across, `at ${String(width)} wide`).toBe(0);
  }
});
