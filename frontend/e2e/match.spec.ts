import { expect, test } from "@playwright/test";

// The whole game, as a player sees it: the page that index.html and main.tsx
// start, through nginx, the API and the database.
test("plays a whole match against the AI", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Rowen" })).toBeVisible();

  await page.getByRole("button", { name: "Humans" }).click();
  await expect(page.getByRole("heading", { name: /^Round / })).toBeVisible();

  // Always the first move, until the match is over. Each move adds one entry
  // to what happened (the AI's answer comes with it), so the test knows the
  // page has the next view before it plays again.
  const moves = page
    .getByRole("list", { name: "What you can do" })
    .getByRole("button");
  const entries = page.getByRole("log").getByRole("listitem");
  const playAgain = page.getByRole("button", { name: "Play again" });
  for (let n = 0; n < 100 && !(await playAgain.isVisible()); n++) {
    const count = await entries.count();
    await moves.first().click();
    await expect(entries).toHaveCount(count + 1);
    // nginx answers 429 after 20 requests in a row beyond 5 a second
    // (nginx.conf): a player clicks slower than this.
    await page.waitForTimeout(250);
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
