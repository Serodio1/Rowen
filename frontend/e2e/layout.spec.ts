import { expect, test, type Page } from "@playwright/test";

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

  // The board, the hand, the moves and what happened: all on one screen.
  expect(await scrolls(page)).toEqual({ across: 0, down: 0 });
  for (const shown of [
    page.getByRole("region", { name: "Board" }),
    page.getByRole("list", { name: "Your hand" }),
    page.getByRole("button", { name: "Pass" }),
    page.getByRole("log"),
  ]) {
    await expect(shown).toBeInViewport({ ratio: 1 });
  }
  // The ten cards of the hand at the start, without scrolling it.
  await expect(
    page.getByRole("list", { name: "Your hand" }).getByRole("listitem"),
  ).toHaveCount(10);
  expect(
    await page
      .getByRole("list", { name: "Your hand" })
      .evaluate((hand) => hand.scrollWidth - hand.clientWidth),
  ).toBe(0);

  for (const [width, height] of [
    [390, 844],
    [320, 640],
  ] as const) {
    await page.setViewportSize({ width, height });
    expect((await scrolls(page)).across, `at ${String(width)} wide`).toBe(0);
  }
});
