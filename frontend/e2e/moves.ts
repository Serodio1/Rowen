import { expect, type Page } from "@playwright/test";

/**
 * Play the match on the page until it is over: always the first card the
 * player may choose and the first place it may go (the card itself, if it
 * has nowhere to choose), or else the first other move (keeping the hand, or
 * passing). With `moves`, stop after that many moves, if it isn't over by
 * then.
 *
 * Each move adds one entry to what happened, and the AI's turn after it
 * another, so the next move waits for the move's entry and then for the
 * AI's turn to end (`yourTurn`). (The log is out of sight, but there all the
 * same.) The page must play with reduced motion.
 *
 * It first waits for the board: the entries are counted from there. Counted
 * before, the entry of the AI's first moves, when it starts, would come with
 * the first move's.
 */
export async function playOn(page: Page, moves = 100) {
  await expect(page.getByRole("heading", { name: /^Round / })).toBeVisible();
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
    // At least one more: the AI's turn may add its own right after.
    await expect.poll(() => entries.count()).toBeGreaterThan(count);
    await yourTurn(page);
  }
}

/**
 * Wait until the AI's turn, if it is the AI's, is over: the page says whose
 * turn it is above the moves.
 */
export async function yourTurn(page: Page) {
  await expect(page.getByText(/^The AI('s turn\.| is thinking…)$/)).toHaveCount(
    0,
  );
}
