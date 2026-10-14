import createClient, { type Client, type MethodResponse } from "openapi-fetch";
import type { components, paths } from "./schema";

/** A client for the web API: one method per HTTP method, such as `POST`. */
export type Api = Client<paths>;

// The types of what the API sends, as the client gives them. They are not
// the schema's own types, `components["schemas"]`: the client turns pairs,
// such as the two `players` of a view, into lists (ADR 0008).

/** A deck the player can choose: its id, to start a match, and its name. */
export type Deck = MethodResponse<Api, "get", "/decks">["decks"][number];

/** A match: its id and the player's view of it. */
export type Match = MethodResponse<Api, "get", "/matches/{match_id}">;

/** What the player may see of a match. */
export type View = Match["view"];

/** A card, such as one in the player's hand. */
export type Card = View["hand"][number];

/** One of the moves the player can make, as the view lists them. */
export type Action = View["legal_actions"][number];

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
 * to the API. The address is a full one (`http://localhost:5173/api`), because
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
