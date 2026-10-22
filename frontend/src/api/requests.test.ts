import { afterEach, expect, test, vi } from "vitest";
import { DECKS } from "../test-data.ts";
import { createApi } from "./client.ts";
import {
  createQueryClient,
  decksQuery,
  RequestError,
  sessionQuery,
} from "./requests.ts";

afterEach(() => {
  vi.useRealTimers();
});

test("the decks stay in the cache while the page is open, even when it doesn't show them", async () => {
  vi.useFakeTimers();
  const api = createApi(() => Promise.resolve(Response.json({ decks: DECKS })));
  const client = createQueryClient();
  const query = decksQuery(api);

  // Nothing shows them, as during a match: by default TanStack Query would
  // drop them after 5 minutes.
  await client.query(query);
  await vi.advanceTimersByTimeAsync(60 * 60 * 1000);

  expect(client.getQueryData(query.queryKey)).toEqual(DECKS);
});

test("a guest is no account, but another error is an error", async () => {
  const answering = (status: number, code: string) =>
    createApi(() =>
      Promise.resolve(Response.json({ code, message: code }, { status })),
    );

  const guest = sessionQuery(answering(401, "not_logged_in"));
  const broken = sessionQuery(answering(500, "server_error"));

  expect(await createQueryClient().query(guest)).toBeNull();
  await expect(createQueryClient().query(broken)).rejects.toEqual(
    new RequestError("server_error", "server_error"),
  );
});
