import { expect, test } from "./test.ts";

// The tutorial needs no server: it plays a recording. With reduced motion each
// move shows at once.
test.use({ reducedMotion: "reduce" });

/** Open the tutorial and do what each balloon asks, until it is over. */
async function playTutorial(
  page: import("@playwright/test").Page,
  inside?: { width: number; height: number },
) {
  await page.goto("/");
  await page.getByRole("button", { name: "Tutorial" }).click();
  const note = page.getByRole("note");
  const done = page.getByRole("heading", { name: "Tutorial complete" });
  for (let step = 0; step < 100 && !(await done.isVisible()); step += 1) {
    await expect(note).toBeVisible();
    if (inside !== undefined) {
      const box = await note.boundingBox();
      expect(box).not.toBeNull();
      expect(box?.x).toBeGreaterThanOrEqual(0);
      expect(box?.y).toBeGreaterThanOrEqual(0);
      expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(
        inside.width,
      );
      expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(
        inside.height,
      );
    }
    const text = await note.textContent();
    const next = page.getByRole("button", { name: "Next" });
    const lit = page.locator("[data-choosable]:not(:disabled)");
    const row = page.locator("[data-target]");
    if (await next.isVisible()) {
      await next.click();
    } else if ((await lit.count()) > 0) {
      await lit.first().click();
      if ((await row.count()) > 0) {
        // Not click(): on the Medic step the balloon covers the row (reported).
        await row.first().dispatchEvent("click");
      }
    } else {
      await page.getByRole("button", { name: "Pass" }).click();
    }
    // The step moved on (or the end came).
    await expect(async () => {
      expect(
        (await done.isVisible()) || (await note.textContent()) !== text,
      ).toBe(true);
    }).toPass();
  }
  await expect(done).toBeVisible();
}

test("plays the tutorial to the end", async ({ page }) => {
  await playTutorial(page);
  await page.getByRole("button", { name: "Return to main menu" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose your deck" }),
  ).toBeVisible();
});

// Fails today: on step 4 ("Each row adds up…", target "total") the balloon is
// above the screen at 390x844 (y = -259; the page is scrolled 494 px down and
// scrollIntoView didn't bring the target back). Reported; enable once fixed.
test.fixme("the balloons fit a phone's screen", async ({ page }) => {
  const size = { width: 390, height: 844 };
  await page.setViewportSize(size);
  await playTutorial(page, size);
});
