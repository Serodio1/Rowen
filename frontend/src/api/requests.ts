/**
 * The page's requests to the web API, for TanStack Query to send.
 *
 * TanStack Query keeps the answers in a cache, under a key such as
 * `["match", id]`, and tells the page whether a request is still waiting or
 * didn't work. A query reads something and may be sent again, such as the
 * decks; a mutation changes something, such as playing a move, and is only
 * sent when the page says so.
 */
import { QueryClient, queryOptions } from "@tanstack/react-query";
import type { Action, Api, ErrorCode } from "./client.ts";

// What a request says when no answer came, or none from the API: the network
// is down, the API isn't running, or a proxy answered in its place.
const UNREACHABLE = "Could not reach the server.";

/** A request that didn't work: the API turned it down, or no answer came. */
export class RequestError extends Error {
  /**
   * What went wrong, as the API says it, such as `"match_not_found"`, or
   * `null` when no answer came from the API.
   */
  readonly code: ErrorCode | null;

  constructor(code: ErrorCode | null, message: string) {
    super(message);
    this.name = "RequestError";
    this.code = code;
  }
}

// Every request here goes through `send`, which throws a `RequestError` when
// the API turns it down or doesn't answer: this tells TypeScript, so the
// `error` TanStack Query gives the page has a `code`. (An answer of the wrong
// shape could still fail with another error, without one; the API's tests
// check the shape of its answers.)
declare module "@tanstack/react-query" {
  interface Register {
    defaultError: RequestError;
  }
}

/**
 * Make the cache the page keeps its answers in.
 *
 * `main.tsx` makes the one the page uses, and each test makes its own.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // The decks don't change while the page is open, and a match only
        // changes when the player plays, which puts the new view in the
        // cache. So an answer that came is never asked for again on its own.
        // A request that didn't work is, when the player comes back to the
        // page, as if they had tried again.
        staleTime: Infinity,
        // A request that didn't work says so at once, and the player can try
        // again. (A mutation is never sent again on its own.)
        retry: false,
        // Send each request even when the browser says it is offline, so it
        // fails at once and the page says so. By default TanStack Query would
        // hold it back without a word, and send it when the network is back,
        // maybe long after: for a move, one the player may have given up on.
        // (So nothing is asked for again on its own when the network is
        // back, either.)
        networkMode: "always",
      },
      mutations: {
        networkMode: "always",
      },
    },
  });
}

/** The decks the player can choose from. */
export function decksQuery(api: Api) {
  return queryOptions({
    queryKey: ["decks"],
    queryFn: async () => (await send(api.GET("/decks"))).decks,
    // Keep them while the page is open, even during a long match, so playing
    // again never waits for them. (By default an answer no part of the page
    // shows is dropped after 5 minutes.)
    gcTime: Infinity,
  });
}

/**
 * The player's view of the match with the id `matchId`.
 *
 * Starting the match and playing a move put the view of their answer here,
 * so the page only asks for it when its view may be out of date: after a
 * move that didn't work.
 */
export function matchQuery(api: Api, matchId: string) {
  return queryOptions({
    queryKey: ["match", matchId],
    queryFn: async () => {
      const match = await send(
        api.GET("/matches/{match_id}", {
          params: { path: { match_id: matchId } },
        }),
      );
      return match.view;
    },
  });
}

/** Start a match against the AI with the deck `deck`. */
export function startMatch(api: Api, deck: string) {
  return send(api.POST("/matches", { body: { deck } }));
}

/**
 * Play `action`, one of the legal actions in the view, as the view lists it.
 * The answer has the view after the AI's answer.
 */
export function playAction(api: Api, matchId: string, action: Action) {
  return send(
    api.POST("/matches/{match_id}/actions", {
      params: { path: { match_id: matchId } },
      body: action,
    }),
  );
}

/**
 * Wait for the answer to `request` and return its data, or throw a
 * `RequestError` if the request didn't work.
 */
async function send<T>(
  request: Promise<{ data?: T; error?: unknown }>,
): Promise<T> {
  let answer;
  try {
    answer = await request;
  } catch {
    // No answer came at all.
    throw new RequestError(null, UNREACHABLE);
  }
  // Check the data, not the error: an answer without a JSON body, such as a
  // 502 from a proxy, comes back with no data and an empty error.
  if (answer.data === undefined) {
    throw turnedDown(answer.error);
  }
  return answer.data;
}

/**
 * Return the error for an answer without data. Every error the API sends has
 * a code and a message (its OpenAPI document says so); an answer without
 * them didn't come from the API.
 */
function turnedDown(error: unknown): RequestError {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return new RequestError(error.code as ErrorCode, error.message);
  }
  return new RequestError(null, UNREACHABLE);
}
