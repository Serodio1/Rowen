import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import "@fontsource-variable/cinzel";
import "@fontsource/alegreya-sans/400.css";
import "@fontsource/alegreya-sans/700.css";
import "./index.css";
import { createApi } from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";

const root = document.getElementById("root");
if (root === null) {
  throw new Error('index.html has no element with id="root"');
}

const queryClient = createQueryClient();

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App api={createApi()} />
    </QueryClientProvider>
  </StrictMode>,
);
