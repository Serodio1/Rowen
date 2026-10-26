import { QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { expect, test } from "vitest";
import { App } from "./App.tsx";
import {
  createApi,
  type Match,
  type Matches,
  type MatchSummary,
  type Played,
} from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";
import { DECKS, view } from "./test-data.ts";

/** An answer of the fake API: a status and a JSON body. */
type Answer = { status: number; body: unknown };

/**
 * Show the page with a fake API, which answers each request with the answer
 * for its method, path and query, such as `"GET /api/matches?before=m1"`,
 * and return the requests it got. The answers may change during a test.
 */
function renderApp(answers: Record<string, Answer>) {
  const requests: string[] = [];
  const api = createApi((request) => {
    const url = new URL(request.url);
    const to = `${request.method} ${url.pathname}${url.search}`;
    requests.push(to);
    const answer = answers[to];
    if (answer === undefined) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    return Promise.resolve(
      answer.status === 204
        ? // A 204 has no body.
          new Response(null, { status: 204 })
        : Response.json(answer.body, { status: answer.status }),
    );
  });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <App api={api} />
    </QueryClientProvider>,
  );
  return requests;
}

const RUI = {
  "GET /api/decks": { status: 200, body: { decks: DECKS } },
  "GET /api/session": { status: 200, body: { username: "rui" } },
};

const STARTED_AT = "2026-10-22T13:30:00Z";

/** Return a match of the list: one that isn't over, unless `changes` say. */
function summary(changes: Partial<MatchSummary> = {}): MatchSummary {
  return {
    id: "a-match",
    deck: "humans",
    ai_deck: "robots",
    started_at: STARTED_AT,
    result: null,
    ...changes,
  };
}

const WON = summary({
  id: "won",
  result: {
    outcome: "won",
    rounds: [
      { player: 10, ai: 12 },
      { player: 9, ai: 4 },
      { player: 7, ai: 3 },
    ],
    ended_at: STARTED_AT,
  },
});

/** Return the answer with a page of matches. */
function page(matches: MatchSummary[], more = false): Answer {
  return { status: 200, body: { matches, more } satisfies Matches };
}

/** Return the answer with the stats of the decks. */
function stats(decks: unknown[]): Answer {
  return { status: 200, body: { decks } };
}

/** Open the list of the player's matches. */
async function openMatches() {
  fireEvent.click(await screen.findByRole("button", { name: "My matches" }));
}

test("a player who is logged in sees how their matches with each deck ended, and the matches", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([{ deck: "humans", won: 2, lost: 1, drawn: 0 }]),
    "GET /api/matches": page([summary(), WON]),
  });
  await openMatches();

  expect(screen.getByRole("heading", { name: "My matches" })).toHaveFocus();
  // The other button would leave the list.
  expect(
    screen.queryByRole("button", { name: "My matches" }),
  ).not.toBeInTheDocument();
  const table = await screen.findByRole("table", {
    name: "Matches won, lost and drawn",
  });
  expect(
    within(table)
      .getAllByRole("row")
      .map((row) => row.textContent),
  ).toEqual(["DeckWonLostDrawn", "Humans210"]);

  const items = await screen.findAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    expect.stringContaining("Humans against Robots"),
    expect.stringContaining("Won: 10 to 12, 9 to 4, 7 to 3"),
  ]);
  expect(items[0]).toHaveTextContent("Not over yet.");
  // The date as the player's browser writes it, with the time for machines.
  const time = within(items[0] as HTMLElement).getByText(
    new Date(STARTED_AT).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }),
  );
  expect(time).toHaveAttribute("datetime", STARTED_AT);
  // Only a match that isn't over can be played on.
  expect(
    within(items[0] as HTMLElement).getByRole("button", { name: "Resume" }),
  ).toHaveAccessibleDescription(expect.stringContaining("Not over yet."));
  expect(
    within(items[1] as HTMLElement).queryByRole("button"),
  ).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(
    screen.getByRole("heading", { name: "Choose your deck" }),
  ).toHaveFocus();
});

test("a guest has no list of matches", async () => {
  renderApp({
    ...RUI,
    "GET /api/session": {
      status: 401,
      body: { code: "not_logged_in", message: "The player isn't logged in." },
    },
  });

  await screen.findByRole("button", { name: "Log in" });
  expect(
    screen.queryByRole("button", { name: "My matches" }),
  ).not.toBeInTheDocument();
});

test("with no match yet, the list says so", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([]),
  });
  await openMatches();

  expect(await screen.findByText("No match finished yet.")).toBeInTheDocument();
  expect(
    await screen.findByText("No match yet: choose a deck to play one."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
});

test("the older matches come a page at a time, from the last one shown", async () => {
  const requests = renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary({ id: "newest" })], true),
    "GET /api/matches?before=newest": page([summary({ id: "older" })], true),
    "GET /api/matches?before=older": page([WON]),
  });
  await openMatches();
  expect(await screen.findAllByRole("listitem")).toHaveLength(1);

  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  // The last page says there are no more.
  expect(
    screen.queryByRole("button", { name: "Show more" }),
  ).not.toBeInTheDocument();
  expect(requests.filter((to) => to.startsWith("GET /api/matches"))).toEqual([
    "GET /api/matches",
    "GET /api/matches?before=newest",
    "GET /api/matches?before=older",
  ]);
});

test("a list that didn't come says why, and can be asked for again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/stats": stats([]),
  };
  renderApp(answers);
  await openMatches();

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
  answers["GET /api/matches"] = page([WON]);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(await screen.findAllByRole("listitem")).toHaveLength(1);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("resuming a match gets it as it is now, and its end shows every round", async () => {
  const before = view({ round: 2, legal_actions: [{ type: "pass" }] });
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  type RoundEnded = Match["rounds"][number];
  const first: RoundEnded = {
    type: "round_ended",
    scores: [10, 12],
    winner: 1,
  };
  const second: RoundEnded = { type: "round_ended", scores: [9, 4], winner: 0 };
  const third: RoundEnded = { type: "round_ended", scores: [7, 3], winner: 0 };
  const requests = renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 200,
      body: {
        id: "a-match",
        version: 7,
        view: before,
        rounds: [first],
      } satisfies Match,
    },
    "POST /api/matches/a-match/actions": {
      status: 200,
      body: {
        id: "a-match",
        version: 8,
        view: over,
        // The page never saw the first round end: the API says how it went.
        rounds: [first, second, third],
        moves: [
          {
            events: [second, third, { type: "match_ended", winner: 0 }],
            view: over,
          },
        ],
      } satisfies Played,
    },
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));

  expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
  expect(requests).toContain("GET /api/matches/a-match");
  fireEvent.click(screen.getByRole("button", { name: "Pass" }));

  const end = await screen.findByRole("dialog", { name: "You won the match!" });
  expect(
    within(end)
      .getAllByRole("row")
      .map((row) => row.textContent),
  ).toEqual(["RoundYouThe AIWon by", "11012The AI", "294You", "373You"]);
});

test("a match that can't be resumed says why, and the list stays", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 404,
      body: {
        code: "match_not_found",
        message: "There is no match with this id.",
      },
    },
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "There is no match with this id.",
  );
  expect(screen.getByRole("heading", { name: "My matches" })).toBeVisible();
});

test("logging out during a match leaves it, and the decks show", async () => {
  renderApp({
    ...RUI,
    "POST /api/matches": {
      status: 201,
      body: {
        id: "a-match",
        version: 1,
        view: view(),
        rounds: [],
        moves: [],
      } satisfies Played,
    },
    "DELETE /api/session": { status: 204, body: null },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await screen.findByRole("button", { name: "Keep this hand" });
  // No list during a match: the button would leave it.
  expect(
    screen.queryByRole("button", { name: "My matches" }),
  ).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Log out" }));

  expect(
    await screen.findByRole("heading", { name: "Choose your deck" }),
  ).toHaveFocus();
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
});

/** Return the number of times the list and the stats were asked for. */
function asked(requests: string[]) {
  return [
    requests.filter((to) => to === "GET /api/matches").length,
    requests.filter((to) => to === "GET /api/stats").length,
  ];
}

const NO_MATCHES = {
  ...RUI,
  "GET /api/stats": stats([]),
  "GET /api/matches": page([]),
};

/** Open the list, wait for it, and go back to the decks. */
async function openAndBack() {
  await openMatches();
  await screen.findByText("No match yet: choose a deck to play one.");
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
}

test("the list comes from the cache, until a match starts", async () => {
  const requests = renderApp({
    ...NO_MATCHES,
    // A match over at once, so the page can leave it without a move.
    "POST /api/matches": {
      status: 201,
      body: {
        id: "a-match",
        version: 1,
        view: view({ match_over: true, winner: 1, legal_actions: [] }),
        rounds: [],
        moves: [],
      } satisfies Played,
    },
  });
  await openAndBack();
  await openAndBack();
  expect(asked(requests)).toEqual([1, 1]);

  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  fireEvent.click(await screen.findByRole("button", { name: "Play again" }));
  await openAndBack();

  expect(asked(requests)).toEqual([2, 2]);
});

test("once a match ends, the list and the stats are asked for again", async () => {
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  const requests = renderApp({
    ...NO_MATCHES,
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 200,
      body: {
        id: "a-match",
        version: 7,
        view: view({ legal_actions: [{ type: "pass" }] }),
        rounds: [],
      } satisfies Match,
    },
    "POST /api/matches/a-match/actions": {
      status: 200,
      body: {
        id: "a-match",
        version: 8,
        view: over,
        rounds: [],
        moves: [{ events: [], view: over }],
      } satisfies Played,
    },
  });
  await openMatches();
  // Coming back to a match doesn't change the list.
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
  fireEvent.click(await screen.findByRole("button", { name: "Pass" }));
  fireEvent.click(await screen.findByRole("button", { name: "Play again" }));
  await openMatches();
  await screen.findByRole("button", { name: "Resume" });

  expect(asked(requests)).toEqual([2, 2]);
});
