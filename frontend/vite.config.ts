import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/ and https://vitest.dev/config/
export default defineConfig({
  // Tailwind builds the CSS from the classes the components use (src/index.css).
  plugins: [react(), tailwindcss()],
  // The page calls the web API under /api/ on its own server
  // (src/api/client.ts): the development server (npm run dev) and the preview
  // of the build (npm run preview) pass those requests on to the API, without
  // the /api. So the API needs no CORS. The API is where uvicorn listens by
  // default. frontend/nginx.conf does the same in the Docker image (ADR 0009):
  // change both together.
  build: {
    // Every image a file of its own, however small: nginx's
    // Content-Security-Policy (default-src 'self') would block one written
    // into the JavaScript as a data: URL.
    assetsInlineLimit: 0,
  },
  server: {
    proxy: {
      "/api/": {
        target: "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    // A simulated browser page, so components can be rendered in Node.
    environment: "jsdom",
    // Only the tests in src/: those in e2e/ run in a real browser, with
    // Playwright (playwright.config.ts).
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test-setup.ts"],
  },
});
