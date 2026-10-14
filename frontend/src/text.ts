/**
 * The match in words: cards and actions as text, for the page to show.
 *
 * The functions here only turn data into text, so they are tested on their
 * own. Nothing is worked out here: the cards, the legal actions and every
 * number come from the server (ADR 0002).
 */
import type { Action, Card, View } from "./api/client.ts";

/** A unit on the board, with its strength now. */
type Unit = View["players"][number]["rows"]["melee"]["units"][number];

/**
 * Return a card with what a player needs to know about it.
 *
 * For example `Soldier (4 melee/ranged, agile)`, `Hoarfrost (weather on
 * melee)` or `War Horn (special)`, as in the CLI.
 */
export function cardText(card: Card): string {
  if (card.type === "special") {
    return card.weather_row === null
      ? `${card.name} (special)`
      : `${card.name} (weather on ${card.weather_row})`;
  }

  const details = [`${String(card.strength)} ${card.rows.join("/")}`];
  if (card.legend) {
    details.push("legend");
  }
  if (card.ability !== null) {
    details.push(card.ability);
  }
  return `${card.name} (${details.join(", ")})`;
}

/**
 * Return a unit on the board, with its strength now if weather or another
 * card changed it.
 *
 * For example `Soldier (4 melee/ranged, agile), now 1`.
 */
export function unitText(unit: Unit): string {
  const text = cardText(unit.card);
  return unit.strength === unit.card.strength
    ? text
    : `${text}, now ${String(unit.strength)}`;
}

/**
 * Return the short words a card shows under its name: where it goes and what
 * it does.
 *
 * For example `["Siege", "Muster"]`, `["Weather", "Melee"]` for Hoarfrost, or
 * `["Special"]`. A unit that may go in more than one row shows only what it
 * does, such as `["Agile"]`: the words must fit on the card, and `cardText`
 * says it all.
 */
export function cardLabels(card: Card): string[] {
  if (card.type === "special") {
    return card.weather_row === null
      ? ["Special"]
      : ["Weather", capitalized(card.weather_row)];
  }

  const [row, ...others] = card.rows;
  const labels =
    row !== undefined && others.length === 0 ? [capitalized(row)] : [];
  if (card.ability !== null) {
    labels.push(capitalized(card.ability));
  }
  return labels;
}

/** Return a word with its first letter in capitals: `melee` is `Melee`. */
function capitalized(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

/**
 * Return who won the match, for the player of the view, once it is over.
 */
export function resultText(view: View): string {
  if (view.winner === null) {
    return "The match is a draw.";
  }
  return view.winner === view.player
    ? "You won the match!"
    : "The AI won the match.";
}

/**
 * Return the name of every card the view shows, by id.
 *
 * Actions name their cards by id. The cards they name are all in the view: in
 * the hand, in a discard pile (to revive) or on the board (to take back with a
 * Scarecrow).
 */
export function cardNames(view: View): Map<string, string> {
  const cards: Card[] = [...view.hand];
  for (const side of view.players) {
    cards.push(...side.discard);
    for (const row of [side.rows.melee, side.rows.ranged, side.rows.siege]) {
      cards.push(...row.units.map((unit) => unit.card));
    }
  }
  return new Map(cards.map((card) => [card.id, card.name]));
}

/**
 * Return an action as one of the player's choices.
 *
 * For example `Play Sniper in the ranged row`. Every kind of action has a
 * case, so TypeScript reports a missing return when a new kind has no text
 * yet.
 *
 * @param names - The name of every card, by id, from {@link cardNames}.
 */
export function actionText(
  action: Action,
  names: ReadonlyMap<string, string>,
): string {
  // The id itself if the view didn't show the card, which shouldn't happen.
  const name = (id: string) => names.get(id) ?? id;

  switch (action.type) {
    case "play_unit":
      return `Play ${name(action.card)} in the ${action.row} row`;
    case "play_special":
      return `Play ${name(action.card)}`;
    case "play_horn":
      return `Play ${name(action.card)} in the ${action.row} row`;
    case "play_scarecrow":
      return `Play ${name(action.card)} in the ${action.row} row, taking back ${name(action.unit)}`;
    case "pass":
      return "Pass";
    case "revive":
      return `Revive ${name(action.card)} in the ${action.row} row`;
    case "redraw":
      return `Swap ${name(action.card)}`;
    case "end_redraw":
      return "Keep this hand";
  }
}
