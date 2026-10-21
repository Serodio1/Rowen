/**
 * The match in words: cards, actions and events as text, for the page to
 * show.
 *
 * The functions here only turn data into text, so they are tested on their
 * own. The cards, the legal actions, the scores and who won come from the
 * server (ADR 0002): here the rounds that end are only numbered, and the
 * winner's score put first.
 */
import type { Action, Card, Event, View } from "./api/client.ts";

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
 * Actions and events name their cards by id. The cards an action names are
 * all in the view: in the hand, in a discard pile (to revive) or on the board
 * (to take back with a Scarecrow). Those an event names are in the view
 * before or after it: a card that leaves the view, such as a unit a
 * Scarecrow takes back to the AI's hand, was in the view before. (All but a
 * unit the AI both plays and takes back between two of the player's moves,
 * once the player passed: it is named by its id.)
 */
export function cardNames(view: View): Map<string, string> {
  const cards: Card[] = [...view.hand];
  for (const side of view.players) {
    cards.push(...side.discard, ...side.weather);
    for (const row of [side.rows.melee, side.rows.ranged, side.rows.siege]) {
      cards.push(...row.units.map((unit) => unit.card), ...row.scarecrows);
      if (row.horn !== null) {
        cards.push(row.horn);
      }
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

/**
 * What happened after one request: the sentences of its events, in order,
 * and how the round went if one ended.
 */
export interface Happened {
  sentences: string[];
  /** How the last round that ended went, if one did, as in `eventText`. */
  round: string | null;
}

/**
 * Return what happened in `events`, for the player of the view.
 *
 * @param viewer - The player of the view: 0 or 1.
 * @param names - The name of every card, by id: those of the views before
 *   and after the events, from {@link cardNames}.
 * @param round - The round the events start in. Each round that ends in them
 *   is the next one.
 */
export function happened(
  events: readonly Event[],
  viewer: number,
  names: ReadonlyMap<string, string>,
  round: number,
): Happened {
  const sentences: string[] = [];
  let result: string | null = null;
  for (const event of events) {
    const sentence = eventText(event, viewer, names, round);
    sentences.push(sentence);
    if (event.type === "round_ended") {
      result = sentence;
      round += 1;
    }
  }
  return { sentences, round: result };
}

/**
 * Return an event as one sentence for the player `viewer`.
 *
 * For example `The AI played Sniper in the ranged row.`, as in the CLI. The
 * end of a round says how it went, with the winner's score first: `Round 1:
 * you won, 34 to 28.` Every kind of event has a case, so TypeScript reports
 * a missing return when a new kind has no text yet.
 *
 * @param names - The name of every card, by id. A card it doesn't name is
 *   named by its id.
 * @param round - The round the event is in.
 */
export function eventText(
  event: Event,
  viewer: number,
  names: ReadonlyMap<string, string>,
  round: number,
): string {
  const name = (id: string) => names.get(id) ?? id;
  const who = (player: number) => (player === viewer ? "You" : "The AI");
  const whose = (player: number) => (player === viewer ? "your" : "the AI's");
  // A unit on the other player's side, a Spy, says whose side it is on.
  const where = (row: string, side: number, player: number) =>
    side === player ? `in the ${row} row` : `in ${whose(side)} ${row} row`;

  switch (event.type) {
    case "unit_played":
      return `${who(event.player)} played ${name(event.card)} ${where(event.row, event.side, event.player)}.`;
    case "unit_revived":
      return `${who(event.player)} revived ${name(event.card)} ${where(event.row, event.side, event.player)}.`;
    case "unit_mustered":
      return `${name(event.card)} came from ${whose(event.player)} ${event.from_hand ? "hand" : "deck"} to the ${event.row} row.`;
    case "cards_drawn":
      return `${who(event.player)} drew ${event.cards.map(name).join(", ")}.`;
    case "opponent_drew":
      return `${who(event.player)} drew ${event.count === 1 ? "1 card" : `${String(event.count)} cards`}.`;
    case "weather_played":
      return `${who(event.player)} played ${name(event.card)}: weather on both ${event.row} rows.`;
    case "weather_cleared":
      return `${who(event.player)} played ${name(event.card)} and cleared all weather.`;
    case "horn_played":
      return `${who(event.player)} played ${name(event.card)} in the ${event.row} row.`;
    case "scarecrow_played":
      return `${who(event.player)} played ${name(event.card)} in the ${event.row} row and took back ${name(event.unit)}.`;
    case "wildfire_played":
      return `${who(event.player)} played ${name(event.card)}.`;
    case "unit_destroyed":
      return `${name(event.card)} was destroyed in ${whose(event.side)} ${event.row} row.`;
    case "player_passed":
      return `${who(event.player)} passed.`;
    case "round_ended": {
      // The winner has the higher score.
      const high = Math.max(...event.scores);
      const low = Math.min(...event.scores);
      const how =
        event.winner === null
          ? "a tie"
          : `${event.winner === viewer ? "you" : "the AI"} won`;
      return `Round ${String(round)}: ${how}, ${String(high)} to ${String(low)}.`;
    }
    case "match_ended":
      return event.winner === null
        ? "Match over. It's a draw."
        : `Match over. ${who(event.winner)} won the match.`;
    case "card_redrawn":
      return `${who(event.player)} swapped ${name(event.card)} for ${name(event.drawn)}.`;
    case "opponent_redrew":
      return `${who(event.player)} swapped a card.`;
    case "redraw_ended":
      return `${who(event.player)} finished swapping.`;
  }
}
