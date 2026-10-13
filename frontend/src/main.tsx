import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import { createApi } from "./api/client.ts";

const root = document.getElementById("root");
if (root === null) {
  throw new Error('index.html has no element with id="root"');
}

createRoot(root).render(
  <StrictMode>
    <App api={createApi()} />
  </StrictMode>,
);
