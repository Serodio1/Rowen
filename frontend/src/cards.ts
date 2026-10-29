/**
 * What the page draws on each card, apart from its words: its art and its
 * icons. Rules stay on the server: these only read the card's data.
 */
import type { Card } from "./api/client.ts";
import type { IconName } from "./icons.tsx";

/**
 * The art of the cards: one picture for each kind of card, in
 * `src/art/<id>.webp`, named by the card's id (such as `soldier.webp`).
 *
 * Vite finds the files when it builds the page, and gives each one an
 * address with a hash of its content, so a browser fetches a picture again
 * only when it changed (nginx keeps /assets/ cached for a year). A card with
 * no file shows a placeholder.
 */
const ART = import.meta.glob<string>("./art/*.webp", {
  eager: true,
  import: "default",
  query: "?url",
});

/**
 * Return the address of a card's art, or `undefined` if it has none yet.
 *
 * @param art - The art by file, as `import.meta.glob` finds it: tests pass
 *   their own.
 */
export function artOf(
  card: Pick<Card, "id">,
  art: Record<string, string> = ART,
): string | undefined {
  return art[`./art/${card.id}.webp`];
}

/**
 * Return the icons a card shows by its strength: where it goes and what it
 * does.
 *
 * For example the siege row and Muster, or Hoarfrost and the melee row it
 * hits. A unit that may go in more than one row shows only what it does
 * (Agile): its rows are in its name for screen readers (`cardText`).
 */
export function cardIcons(card: Card): IconName[] {
  if (card.type === "special") {
    return card.weather_row === null
      ? [card.kind]
      : [card.kind, card.weather_row];
  }
  const [row, ...others] = card.rows;
  const icons: IconName[] =
    row !== undefined && others.length === 0 ? [row] : [];
  if (card.ability !== null) {
    icons.push(card.ability);
  }
  return icons;
}

/** What a card with no art yet looks like: a row, or a kind of special card. */
export type Look =
  | Extract<Card, { type: "unit" }>["rows"][number]
  | Extract<Card, { type: "special" }>["kind"];

/**
 * Return what a card with no art yet looks like, and its big icon: its first
 * row for a unit, what it is for a special card.
 */
export function placeholderLook(card: Card): Look {
  return card.type === "special" ? card.kind : (card.rows[0] ?? "melee");
}
