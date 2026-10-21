import { useLayoutEffect, useRef } from "react";
import { CardFace } from "./CardFace.tsx";
import { TIMES, type Step } from "./stage.ts";
import { cardText } from "./text.ts";

/**
 * A card being played, large on the right of the screen, as in the card game
 * of The Witcher 3. Once `flying`, it goes to its place on the board (the
 * element whose `data-cell` is the step's), shrinking to its size, or fades
 * away if it has no place there.
 *
 * It is only a picture: the log says what was played, for screen readers too.
 */
export function Showcase({ step, flying }: { step: Step; flying: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const card = ref.current;
    if (!flying || card === null) {
      return;
    }
    const target =
      step.cell === undefined
        ? null
        : document.querySelector(`[data-cell="${step.cell}"]`);
    if (target === null) {
      card.style.opacity = "0";
      return;
    }
    // From the middle of the card here to the middle of its place, and as
    // big as its place.
    const from = card.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    const x = to.left + to.width / 2 - (from.left + from.width / 2);
    const y = to.top + to.height / 2 - (from.top + from.height / 2);
    const scale = Math.min(to.width / from.width, to.height / from.height, 1);
    card.style.transform = `translate(${String(x)}px, ${String(y)}px) scale(${String(scale)})`;
  }, [flying, step]);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed top-1/2 right-6 z-50 -translate-y-1/2 lg:right-76"
    >
      <div
        ref={ref}
        data-showcase={step.card.id}
        style={{ transitionDuration: `${String(TIMES.fly)}ms` }}
        className="animate-show transition-[transform,opacity] ease-in"
      >
        {/* The card of the hand, two and a half times as big. */}
        <div className="drop-shadow-2xl [zoom:2.5]">
          <CardFace card={step.card} name={cardText(step.card)} size="large" />
        </div>
      </div>
    </div>
  );
}
