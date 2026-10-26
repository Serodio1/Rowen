import { expect, test } from "@playwright/test";

// A deck as a player builds one, through nginx, the API and the database: the
// rules come from the API, and the deck is kept and deleted there.
test("builds a deck from a faction's cards, keeps it and deletes it", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Log in" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", { name: "No account yet? Create one" })
    .click();
  await dialog.getByLabel("Username").fill(`e2e${Date.now().toString()}`);
  await dialog.getByLabel("Password").fill("e2e test password");
  await dialog.getByRole("button", { name: "Create an account" }).click();

  await page.getByRole("button", { name: "My decks" }).click();
  await expect(page.getByText("No deck built yet.")).toBeVisible();
  await page.getByRole("button", { name: "New Humans deck" }).click();

  // Every unit the faction has, as many copies as each may have: more than
  // the 22 a deck needs.
  const cards = page.getByRole("list", { name: "Cards" });
  const units = cards.getByRole("button", {
    name: /^Add .*\(\d+ (melee|ranged|siege)/,
  });
  await expect(units.first()).toBeVisible();
  const save = page.getByRole("button", { name: "Save" });
  await expect(save).toBeDisabled();
  for (const unit of await units.all()) {
    while (await unit.isEnabled()) {
      await unit.click();
    }
  }
  await expect(save).toBeEnabled();
  await page.getByLabel("Name").fill("All of them");
  await save.click();

  const list = page.getByRole("list", { name: "Your decks" });
  await expect(list).toContainText("All of them");
  await page.getByRole("button", { name: "Delete All of them" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText("No deck built yet.")).toBeVisible();
});
