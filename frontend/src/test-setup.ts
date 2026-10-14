import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Render as main.tsx does, in StrictMode, so effects run twice as in development.
configure({ reactStrictMode: true });

// Remove what each test rendered, so the next test starts from an empty page.
afterEach(() => {
  cleanup();
});
