import createClient, { type Client } from "openapi-fetch";
import type { paths } from "./schema";

/** A client for the web API: one method per HTTP method, such as `POST`. */
export type Api = Client<paths>;

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
