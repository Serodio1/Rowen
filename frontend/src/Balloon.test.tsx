import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { arrowSide } from "./arrowSide.ts";
import { Balloon } from "./Balloon.tsx";

// jsdom has no layout and no scrollIntoView: stub it, and check it is called.
const scrollIntoView = vi.fn();
beforeEach(() => {
  Element.prototype.scrollIntoView = scrollIntoView;
});
afterEach(() => {
  scrollIntoView.mockClear();
  for (const target of added.splice(0)) target.remove();
});

const PASS = '[data-tutorial="pass"]';
const ROW = '[data-tutorial="row"]';
const added: HTMLElement[] = [];
function addTarget(name = "pass") {
  const target = document.createElement("div");
  target.dataset["tutorial"] = name;
  document.body.append(target);
  added.push(target);
  return target;
}

test("the text is in the status region, even with no target", () => {
  render(<Balloon target={PASS} text="Press Pass." />);
  expect(screen.getByRole("status")).toHaveTextContent("Press Pass.");
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
});

test("with a target, a note shows the text and the target is scrolled to", () => {
  const target = addTarget();
  render(<Balloon target={PASS} text="Press Pass." />);
  expect(screen.getByRole("note")).toHaveTextContent("Press Pass.");
  // StrictMode runs the effect twice.
  expect(scrollIntoView).toHaveBeenCalled();
  expect(scrollIntoView.mock.contexts[0]).toBe(target);
});

test("Next shows even with no target", () => {
  render(<Balloon target={PASS} text="Hello." onNext={() => undefined} />);
  expect(screen.getByRole("button", { name: "Next" })).toHaveFocus();
});

test("Next takes the focus and calls onNext once", () => {
  addTarget();
  const onNext = vi.fn();
  render(<Balloon target={PASS} text="Hello." onNext={onNext} />);
  const next = screen.getByRole("button", { name: "Next" });
  expect(next).toHaveFocus();
  fireEvent.click(next);
  expect(onNext).toHaveBeenCalledOnce();
});

test("focusing Next doesn't scroll: the balloon may not be placed yet", () => {
  addTarget();
  const focus = vi.spyOn(HTMLElement.prototype, "focus");
  render(<Balloon target={PASS} text="Hello." onNext={() => undefined} />);
  expect(focus).toHaveBeenCalledWith({ preventScroll: true });
  focus.mockRestore();
});

test("a held Enter on Next doesn't click it again", () => {
  addTarget();
  render(<Balloon target={PASS} text="Hello." onNext={() => undefined} />);
  const next = screen.getByRole("button", { name: "Next" });
  // fireEvent returns false when the default (the click) is prevented.
  expect(fireEvent.keyDown(next, { key: "Enter", repeat: true })).toBe(false);
  expect(fireEvent.keyDown(next, { key: "Enter" })).toBe(true);
});

test("without onNext there is no Next button", () => {
  addTarget();
  render(<Balloon target={PASS} text="Hello." />);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("a target that mounts later, in a new step, gets the panel", () => {
  const { rerender } = render(<Balloon target={PASS} text="One." />);
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
  addTarget("row");
  rerender(<Balloon target={ROW} text="Two." />);
  expect(screen.getByRole("note")).toHaveTextContent("Two.");
});

test("a new text keeps the status node and moves the focus to Next", () => {
  addTarget();
  const { rerender } = render(
    <Balloon target={PASS} text="One." onNext={() => undefined} />,
  );
  const status = screen.getByRole("status");
  const next = screen.getByRole("button", { name: "Next" });
  next.blur();
  rerender(<Balloon target={PASS} text="Two." onNext={() => undefined} />);
  expect(screen.getByRole("status")).toBe(status);
  expect(status).toHaveTextContent("Two.");
  expect(screen.getByRole("button", { name: "Next" })).toHaveFocus();
});

test("the arrow sits on the edge facing the target", () => {
  addTarget();
  const { container } = render(<Balloon target={PASS} text="One." />);
  // jsdom has no layout, so floating-ui keeps the placement "top".
  expect(container.ownerDocument.querySelector("[data-side]")).toHaveAttribute(
    "data-side",
    "bottom",
  );
});

test("arrowSide is the side opposite the placement", () => {
  expect(arrowSide("top")).toBe("bottom");
  expect(arrowSide("bottom-start")).toBe("top");
  expect(arrowSide("left")).toBe("right");
  expect(arrowSide("right-end")).toBe("left");
});

test("hidden, it shows nothing; shown again, it finds its target anew", () => {
  const old = addTarget();
  const { rerender } = render(<Balloon target={PASS} text="One." shown />);
  expect(screen.getByRole("note")).toBeInTheDocument();
  rerender(<Balloon target={PASS} text="One." shown={false} />);
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
  // The board drew a new node for the same target meanwhile.
  old.remove();
  const target = addTarget();
  scrollIntoView.mockClear();
  rerender(<Balloon target={PASS} text="One." shown />);
  expect(screen.getByRole("note")).toHaveTextContent("One.");
  expect(scrollIntoView.mock.contexts[0]).toBe(target);
});
