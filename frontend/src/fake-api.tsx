import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { App } from "./App.tsx";
import { createApi, type Api } from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";

/**
 * An answer of the fake API: a status and a JSON body, any `Response`, or one
 * that comes when the test says so.
 */
export type Answer =
  { status: number; body: unknown } | Response | Promise<Response>;

/** Return a request's method, path and query, such as `"GET /api/decks"`. */
export function to(request: Request) {
  const url = new URL(request.url);
  return `${request.method} ${url.pathname}${url.search}`;
}

/**
 * Return a client whose `fetch` answers each request with the answer for its
 * method, path and query, such as `"GET /api/matches?before=m1"`, and the
 * requests it got. With no answer for a request, the request fails, as when
 * there is no network. The answers may change during a test.
 */
export function fakeApi(answers: Record<string, Answer>) {
  const requests: Request[] = [];
  const api = createApi((request) => {
    requests.push(request);
    const answer = answers[to(request)];
    if (answer === undefined) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (answer instanceof Response || answer instanceof Promise) {
      // A copy for each request, as a server sends: a body can be read only
      // once, so a second request would fail to read it.
      return Promise.resolve(answer).then((response) => response.clone());
    }
    return Promise.resolve(
      answer.status === 204
        ? // A 204 has no body.
          new Response(null, { status: 204 })
        : Response.json(answer.body, { status: answer.status }),
    );
  });
  return { api, requests };
}

/** Show the page, as `main.tsx` does, with an empty cache of its own. */
export function renderApp(api: Api) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <App api={api} />
    </QueryClientProvider>,
  );
}

/** Show the page with a fake API, and return the requests it got. */
export function showApp(answers: Record<string, Answer>) {
  const { api, requests } = fakeApi(answers);
  renderApp(api);
  return requests;
}

/** Return the requests for one method and path, such as `"GET /api/decks"`. */
export function sent(requests: Request[], where: string) {
  return requests.filter((request) => to(request) === where);
}

/** Wait until a request the page may have just sent has been answered. */
export function settle() {
  return new Promise((resolve) => setTimeout(resolve));
}

/**
 * Return an answer that comes only when the test calls `answer`, so the test
 * can look at the page while the request waits.
 */
export function later() {
  let answer: (response: Response) => void = () => {};
  const response = new Promise<Response>((resolve) => {
    answer = resolve;
  });
  return { response, answer };
}
