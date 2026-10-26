import { expect, type Page } from "@playwright/test";

/**
 * Play the match on the page until it is over: always the first card the
 * player may choose and the first place it may go (the card itself, if it
 * has nowhere to choose), or else the first other move (keeping the hand, or
 * passing). With `moves`, stop after that many moves, if it isn't over by
 * then.
 *
 * Each move adds one entry to what happened (the AI's answer comes with it),
 * so the next move waits until the page has the next view. (The log is out
 * of sight, but there all the same.) The page must play with reduced motion.
 */
export async function playOn(page: Page, moves = 100) {
  const cards = page.locator("[data-choosable]");
  const places = page.locator("[data-target]");
  const others = page.getByRole("group", { name: "Moves" }).getByRole("button");
  const entries = page.getByRole("log").getByRole("listitem");
  const over = page.getByRole("log").getByText(/^Match over\./);
  for (let n = 0; n < moves && (await over.count()) === 0; n++) {
    const count = await entries.count();
    if ((await cards.count()) > 0) {
      await cards.first().click();
      await places.first().click();
    } else {
      await others.first().click();
    }
    await expect(entries).toHaveCount(count + 1);
  }
}
