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
 * the `fetch` of Node.js, which the tests run on, cannot take a relative one.
 *
 * @param fetch - What sends each request and returns the answer: the
 *   browser's `fetch`, unless a test passes a fake one, so that no request
 *   leaves the test.
 */
export function createApi(
  fetch: (request: Request) => Promise<Response> = (request) =>
    globalThis.fetch(request),
): Api {
  return createClient<paths>({
    baseUrl: `${window.location.origin}/api`,
    fetch,
  });
}
