import { Fragment } from "react";
import type { Card } from "./api/client.ts";
import { cardLabels } from "./text.ts";

/**
 * A card as the page draws it: its strength in a circle, its name and a few
 * words on what it does, on a parchment face in a gold frame. (The art comes
 * in Phase 3.)
 *
 * Screen readers read the card as one picture, with `name` as its text: the
 * face only repeats it in short.
 *
 * @param card - The card to draw.
 * @param strength - A unit's strength now, if weather or another card may
 *   have changed it: the circle is green above the card's own strength, red
 *   below.
 * @param name - What the card is, in words, such as the text of `cardText`.
 * @param size - `"small"` on the board, `"large"` in the hand.
 */
export function CardFace({
  card,
  strength,
  name,
  size = "small",
}: {
  card: Card;
  strength?: number;
  name: string;
  size?: "small" | "large";
}) {
  const legend = card.type === "unit" && card.legend;
  return (
    <div
      role="img"
      aria-label={name}
      className={`relative flex shrink-0 flex-col justify-end gap-0.5 rounded-md border bg-linear-to-b from-parchment to-parchment-dark p-1 text-ink shadow-md shadow-black/50 ${
        size === "small"
          ? "h-20 w-14 lg:h-24 lg:w-16"
          : "h-24 w-16 lg:h-30 lg:w-20"
      } ${legend ? "border-gold-300 ring-2 ring-gold-400/70" : "border-gold-600"}`}
    >
      {/* Where the art goes in Phase 3: for now, the first letter of the name,
          faint (and gone in the high contrast mode of Windows, which would
          draw it over the name). */}
      <span className="absolute inset-x-1 top-1 bottom-7 grid place-items-center rounded-sm border border-gold-600/25 font-display text-3xl font-bold text-ink/15 lg:bottom-8 lg:text-4xl forced-colors:hidden">
        {card.name.charAt(0)}
      </span>
      {card.type === "unit" && (
        <Strength
          own={card.strength}
          now={strength ?? card.strength}
          legend={card.legend}
        />
      )}
      <p className="relative line-clamp-2 text-center font-display text-[0.65rem] leading-tight font-bold lg:text-xs">
        {card.name}
      </p>
      <p className="relative text-center text-[0.625rem] leading-tight uppercase lg:text-[0.65rem]">
        {/* A line may break between two words, never inside one. */}
        {cardLabels(card).map((label, index) => (
          <Fragment key={label}>
            {index > 0 && " "}
            <span className="whitespace-nowrap">
              {index > 0 && "· "}
              {label}
            </span>
          </Fragment>
        ))}
      </p>
    </div>
  );
}

/**
 * A unit's strength in its circle: dark with gold for a Legend, green when
 * the unit is stronger now than its own strength, red when weaker.
 */
function Strength({
  own,
  now,
  legend,
}: {
  own: number;
  now: number;
  legend: boolean;
}) {
  let colour = legend ? "text-gold-200" : "text-ink";
  if (now > own) {
    colour = legend ? "text-green-300" : "text-green-800";
  } else if (now < own) {
    colour = legend ? "text-red-300" : "text-red-700";
  }
  return (
    <span
      className={`absolute -top-1.5 -left-1.5 grid size-6 place-items-center rounded-full border-2 font-display text-xs font-bold shadow lg:size-7 lg:text-sm ${
        legend ? "border-gold-300 bg-ink" : "border-gold-600 bg-parchment"
      } ${colour}`}
    >
      {now}
    </span>
  );
}
