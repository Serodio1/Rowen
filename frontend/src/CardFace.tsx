import type { Card } from "./api/client.ts";
import { artOf, cardIcons, placeholderLook, type Look } from "./cards.ts";
import { Icon } from "./icons.tsx";
import { describe } from "./text.ts";

/**
 * The colours of a card with no art yet, by what its big icon is: a unit's
 * row, or a special card's kind. (A unit that may go in two rows fades from
 * the first to the second.)
 */
const PLACEHOLDER_LOOKS = {
  melee: { from: "from-melee", to: "to-melee" },
  ranged: { from: "from-ranged", to: "to-ranged" },
  siege: { from: "from-siege", to: "to-siege" },
  hoarfrost: { from: "from-hoarfrost", to: "to-wood-900" },
  "thick-fog": { from: "from-thick-fog", to: "to-wood-900" },
  downpour: { from: "from-downpour", to: "to-wood-900" },
  "clear-skies": { from: "from-clear-skies", to: "to-wood-900" },
  "war-horn": { from: "from-war-horn", to: "to-wood-900" },
  wildfire: { from: "from-wildfire", to: "to-wood-900" },
  scarecrow: { from: "from-scarecrow", to: "to-wood-900" },
} satisfies Record<Look, { from: string; to: string }>;

/**
 * A card as the page draws it, upright: its art over the whole face, its
 * strength in a circle at the top left, icons at the top right for where it
 * goes and what it does, and its name in a strip at the bottom. A Legend has
 * a gold frame, a special card a dark one. Until a card has its art
 * (`src/art`), a placeholder shows: its colours, and its big icon.
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
  const art = artOf(card);
  let frame = "border-gold-600";
  if (legend) {
    frame = "border-gold-300 ring-2 ring-gold-400/70";
  } else if (card.type === "special") {
    frame = "border-wood-950 ring-1 ring-gold-600";
  }
  return (
    <div
      role="img"
      aria-label={name}
      // What the card does, for screen readers; and its id and strength, so
      // the page can show it large when it is pointed at or focused.
      aria-description={describe(card)}
      data-card={card.id}
      data-strength={strength}
      className={`relative shrink-0 overflow-hidden rounded-md border-2 bg-wood-900 shadow-md shadow-black/50 ${
        size === "small" ? "h-20 w-14" : "h-24 w-16"
      } ${frame}`}
    >
      {art === undefined ? (
        <Placeholder card={card} />
      ) : (
        <img
          src={art}
          alt=""
          // The hand and the board show many cards: each picture is
          // fetched once it is about to show, and drawn without holding up
          // the page.
          loading="lazy"
          decoding="async"
          className="absolute inset-0 size-full object-cover"
        />
      )}
      {card.type === "unit" && (
        <Strength
          own={card.strength}
          now={strength ?? card.strength}
          legend={card.legend}
        />
      )}
      <div className="absolute top-0.5 right-0.5 flex flex-col items-center gap-0.5">
        {cardIcons(card).map((icon) => (
          <span
            key={icon}
            className="grid size-4 place-items-center rounded-full border border-gold-600 bg-wood-950/85 text-gold-200 lg:size-5"
          >
            <Icon name={icon} className="size-2.5 lg:size-3" />
          </span>
        ))}
      </div>
      <p className="absolute inset-x-0 bottom-0 line-clamp-2 bg-wood-950/85 px-0.5 py-px text-center font-display text-[0.6rem] leading-tight font-bold text-parchment lg:text-[0.65rem]">
        {card.name}
      </p>
    </div>
  );
}

/**
 * What a card with no art yet shows over its face: its colours, and its big
 * icon (gone in the high contrast mode of Windows, as the colours are).
 */
function Placeholder({ card }: { card: Card }) {
  const icon = placeholderLook(card);
  const look = PLACEHOLDER_LOOKS[icon];
  // A unit's last row: the same as its first, unless it may go in two.
  const last =
    card.type === "unit" ? (card.rows.at(-1) ?? card.rows[0]) : undefined;
  const to = last === undefined ? look.to : PLACEHOLDER_LOOKS[last].to;
  return (
    <div
      data-placeholder
      className={`absolute inset-0 grid place-items-center bg-linear-to-br ${look.from} ${to} pt-3 pb-5 forced-colors:hidden`}
    >
      <Icon name={icon} className="size-1/2 text-white/30" />
    </div>
  );
}

/**
 * A unit's strength in its circle: dark with gold for a Legend, green when
 * the unit is stronger now than its own strength, red when weaker. An arrow
 * up or down says it too, for those who can't tell the colours apart (screen
 * readers read it in the card's name, such as "now 1").
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
      // A new strength is a new circle, which bumps.
      key={now}
      className={`absolute top-0.5 left-0.5 grid size-6 place-items-center rounded-full border-2 font-display text-xs font-bold shadow shadow-black/60 motion-safe:animate-bump lg:size-7 lg:text-sm ${
        legend ? "border-gold-300 bg-ink" : "border-gold-600 bg-parchment"
      } ${colour}`}
    >
      {now}
      {now !== own && (
        <svg
          viewBox="0 0 10 10"
          aria-hidden
          data-change={now > own ? "up" : "down"}
          className={`absolute -right-1 -bottom-1 size-3 fill-current drop-shadow lg:size-3.5 ${colour}`}
        >
          <path d={now > own ? "M5 1 9.5 9h-9z" : "M5 9 .5 1h9z"} />
        </svg>
      )}
    </span>
  );
}
