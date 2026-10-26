import { defineConfig, devices } from "@playwright/test";

// https://playwright.dev/docs/test-configuration
//
// The end-to-end tests (e2e/) play the game in a real browser, against the
// game already running at BASE_URL: by default the Docker images, as
// `docker compose up` starts them (the README, and the Docker job in CI). They
// don't start it themselves.
export default defineConfig({
  testDir: "e2e",
  // A test that waits for longer than this has failed: a whole match takes a
  // few seconds.
  timeout: 60_000,
  // In CI, a test.only left in by mistake fails the run instead of skipping
  // the other tests.
  forbidOnly: Boolean(process.env.CI),
  // A test that fails once has failed: no second try that could hide a bug.
  retries: 0,
  // One test at a time. nginx limits how many requests each visitor may send
  // (frontend/nginx.conf, ADR 0011), and every test is the same visitor:
  // side by side, they went over the limit, and a request was turned down
  // (429). One after the other, quickly, they went over it too: each test
  // first waits for the limit on all requests to refill (e2e/test.ts).
  //
  // The tests together start 5 matches and log in 4 times (an account made
  // counts as a login), and nginx lets one visitor start 6 matches and log in
  // 6 times at once, then 10 and 5 more a minute. A new test that starts
  // matches or logs in uses up this budget: running all the tests twice in
  // the same minute goes over it (8 logins), and the Smoke test in CI, which
  // starts 2 more matches and makes 1 more account, comes after them.
  workers: 1,
  // In CI, each step is printed, and the report is written for the job to
  // keep when a test fails (with a trace: the page at each step).
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
