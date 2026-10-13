import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/ and https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // A simulated browser page, so components can be rendered in Node.
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
