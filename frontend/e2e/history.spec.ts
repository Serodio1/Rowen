import { expect, test } from "@playwright/test";
import { playOn } from "./moves.ts";

test.use({ reducedMotion: "reduce" });

// A player's matches, kept by the database: one left halfway, played on from
// the list after the page opens again, and then listed with how it ended.
test("lists a player's matches, plays on one and counts how it ended", async ({
  page,
}) => {
  // A new account each run, so the list holds only this test's match.
  await page.goto("/");
  await page.getByRole("button", { name: "Log in" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", { name: "No account yet? Create one" })
    .click();
  await dialog.getByLabel("Username").fill(`e2e${Date.now().toString()}`);
  await dialog.getByLabel("Password").fill("e2e test password");
  await dialog.getByRole("button", { name: "Create an account" }).click();

  await page.getByRole("button", { name: "Humans" }).click();
  await playOn(page, 3);
  // The page forgets the match: only the list can bring it back.
  await page.reload();

  await page.getByRole("button", { name: "My matches" }).click();
  await expect(page.getByText("No match finished yet.")).toBeVisible();
  const match = page.getByRole("listitem");
  await expect(match).toHaveCount(1);
  await expect(match).toContainText("Humans against Robots");
  await expect(match).toContainText("Not over yet.");
  await match.getByRole("button", { name: "Resume" }).click();

  await playOn(page);
  const end = page.getByRole("dialog");
  await expect(end.getByRole("heading")).toHaveText(
    /^(You won the match!|The AI won the match\.|The match is a draw\.)$/,
  );
  // Each round, the first ones too, played before the page opened again.
  const rounds = end.getByRole("table", { name: "The rounds" });
  const ended = (await rounds.getByRole("row").count()) - 1;
  expect(ended).toBeGreaterThanOrEqual(2);
  await end.getByRole("button", { name: "Play again" }).click();

  await page.getByRole("button", { name: "My matches" }).click();
  await expect(match).toContainText(/^.*(Won|Lost|Drawn): \d+ to \d+/);
  await expect(match.getByRole("button", { name: "Resume" })).toHaveCount(0);
  const stats = page.getByRole("table", {
    name: "Matches won, lost and drawn",
  });
  await expect(stats.getByRole("row")).toHaveCount(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
});
