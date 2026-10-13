import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { App } from "./App.tsx";

test("the page shows the name of the game as its main heading", () => {
  render(<App />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Rowen" }),
  ).toBeInTheDocument();
});
