import {
  arrow,
  autoUpdate,
  flip,
  offset,
  shift,
  useFloating,
} from "@floating-ui/react-dom";
import { useEffect, useState } from "react";
import { BUTTON } from "./styles.ts";

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
  const element = document.querySelector<HTMLElement>(
    `[data-tutorial="${target}"]`,
  );
  const [arrowElement, setArrowElement] = useState<HTMLDivElement | null>(null);
  const {
    refs: { setFloating },
    floatingStyles,
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

  useEffect(() => {
    element?.scrollIntoView({ block: "nearest" });
  }, [element]);

  // Without a target the button still shows, so the tutorial can't get stuck.
  const next = onNext && (
    <button type="button" autoFocus className={BUTTON} onClick={onNext}>
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
            className="absolute -bottom-2 size-3 rotate-45 border-r-2 border-b-2 border-gold-600 bg-wood-800"
            style={{ left: middlewareData.arrow?.x }}
          />
        </div>
      ) : (
        next
      )}
    </>
  );
}
