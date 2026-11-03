import { expect, test } from "./test.ts";

// The tutorial needs no server: it plays a recording. With reduced motion each
// move shows at once.
test.use({ reducedMotion: "reduce" });

/** The balloon doesn't cover the middle of what the player must click. */
async function expectUncovered(target: import("@playwright/test").Locator) {
  await target.scrollIntoViewIfNeeded();
  expect(
    await target.evaluate((element) => {
      const { x, y, width, height } = element.getBoundingClientRect();
      const hit = document.elementFromPoint(x + width / 2, y + height / 2);
      return hit !== null && element.contains(hit);
    }),
  ).toBe(true);
}

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
      // Once floating-ui has placed it (it may first be where the last was).
      await expect(async () => {
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
      }).toPass();
    }
    const text = await note.textContent();
    const next = page.getByRole("button", { name: "Next" });
    const lit = page.locator("[data-choosable]:not(:disabled)");
    const row = page.locator("[data-target]");
    if (await next.isVisible()) {
      await next.click();
    } else if ((await lit.count()) > 0) {
      await expectUncovered(lit.first());
      await lit.first().click();
      if ((await row.count()) > 0) {
        await expectUncovered(row.first());
        await row.first().click();
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

test("the balloons fit a phone's screen", async ({ page }) => {
  const size = { width: 390, height: 844 };
  await page.setViewportSize(size);
  await playTutorial(page, size);
});
