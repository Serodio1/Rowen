import {
  arrow,
  autoUpdate,
  flip,
  offset,
  shift,
  useFloating,
} from "@floating-ui/react-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { arrowSide, type Side } from "./arrowSide.ts";
import { BUTTON } from "./styles.ts";

// Each side's position and the two borders that make the rotated square a point.
const ARROW_CLASSES: Record<Side, string> = {
  bottom: "-bottom-2 border-r-2 border-b-2",
  top: "-top-2 border-t-2 border-l-2",
  right: "-right-2 border-t-2 border-r-2",
  left: "-left-2 border-b-2 border-l-2",
};

/**
 * The tutorial's speech balloon: it points at the element with
 * `data-tutorial="<target>"`, and follows it. The text is also in a hidden
 * status region, so a screen reader reads it even if there is no target.
 * It is a `note`, not a `dialog`: nothing else on the page is blocked.
 */
export function Balloon({
  target,
  text,
  onNext,
}: {
  target: string;
  text: string;
  onNext?: () => void;
}) {
  const [element, setElement] = useState<HTMLElement | null>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const [arrowElement, setArrowElement] = useState<HTMLDivElement | null>(null);
  const {
    refs: { setFloating },
    floatingStyles,
    placement,
    middlewareData,
  } = useFloating({
    placement: "top",
    elements: { reference: element },
    middleware: [
      offset(12),
      flip(),
      shift({ padding: 8 }),
      arrow({ element: arrowElement }),
    ],
    whileElementsMounted: autoUpdate,
  });

  // The target may mount after the balloon, and changes from step to step.
  useLayoutEffect(() => {
    const found = document.querySelector<HTMLElement>(
      `[data-tutorial="${target}"]`,
    );
    found?.scrollIntoView({ block: "nearest" });
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reads the DOM
    setElement(found);
  }, [target, text]);

  // A new step: the keyboard goes to Next. (It is also a new node if the
  // target appeared or went away.)
  useEffect(() => {
    nextRef.current?.focus();
  }, [text, element]);

  const side = arrowSide(placement);

  // Without a target the button still shows, so the tutorial can't get stuck.
  const next = onNext && (
    <button type="button" ref={nextRef} className={BUTTON} onClick={onNext}>
      Next
    </button>
  );

  return (
    <>
      <p role="status" className="sr-only">
        {text}
      </p>
      {element ? (
        <div
          ref={setFloating}
          role="note"
          style={floatingStyles}
          className="wood z-50 flex max-w-xs flex-col items-center gap-2 rounded-xl border-2 border-gold-600 p-3 text-center shadow-2xl shadow-black/60"
        >
          <p>{text}</p>
          {next}
          <div
            ref={setArrowElement}
            aria-hidden="true"
            data-side={side}
            className={`absolute size-3 rotate-45 border-gold-600 bg-wood-800 ${ARROW_CLASSES[side]}`}
            style={
              side === "top" || side === "bottom"
                ? { left: middlewareData.arrow?.x }
                : { top: middlewareData.arrow?.y }
            }
          />
        </div>
      ) : (
        next
      )}
    </>
  );
}
