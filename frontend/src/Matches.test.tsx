import { focusManager, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { expect, onTestFinished, test } from "vitest";
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

/**
 * An answer of the fake API: a status and a JSON body, or one that comes when
 * the test says so.
 */
type Answer = { status: number; body: unknown } | Promise<Response>;

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
    if (answer instanceof Promise) {
      return answer.then((response) => response.clone());
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
    deck_name: null,
    ai_deck: "robots",
    level: "easy",
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

/**
 * Return an answer that comes only when the test calls `answer`, so the test
 * can look at the page while the request waits.
 */
function later() {
  let answer: (response: Response) => void = () => {};
  const response = new Promise<Response>((resolve) => {
    answer = resolve;
  });
  return { response, answer };
}

/** Wait until a request the page may have just sent has been answered. */
function settle() {
  return new Promise((resolve) => setTimeout(resolve));
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

test("a match played with a deck the player built shows its name and faction", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary({ deck_name: "Mine" })]),
  });
  await openMatches();

  expect(await screen.findByRole("listitem")).toHaveTextContent(
    "Mine (Humans) against Robots",
  );
});

test("each match says the level of the AI it was played against", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary({ level: "hard" })]),
  });
  await openMatches();

  expect(await screen.findByRole("listitem")).toHaveTextContent(
    "Humans against Robots (Hard)",
  );
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
    "GET /api/matches": page(
      [summary({ id: "newest" }), summary({ id: "new" })],
      true,
    ),
    "GET /api/matches?before=new": page(
      [summary({ id: "old" }), summary({ id: "older" })],
      true,
    ),
    "GET /api/matches?before=older": page([WON]),
  });
  await openMatches();
  expect(await screen.findAllByRole("listitem")).toHaveLength(2);

  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });
  // The focus goes to the first match of the new page.
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")[2]).toHaveFocus();
  });
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });
  // Show more is gone, and the focus didn't go with it.
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")[4]).toHaveFocus();
  });

  // The last page says there are no more.
  expect(
    screen.queryByRole("button", { name: "Show more" }),
  ).not.toBeInTheDocument();
  expect(requests.filter((to) => to.startsWith("GET /api/matches"))).toEqual([
    "GET /api/matches",
    "GET /api/matches?before=new",
    "GET /api/matches?before=older",
  ]);
});

test("while the next page is asked for, no second one is", async () => {
  const next = later();
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()], true),
    "GET /api/matches?before=a-match": next.response,
  });
  await openMatches();
  const more = await screen.findByRole("button", { name: "Show more" });

  fireEvent.click(more);
  await waitFor(() => {
    expect(more).toBeDisabled();
  });
  next.answer(Response.json({ matches: [WON], more: false }));
  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});

test("a next page that didn't come says why, and Show more asks again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()], true),
  };
  renderApp(answers);
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Show more" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
  // The first page is still there: no need to ask for it again.
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(
    screen.queryByRole("button", { name: "Try again" }),
  ).not.toBeInTheDocument();
  // Disabled meanwhile, Show more gets the focus back, to ask again.
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Show more" })).toHaveFocus();
  });
  answers["GET /api/matches?before=a-match"] = page([WON]);
  fireEvent.click(screen.getByRole("button", { name: "Show more" }));

  await waitFor(() => {
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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

test("while a match is asked for, to play on, no other one can be", async () => {
  const match = later();
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary(), summary({ id: "another" })]),
    "GET /api/matches/a-match": match.response,
  });
  await openMatches();
  const [first, second] = await screen.findAllByRole("button", {
    name: "Resume",
  });

  fireEvent.click(first as HTMLElement);
  await waitFor(() => {
    expect(second).toBeDisabled();
  });
  match.answer(
    Response.json({
      id: "a-match",
      version: 1,
      view: view(),
      rounds: [],
    } satisfies Match),
  );
  expect(
    await screen.findByRole("button", { name: "Keep this hand" }),
  ).toBeInTheDocument();
});

test("two clicks in the same instant ask for one match only", async () => {
  const requests = renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary(), summary({ id: "another" })]),
  });
  await openMatches();
  const [first, second] = await screen.findAllByRole("button", {
    name: "Resume",
  });

  // Both before the page shows the buttons disabled.
  fireEvent.click(first as HTMLElement);
  fireEvent.click(second as HTMLElement);
  await screen.findByRole("alert");

  expect(requests.filter((to) => to.startsWith("GET /api/matches/"))).toEqual([
    "GET /api/matches/a-match",
  ]);
});

test("a match the player comes back to is asked for again, as it may have been played elsewhere", async () => {
  const requests = renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 200,
      body: {
        id: "a-match",
        version: 1,
        view: view(),
        rounds: [],
      } satisfies Match,
    },
    "DELETE /api/session": { status: 204, body: null },
    "POST /api/session": { status: 200, body: { username: "rui" } },
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
  await screen.findByRole("button", { name: "Keep this hand" });
  // The page keeps the match it had, and the player comes back to it.
  fireEvent.click(screen.getByRole("button", { name: "Log out" }));
  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "rui" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "dragon123" },
  });
  fireEvent.submit(
    screen.getByRole("dialog").querySelector("form") as HTMLFormElement,
  );
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
  await screen.findByRole("button", { name: "Keep this hand" });

  expect(
    requests.filter((to) => to === "GET /api/matches/a-match"),
  ).toHaveLength(2);
  // Logging out forgot the list: it is asked for again too.
  expect(requests.filter((to) => to === "GET /api/matches")).toHaveLength(2);
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

  // The heading can show before the effect that puts the focus on it has run:
  // the page leaves the match in an effect of its own, once it knows who is
  // logged in, and not straight after a click.
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toHaveFocus();
  });
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

const GUEST_ANSWER: Answer = {
  status: 401,
  body: { code: "not_logged_in", message: "The player isn't logged in." },
};

/** Return the answer of the API to a new match, at `view`. */
function newMatch(match = view()): Answer {
  return {
    status: 201,
    body: {
      id: "a-match",
      version: 1,
      view: match,
      rounds: [],
      moves: [],
    } satisfies Played,
  };
}

test("a request turned down as not logged in shows the player as a guest", async () => {
  // The player logged out in another tab: this one still thinks not.
  renderApp({
    ...RUI,
    "GET /api/stats": GUEST_ANSWER,
    "GET /api/matches": GUEST_ANSWER,
  });
  await openMatches();

  expect(
    await screen.findByRole("button", { name: "Log in" }),
  ).toBeInTheDocument();
  // The heading can show before the effect that puts the focus on it has run:
  // the page leaves the match in an effect of its own, once it knows who is
  // logged in, and not straight after a click.
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toHaveFocus();
  });
  expect(screen.queryByText(/Logged in as/)).not.toBeInTheDocument();
});

test("coming back to the tab asks again who is logged in", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "POST /api/matches": newMatch(),
  };
  renderApp(answers);
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await screen.findByRole("button", { name: "Keep this hand" });

  // Logged out in another tab, while this one was hidden.
  answers["GET /api/session"] = GUEST_ANSWER;
  act(() => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
  });
  onTestFinished(() => {
    focusManager.setFocused(undefined);
  });

  // The match was the account's: the page leaves it.
  // The heading can show before the effect that puts the focus on it has run:
  // the page leaves the match in an effect of its own, once it knows who is
  // logged in, and not straight after a click.
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toHaveFocus();
  });
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
});

test("another account logged in elsewhere gets its own list", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
  };
  const requests = renderApp(answers);
  await openMatches();
  await screen.findByRole("listitem");

  answers["GET /api/session"] = { status: 200, body: { username: "ana" } };
  answers["GET /api/matches"] = page([]);
  act(() => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
  });
  onTestFinished(() => {
    focusManager.setFocused(undefined);
  });
  expect(await screen.findByText("ana")).toBeInTheDocument();
  await openMatches();

  expect(
    await screen.findByText("No match yet: choose a deck to play one."),
  ).toBeInTheDocument();
  expect(requests.filter((to) => to === "GET /api/matches")).toHaveLength(2);
});

test("a guest's match goes on when they log in and out", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/session": GUEST_ANSWER,
    "POST /api/matches": newMatch(),
    "POST /api/session": { status: 200, body: { username: "rui" } },
    "DELETE /api/session": { status: 204, body: null },
  };
  renderApp(answers);
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await screen.findByRole("button", { name: "Keep this hand" });

  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "rui" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "dragon123" },
  });
  fireEvent.submit(
    screen.getByRole("dialog").querySelector("form") as HTMLFormElement,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
  await screen.findByRole("button", { name: "Log in" });

  expect(screen.getByRole("button", { name: "Keep this hand" })).toBeEnabled();
});

test("no logging out while a match starts", async () => {
  const match = later();
  renderApp({ ...RUI, "POST /api/matches": match.response });
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

  // Its answer would be a match of the account, for a guest.
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Log out" })).toBeDisabled();
  });
  match.answer(
    Response.json((newMatch() as { body: unknown }).body, { status: 201 }),
  );
  await screen.findByRole("button", { name: "Keep this hand" });
  expect(screen.getByRole("button", { name: "Log out" })).toBeEnabled();
});

test("going back while a match is asked for, to play on, doesn't open it", async () => {
  const match = later();
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": match.response,
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
  fireEvent.click(screen.getByRole("button", { name: "Back" }));

  match.answer(
    Response.json({
      id: "a-match",
      version: 1,
      view: view(),
      rounds: [],
    } satisfies Match),
  );
  await settle();

  expect(
    screen.getByRole("heading", { name: "Choose your deck" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Keep this hand" }),
  ).not.toBeInTheDocument();
});

test("the end of a match puts the top of the page out of reach too", async () => {
  renderApp({
    ...RUI,
    "POST /api/matches": newMatch(
      view({ match_over: true, winner: 0, legal_actions: [] }),
    ),
  });
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await screen.findByRole("button", { name: "Play again" });

  // The dialog is modal: Tab must not reach "Log out" behind it.
  expect(
    screen
      .getByRole("button", { name: "Log out", hidden: true })
      .closest("[inert]"),
  ).not.toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "Play again" }));
  expect(
    screen.getByRole("button", { name: "Log out" }).closest("[inert]"),
  ).toBeNull();
});

test("stats that didn't come can be asked for again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/matches": page([WON]),
  };
  renderApp(answers);
  await openMatches();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );

  answers["GET /api/stats"] = stats([
    { deck: "humans", won: 1, lost: 0, drawn: 0 },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("table", { name: "Matches won, lost and drawn" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a match the player comes back to says how its last round went", async () => {
  renderApp({
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 200,
      body: {
        id: "a-match",
        version: 9,
        view: view({ round: 2, legal_actions: [{ type: "pass" }] }),
        rounds: [{ type: "round_ended", scores: [5, 3], winner: 0 }],
      } satisfies Match,
    },
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));

  expect(
    await screen.findByText("Round 1: you won, 5 to 3."),
  ).toBeInTheDocument();
});

test("opening the list while a match starts doesn't open the match over it", async () => {
  const match = later();
  renderApp({
    ...NO_MATCHES,
    "POST /api/matches": match.response,
  });
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await openMatches();
  await screen.findByText("No match yet: choose a deck to play one.");

  match.answer(
    Response.json((newMatch() as { body: unknown }).body, { status: 201 }),
  );
  await settle();

  expect(screen.getByRole("heading", { name: "My matches" })).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Keep this hand" }),
  ).not.toBeInTheDocument();
});

test("a match gone because the player logged out in another tab is left, saying why", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "POST /api/matches": newMatch(),
  };
  const requests = renderApp(answers);
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  const keep = await screen.findByRole("button", { name: "Keep this hand" });

  // The API gives a guest a 404 for the account's match.
  answers["GET /api/session"] = GUEST_ANSWER;
  answers["POST /api/matches/a-match/actions"] = {
    status: 404,
    body: { code: "match_not_found", message: "The match doesn't exist." },
  };
  fireEvent.click(keep, { detail: 1 });

  expect(
    await screen.findByText(
      "You were logged out, so the match was left: log in to play on.",
    ),
  ).toBeInTheDocument();
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toHaveFocus();
  });
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  expect(requests.filter((to) => to === "GET /api/session")).toHaveLength(2);

  // Gone once another match starts, and so after it too.
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  answers["POST /api/matches/a-match/actions"] = {
    status: 200,
    body: {
      id: "a-match",
      version: 2,
      view: over,
      rounds: [],
      moves: [{ events: [], view: over }],
    } satisfies Played,
  };
  fireEvent.click(screen.getByRole("button", { name: "Humans" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Keep this hand" }),
    { detail: 1 },
  );
  fireEvent.click(await screen.findByRole("button", { name: "Play again" }), {
    detail: 1,
  });
  await screen.findByRole("heading", { name: "Choose your deck" });
  expect(screen.queryByText(/You were logged out/)).not.toBeInTheDocument();
});

test("a match the server doesn't know says so, with the focus", async () => {
  renderApp({
    ...RUI,
    "POST /api/matches": newMatch(),
    "POST /api/matches/a-match/actions": {
      status: 404,
      body: { code: "match_not_found", message: "The match doesn't exist." },
    },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Keep this hand" }),
    { detail: 1 },
  );

  // Still logged in: the page stays, and says the match is gone.
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Match not found" }),
    ).toHaveFocus();
  });
  await settle();
  expect(screen.getByText(/Logged in as/)).toBeInTheDocument();
  expect(screen.queryByText(/You were logged out/)).not.toBeInTheDocument();
});

test("who is logged in stays when asking again doesn't work", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/stats": stats([]),
    "GET /api/matches": page([summary()]),
  };
  const requests = renderApp(answers);
  await openMatches();
  await screen.findByRole("listitem");
  onTestFinished(() => {
    focusManager.setFocused(undefined);
  });
  const backToTab = () => {
    act(() => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
  };

  // No answer: the page still shows rui, and their list. (Nothing on the
  // page says the request failed: the test waits for it to be sent, then
  // long enough for its answer to come.)
  delete answers["GET /api/session"];
  backToTab();
  await waitFor(() => {
    expect(requests.filter((to) => to === "GET /api/session")).toHaveLength(2);
  });
  await act(() => new Promise((resolve) => setTimeout(resolve, 100)));
  expect(screen.getByText("rui")).toBeInTheDocument();
  expect(screen.getByRole("listitem")).toBeInTheDocument();

  // Then ana: the page knows it changed, and forgets rui's list.
  answers["GET /api/session"] = { status: 200, body: { username: "ana" } };
  answers["GET /api/matches"] = page([]);
  backToTab();
  expect(await screen.findByText("ana")).toBeInTheDocument();
  await openMatches();
  expect(
    await screen.findByText("No match yet: choose a deck to play one."),
  ).toBeInTheDocument();
  expect(requests.filter((to) => to === "GET /api/matches")).toHaveLength(2);
});

test("resuming a match that ended in another tab asks for the list again", async () => {
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  const requests = renderApp({
    ...NO_MATCHES,
    // The list says it isn't over: it came before it ended.
    "GET /api/matches": page([summary()]),
    "GET /api/matches/a-match": {
      status: 200,
      body: {
        id: "a-match",
        version: 9,
        view: over,
        rounds: [],
      } satisfies Match,
    },
  });
  await openMatches();
  fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
  fireEvent.click(await screen.findByRole("button", { name: "Play again" }), {
    detail: 1,
  });
  await openMatches();
  await screen.findByRole("listitem");

  expect(asked(requests)).toEqual([2, 2]);
});
