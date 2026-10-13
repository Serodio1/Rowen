import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Remove what each test rendered, so the next test starts from an empty page.
afterEach(() => {
  cleanup();
});
