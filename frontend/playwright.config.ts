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
