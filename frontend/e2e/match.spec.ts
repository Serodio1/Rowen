import { expect, test } from "@playwright/test";

// With reduced motion, as some players ask their system for: each move shows
// at once, so a whole match takes seconds, not minutes. (The layout test plays
// with the animations.)
test.use({ reducedMotion: "reduce" });

// The whole game, as a player sees it: the page that index.html and main.tsx
// start, through nginx, the API and the database.
test("plays a whole match against the AI", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Rowen" })).toBeVisible();

  await page.getByRole("button", { name: "Humans" }).click();
  await expect(page.getByRole("heading", { name: /^Round / })).toBeVisible();

  // Always the first card the player may choose and the first place it may
  // go (the card itself, if it has nowhere to choose), or else the first
  // other move (keeping the hand, or passing), until the match is over. Each
  // move adds one entry to what happened (the AI's answer comes with it), so
  // the test knows the page has the next view before it plays again. (The
  // log is out of sight, but there all the same.)
  const cards = page.locator("[data-choosable]");
  const places = page.locator("[data-target]");
  const others = page.getByRole("group", { name: "Moves" }).getByRole("button");
  const entries = page.getByRole("log").getByRole("listitem");
  const playAgain = page.getByRole("button", { name: "Play again" });
  const over = page.getByRole("log").getByText(/^Match over\./);
  for (let n = 0; n < 100 && (await over.count()) === 0; n++) {
    const count = await entries.count();
    if ((await cards.count()) > 0) {
      await cards.first().click();
      await places.first().click();
    } else {
      await others.first().click();
    }
    await expect(entries).toHaveCount(count + 1);
  }

  await expect(playAgain).toBeFocused();
  await expect(
    page.getByText(
      /^(You won the match!|The AI won the match\.|The match is a draw\.)$/,
    ),
  ).toBeVisible();
  // No move was turned down on the way.
  await expect(page.getByRole("alert")).toHaveCount(0);

  await playAgain.click();
  await expect(
    page.getByRole("heading", { name: "Choose your deck" }),
  ).toBeVisible();
});
