import { useLayoutEffect, useRef } from "react";
import type { Card } from "./api/client.ts";
import { CardFace } from "./CardFace.tsx";
import { TIMES, type CardStep } from "./stage.ts";
import { cardText } from "./text.ts";

/**
 * A card being played, large on the right of the screen, as in the card game
 * of The Witcher 3. Once `flying`, it goes to its place on the board (the
 * element whose `data-cell` is the step's), shrinking to its size, or fades
 * away if it has no place there.
 *
 * It is only a picture: the log says what was played, for screen readers too.
 */
export function Showcase({
  step,
  flying,
}: {
  step: CardStep;
  flying: boolean;
}) {
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
      className="pointer-events-none fixed top-1/2 right-6 z-50 -translate-y-1/2 lg:right-24"
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

/**
 * A card pointed at or focused, large on the right where cards played show,
 * with what it does underneath.
 *
 * A unit on the board whose strength isn't the card's says what it is now.
 *
 * It is only a picture: screen readers read what a card does from the card
 * itself (`aria-description`), and its strength from its name.
 */
export function CardPreview({
  card,
  strength,
}: {
  card: Card;
  strength?: number | undefined;
}) {
  return (
    <div
      aria-hidden
      data-preview={card.id}
      className="pointer-events-none fixed top-1/2 right-6 z-50 flex w-60 -translate-y-1/2 flex-col items-center gap-3 lg:right-16"
    >
      <div className="drop-shadow-2xl [zoom:2.5]">
        <CardFace card={card} name={cardText(card)} size="large" />
      </div>
      {card.type === "unit" &&
        strength !== undefined &&
        strength !== card.strength && (
          <p
            data-now
            className="rounded-md border border-gold-400 bg-wood-950/95 px-3 py-1 font-display text-lg text-gold-200 shadow-lg shadow-black/60"
          >
            Now {strength}
          </p>
        )}
      {card.description.length > 0 && (
        <div className="w-full rounded-lg border border-gold-600 bg-wood-950/95 p-3 text-sm shadow-xl shadow-black/60">
          {card.description.map((text) => (
            <p key={text} className="leading-snug text-parchment">
              {text}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * A big message over the whole screen, for what has no card to show, such as
 * "The AI passed." It never takes a click, and it is only a picture: the log
 * says the same to screen readers.
 */
export function Banner({ text }: { text: string }) {
  return (
    <div
      aria-hidden
      data-banner
      className="pointer-events-none fixed inset-0 z-40 grid place-items-center bg-black/55"
    >
      <p className="animate-show border-y-2 border-gold-400 bg-wood-950/90 px-12 py-6 text-center font-display text-4xl text-gold-200 shadow-2xl shadow-black lg:text-5xl">
        {text}
      </p>
    </div>
  );
}
