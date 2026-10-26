import { expect, test } from "./test.ts";

// An account, as a player makes and uses one, through nginx, the API and the
// database: the session's cookie is real, so this is where it is seen to
// work in a browser (HttpOnly, Secure on localhost, SameSite=Lax).
test("makes an account, stays logged in, logs out and in again", async ({
  page,
}) => {
  // A new username each run: the database keeps the accounts.
  const username = `e2e${Date.now().toString()}`;
  const password = "e2e test password";
  await page.goto("/");

  await page.getByRole("button", { name: "Log in" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", { name: "No account yet? Create one" })
    .click();
  await dialog.getByLabel("Username").fill(username);
  await dialog.getByLabel("Password").fill(password);
  await dialog.getByRole("button", { name: "Create an account" }).click();
  await expect(page.getByText(`Logged in as ${username}`)).toBeVisible();

  // The cookie stays when the page opens again.
  await page.reload();
  await expect(page.getByText(`Logged in as ${username}`)).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();

  await page.getByRole("button", { name: "Log in" }).click();
  await dialog.getByLabel("Username").fill(username);
  await dialog.getByLabel("Password").fill(password);
  await dialog.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText(`Logged in as ${username}`)).toBeVisible();

  // Logged in, a match starts as for a guest.
  await page.getByRole("button", { name: "Humans" }).click();
  await expect(page.getByRole("heading", { name: /^Round / })).toBeVisible();
});
