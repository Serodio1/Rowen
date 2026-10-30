import { expect, test } from "./test.ts";
import { playOn } from "./moves.ts";

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

  await playOn(page);

  const toMenu = page.getByRole("button", { name: "Return to main menu" });
  await expect(toMenu).toBeFocused();
  await expect(
    page.getByText(
      /^(You won the match!|The AI won the match\.|The match is a draw\.)$/,
    ),
  ).toBeVisible();
  // No move was turned down on the way.
  await expect(page.getByRole("alert")).toHaveCount(0);

  await toMenu.click();
  await expect(
    page.getByRole("heading", { name: "Choose your deck" }),
  ).toBeVisible();
});
