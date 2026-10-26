import { test as base } from "@playwright/test";

export { expect } from "@playwright/test";

// nginx lets each visitor send 5 requests a second to the API, and 20 more at
// once (the api zone in frontend/nginx.conf, ADR 0011). Every test is the same
// visitor, and in CI the tests are quick: one after the other, they went over
// the 20 and a request was turned down (429). After this long with no request,
// the 20 are all there again.
const API_LIMIT_REFILLS_MS = (20 / 5) * 1000;

/**
 * Playwright's `test`, which first waits for nginx's limit on the API's
 * requests to refill, so that each test starts with all of it, whatever the
 * tests before it sent. The tests import `test` from here.
 */
export const test = base.extend<{ apiLimitRefilled: undefined }>({
  apiLimitRefilled: [
    // eslint-disable-next-line no-empty-pattern -- Playwright reads the fixtures a fixture needs from this pattern.
    async ({}, use) => {
      await new Promise((resolve) => setTimeout(resolve, API_LIMIT_REFILLS_MS));
      await use(undefined);
    },
    // Used by every test, without asking for it.
    { auto: true },
  ],
});
