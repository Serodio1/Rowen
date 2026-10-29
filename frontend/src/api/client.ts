import createClient, { type Client, type MethodResponse } from "openapi-fetch";
import type { components, paths } from "./schema";

/** A client for the web API: one method per HTTP method, such as `POST`. */
export type Api = Client<paths>;

// The types of what the API sends, as the client gives them. They are not
// the schema's own types, `components["schemas"]`: the client turns pairs,
// such as the two `players` of a view, into lists (ADR 0008).

/** A deck the player can choose: its id, to start a match, and its name. */
export type Deck = MethodResponse<Api, "get", "/decks">["decks"][number];

/**
 * A match: its id, its version and the player's view of it. The version goes
 * up each time the match changes.
 */
export type Match = MethodResponse<Api, "get", "/matches/{match_id}">;

/**
 * A match after moves were played in it, and what happened: the AI's first
 * moves in a new match, or the player's move and the AI's answer.
 */
export type Played = MethodResponse<Api, "post", "/matches">;

/** One move played: its events, and the view of the match after it. */
export type MovePlayed = Played["moves"][number];

/** Something that happened in the match, as the player may see it. */
export type Event = MovePlayed["events"][number];

/** What the player may see of a match. */
export type View = Match["view"];

/** A card, such as one in the player's hand. */
export type Card = View["hand"][number];

/** One of the moves the player can make, as the view lists them. */
export type Action = View["legal_actions"][number];

/**
 * What the page sends to play: one of the legal actions of a view, and the
 * version of the match that came with that view.
 */
export type Move =
  paths["/matches/{match_id}/actions"]["post"]["requestBody"]["content"]["application/json"];

/** A page of the player's matches, the newest first, and whether more are left. */
export type Matches = MethodResponse<Api, "get", "/matches">;

/** One of the player's matches, in the list: `result` is null while it goes on. */
export type MatchSummary = Matches["matches"][number];

/**
 * How well the AI plays: `easy` is the baseline AI, `normal` and `hard` the
 * Monte Carlo AI, which guesses the cards it can't see (ADR 0018).
 */
export type Level = MatchSummary["level"];

/**
 * What the page sends to start a match: the id of a faction's own deck, or,
 * for a player who is logged in, that of a deck they built, never both; and
 * the level of the AI.
 */
export type NewMatch = ({ deck: string } | { my_deck: string }) & {
  level: Level;
};

/**
 * What a deck built from a faction may hold: each card once, with the most
 * copies it may have, and how many units and special cards a deck needs.
 */
export type Choices = MethodResponse<Api, "get", "/decks/{deck_id}/choices">;

/** A card a built deck may hold, and the most copies of it. */
export type Choice = Choices["cards"][number];

/** The decks the player built, and how many they may keep. */
export type PlayerDecks = MethodResponse<Api, "get", "/my-decks">;

/** A deck the player built: its name, faction and copies of each card. */
export type PlayerDeck = PlayerDecks["decks"][number];

/** What the page sends to build a deck or change one: all of it at once. */
export type DeckChoice =
  paths["/my-decks"]["post"]["requestBody"]["content"]["application/json"];

/** The account the player is logged in with: its username. */
export type Account = MethodResponse<Api, "get", "/session">;

/** What the player sends to make an account or to log in. */
export type Credentials =
  paths["/session"]["post"]["requestBody"]["content"]["application/json"];

/**
 * What went wrong with a request, as the API says it: `"match_not_found"`.
 * A string is the same in the schema's types as in the client's.
 */
export type ErrorCode = components["schemas"]["ErrorCode"];

/**
 * Make a client for the web API, typed from its OpenAPI document: a wrong
 * path, or a field that is missing or of the wrong type, is a TypeScript
 * error.
 *
 * The API is at `/api` on the page's own server, which passes the requests on
 * to the API. The address is a full one (such as `http://localhost:5173/api`), because
 * the `Request` of Node.js, which the tests use, cannot take a relative one.
 *
 * To know whether a request worked, check `data` (`if (!data)`), not
 * `error`: an answer without a JSON body, such as a 502 from a proxy, comes
 * back with an empty `error`. And when no answer comes at all (no network),
 * the call rejects.
 *
 * @param fetch - What sends each request and returns the answer. Tests pass
 *   a fake one, so that no request leaves the test; without it, the client
 *   uses the browser's `fetch`.
 */
export function createApi(
  fetch?: (request: Request) => Promise<Response>,
): Api {
  return createClient<paths>({
    baseUrl: `${window.location.origin}/api`,
    fetch,
  });
}
