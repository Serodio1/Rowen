import { expect, test } from "vitest";
import { createApi } from "./client.ts";

/**
 * A fake `fetch` that answers every request with `status` and `body`, and
 * keeps the requests it got, so a test can look at them.
 */
function fakeFetch(status: number, body: unknown) {
  const requests: Request[] = [];
  const fetch = (request: Request) => {
    requests.push(request);
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  };
  return { fetch, requests };
}

test("a request goes to /api on the page's own server, with a JSON body", async () => {
  const { fetch, requests } = fakeFetch(201, { id: "a-match" });
  const api = createApi(fetch);

  await api.POST("/matches", { body: { deck: "humans", level: "easy" } });

  expect(requests).toHaveLength(1);
  const [request] = requests;
  expect(request?.method).toBe("POST");
  expect(request?.url).toBe(`${window.location.origin}/api/matches`);
  expect(request?.headers.get("Content-Type")).toBe("application/json");
  expect(await request?.json()).toEqual({ deck: "humans", level: "easy" });
});

test("the API's answer comes back as data", async () => {
  const match = { id: "a-match", view: { round: 1 } };
  const api = createApi(fakeFetch(201, match).fetch);

  const { data, error } = await api.POST("/matches", {
    body: { deck: "humans", level: "easy" },
  });

  expect(data).toEqual(match);
  expect(error).toBeUndefined();
});

test("a request the API turns down comes back as an error, with its code", async () => {
  const turnedDown = {
    code: "unknown_deck",
    message: "There is no such deck.",
  };
  const api = createApi(fakeFetch(422, turnedDown).fetch);

  const { data, error, response } = await api.POST("/matches", {
    body: { deck: "elves", level: "easy" },
  });

  expect(data).toBeUndefined();
  expect(error).toEqual(turnedDown);
  expect(response.status).toBe(422);
});
