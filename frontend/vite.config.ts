import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/ and https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  // The page calls the web API at /api on its own server (src/api/client.ts):
  // the development server (npm run dev) and the preview of the build
  // (npm run preview) pass those requests on to the API, without the /api.
  // So the API needs no CORS. The API is where uvicorn listens by default.
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    // A simulated browser page, so components can be rendered in Node.
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
