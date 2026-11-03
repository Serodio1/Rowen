import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { Balloon } from "./Balloon.tsx";

// jsdom has no layout and no scrollIntoView: stub it, and check it is called.
const scrollIntoView = vi.fn();
beforeEach(() => {
  Element.prototype.scrollIntoView = scrollIntoView;
});
afterEach(() => {
  scrollIntoView.mockClear();
  document.body.innerHTML = "";
});

function addTarget() {
  const target = document.createElement("div");
  target.dataset["tutorial"] = "pass";
  document.body.append(target);
  return target;
}

test("the text is in the status region, even with no target", () => {
  render(<Balloon target="pass" text="Press Pass." />);
  expect(screen.getByRole("status")).toHaveTextContent("Press Pass.");
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
});

test("with a target, a note shows the text and the target is scrolled to", () => {
  const target = addTarget();
  render(<Balloon target="pass" text="Press Pass." />);
  expect(screen.getByRole("note")).toHaveTextContent("Press Pass.");
  // StrictMode runs the effect twice.
  expect(scrollIntoView).toHaveBeenCalled();
  expect(scrollIntoView.mock.contexts[0]).toBe(target);
});

test("Next shows even with no target", () => {
  render(<Balloon target="pass" text="Hello." onNext={() => undefined} />);
  expect(screen.getByRole("button", { name: "Next" })).toHaveFocus();
});

test("Next takes the focus and calls onNext once", () => {
  addTarget();
  const onNext = vi.fn();
  render(<Balloon target="pass" text="Hello." onNext={onNext} />);
  const next = screen.getByRole("button", { name: "Next" });
  expect(next).toHaveFocus();
  fireEvent.click(next);
  expect(onNext).toHaveBeenCalledOnce();
});

test("without onNext there is no Next button", () => {
  addTarget();
  render(<Balloon target="pass" text="Hello." />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
