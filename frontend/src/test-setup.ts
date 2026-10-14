import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Render as main.tsx does, in StrictMode, so effects run twice as in development.
configure({ reactStrictMode: true });

// React warns of a mistake, such as two items of a list with the same key,
// with console.error, and goes on: the test would pass. Each call is kept,
// and fails the test once it is over.
let errors: unknown[][] = [];
beforeEach(() => {
  errors = [];
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    errors.push(args);
  });
});

// Remove what each test rendered, so the next test starts from an empty page.
afterEach(() => {
  cleanup();
  vi.mocked(console.error).mockRestore();
  if (errors.length > 0) {
    throw new Error(
      `console.error was called:\n${errors.map((args) => args.join(" ")).join("\n")}`,
    );
  }
});
