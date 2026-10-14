import { afterEach, expect, test, vi } from "vitest";
import { DECKS } from "../test-data.ts";
import { createApi } from "./client.ts";
import { createQueryClient, decksQuery } from "./requests.ts";

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
