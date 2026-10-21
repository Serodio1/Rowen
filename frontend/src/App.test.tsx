import { onlineManager, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, onTestFinished, test, vi } from "vitest";
import { App } from "./App.tsx";
import {
  createApi,
  type Card,
  type Event,
  type Match,
  type Played,
  type View,
} from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";
import { TIMES } from "./stage.ts";
import { DECKS, HOARFROST, SOLDIER, side, view } from "./test-data.ts";

/**
 * An answer of the fake API: a status and a JSON body, any `Response`, or one
 * that comes when the test says so.
 */
type Answer = { status: number; body: unknown } | Response | Promise<Response>;

/**
 * Return a client whose `fetch` answers each request with the answer for its
 * method and path, such as `"GET /api/decks"`, and the requests it got. With
 * no answer for a request, the request fails, as when there is no network.
 */
function fakeApi(answers: Record<string, Answer>) {
  const requests: Request[] = [];
  const api = createApi((request) => {
    requests.push(request);
    const answer =
      answers[`${request.method} ${new URL(request.url).pathname}`];
    if (answer === undefined) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (answer instanceof Response || answer instanceof Promise) {
      // A copy for each request, as a server sends: a body can be read only
      // once, so a second request would fail to read it.
      return Promise.resolve(answer).then((response) => response.clone());
    }
    return Promise.resolve(
      Response.json(answer.body, { status: answer.status }),
    );
  });
  return { api, requests };
}

/** Return the requests for one method and path, such as `"GET /api/decks"`. */
function sent(requests: Request[], to: string) {
  return requests.filter(
    (request) => `${request.method} ${new URL(request.url).pathname}` === to,
  );
}

/** Show the page, as `main.tsx` does, with an empty cache of its own. */
function renderApp(api: ReturnType<typeof fakeApi>["api"]) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <App api={api} />
    </QueryClientProvider>,
  );
}

/** Wait until a request the page may have just sent has gone out. */
function settle() {
  return new Promise((resolve) => setTimeout(resolve));
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

const THE_DECKS = { "GET /api/decks": { status: 200, body: { decks: DECKS } } };

const A_MATCH = {
  ...THE_DECKS,
  "POST /api/matches": {
    status: 201,
    body: {
      id: "a-match",
      version: 1,
      view: view(),
      events: [],
    } satisfies Played,
  },
};

// Where the moves of the match "a-match" go.
const PLAY = "POST /api/matches/a-match/actions";

// The view once round 1 has begun.
const ROUND_1 = view({
  legal_actions: [
    { type: "play_unit", card: "soldier", row: "melee" },
    { type: "play_unit", card: "soldier", row: "ranged" },
    { type: "pass" },
  ],
});

/**
 * Return the API's answer to a move: the match after it, at `version`, and
 * its events.
 */
function played(after: View, events: Event[] = [], version = 2) {
  return {
    status: 200,
    body: { id: "a-match", version, view: after, events } satisfies Played,
  };
}

/** Return the match "a-match" as the API sends it when asked for it. */
function aMatch(view: View, version: number): Match {
  return { id: "a-match", version, view };
}

/** Return an answer of the API that turns a request down. */
function turnedDown(status: number, code: string): Answer {
  return { status, body: { code, message: `The API says ${code}.` } };
}

/**
 * Return the buttons of the cards the player may choose, in the hand, then
 * of the other moves (Pass, Keep this hand).
 */
function choiceButtons() {
  return [
    ...within(screen.getByRole("list", { name: "Your hand" })).queryAllByRole(
      "button",
    ),
    ...within(screen.getByRole("group", { name: "Moves" })).queryAllByRole(
      "button",
    ),
  ];
}

/** Return each card in the player's hand, by its accessible name, which screen readers read. */
function hand() {
  return within(screen.getByRole("list", { name: "Your hand" }))
    .getAllByRole("img")
    .map((card) => card.getAttribute("aria-label"));
}

/** Return the name of each card the player may choose, then of the other moves. */
function choices() {
  return choiceButtons().map(
    (button) => button.getAttribute("aria-label") ?? button.textContent,
  );
}

/**
 * Swap the first Soldier in the hand: choose it, then click it again, with
 * clicks of a count of 1.
 */
function swapSoldier() {
  const [soldier] = screen.getAllByRole("button", { name: /^Soldier/ });
  fireEvent.click(soldier as HTMLElement, { detail: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Swap Soldier" }), {
    detail: 1,
  });
}

/** Start a match with the humans and wait until it shows. */
async function startMatch() {
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  await screen.findByRole("heading", { name: "Round 1" });
}

test("the page shows the name of the game as its main heading", () => {
  renderApp(fakeApi(THE_DECKS).api);

  expect(
    screen.getByRole("heading", { level: 1, name: "Rowen" }),
  ).toBeInTheDocument();
});

test("the player can choose any of the API's decks", async () => {
  const { api, requests } = fakeApi(THE_DECKS);
  renderApp(api);

  expect(screen.getByText("Loading the decks…")).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Humans" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Robots" })).toBeInTheDocument();
  expect(screen.queryByText("Loading the decks…")).not.toBeInTheDocument();
  // Once, even though StrictMode shows the page twice, as in development.
  expect(sent(requests, "GET /api/decks")).toHaveLength(1);
});

test("choosing a deck starts a match with it, and shows the round, the hand and the moves", async () => {
  const { api, requests } = fakeApi(A_MATCH);
  renderApp(api);

  fireEvent.click(await screen.findByRole("button", { name: "Robots" }));

  expect(
    await screen.findByRole("heading", { name: "Round 1" }),
  ).toBeInTheDocument();
  const [started] = sent(requests, "POST /api/matches");
  expect(await started?.json()).toEqual({ deck: "robots" });
  expect(hand()).toEqual([
    "Soldier (4 melee/ranged, agile)",
    "Soldier (4 melee/ranged, agile)",
    "Hoarfrost (weather on melee)",
  ]);
  // Each card may be swapped: the cards are buttons.
  expect(choices()).toEqual([
    "Soldier (4 melee/ranged, agile)",
    "Soldier (4 melee/ranged, agile)",
    "Hoarfrost (weather on melee)",
    "Keep this hand",
  ]);
  // The view came with the match: the page didn't ask for it.
  expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(0);
});

test("no deck can be chosen while a match starts", async () => {
  const answer = later();
  const { api, requests } = fakeApi({
    ...THE_DECKS,
    "POST /api/matches": answer.response,
  });
  renderApp(api);

  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Humans" })).toBeDisabled();
  });
  expect(screen.getByRole("button", { name: "Robots" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Robots" }));
  await settle();
  expect(sent(requests, "POST /api/matches")).toHaveLength(1);

  answer.answer(Response.json(A_MATCH["POST /api/matches"].body));
  await screen.findByRole("heading", { name: "Round 1" });
});

test("when the API turns a match down, the page shows why, and the player can try again", async () => {
  const answers: Record<string, Answer> = {
    ...THE_DECKS,
    "POST /api/matches": turnedDown(422, "unknown_deck"),
  };
  renderApp(fakeApi(answers).api);

  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The API says unknown_deck.",
  );
  expect(screen.getByRole("button", { name: "Humans" })).toBeEnabled();

  answers["POST /api/matches"] = A_MATCH["POST /api/matches"];
  fireEvent.click(screen.getByRole("button", { name: "Humans" }));

  await screen.findByRole("heading", { name: "Round 1" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test.each<[string, Answer | undefined]>([
  ["no answer", undefined],
  ["an answer without a body", new Response(null, { status: 502 })],
  [
    "a page that isn't from the API",
    new Response("<h1>Bad Gateway</h1>", {
      status: 502,
      headers: { "Content-Type": "text/html" },
    }),
  ],
])(
  "when a match can't start, with %s, the page says it can't reach the server",
  async (_, answer) => {
    const answers: Record<string, Answer> = { ...THE_DECKS };
    if (answer !== undefined) {
      answers["POST /api/matches"] = answer;
    }
    renderApp(fakeApi(answers).api);

    fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the server.",
    );
  },
);

test("when the decks can't be loaded, the page says it can't reach the server, and the player can try again", async () => {
  const answers: Record<string, Answer> = {};
  const { api, requests } = fakeApi(answers);
  renderApp(api);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
  expect(screen.queryByText("Loading the decks…")).not.toBeInTheDocument();
  // At once: the page doesn't ask again on its own.
  expect(sent(requests, "GET /api/decks")).toHaveLength(1);

  const answer = later();
  answers["GET /api/decks"] = answer.response;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(await screen.findByText("Loading the decks…")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Try again" }),
  ).not.toBeInTheDocument();

  answer.answer(Response.json(THE_DECKS["GET /api/decks"].body));
  expect(
    await screen.findByRole("button", { name: "Humans" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Loading the decks…")).not.toBeInTheDocument();
});

test("clicking a move plays it, and the page shows the view of the answer", async () => {
  // Another round and another hand than the match started with, so the test
  // sees that the page shows the answer's.
  const after = view({
    round: 2,
    hand: [HOARFROST],
    legal_actions: [{ type: "pass" }],
  });
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(after) });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });

  expect(
    await screen.findByRole("heading", { name: "Round 2" }),
  ).toBeInTheDocument();
  const [move] = sent(requests, PLAY);
  // The action goes back as the view listed it, with the match's version.
  expect(await move?.json()).toEqual({
    version: 1,
    action: { type: "end_redraw" },
  });
  expect(hand()).toEqual(["Hoarfrost (weather on melee)"]);
  expect(choices()).toEqual(["Pass"]);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a move can be made with the keyboard, which gives a click no count", async () => {
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 0,
  });

  await screen.findByRole("button", { name: "Pass" });
  expect(sent(requests, PLAY)).toHaveLength(1);
});

test("each move sends the version of the match its view came with", async () => {
  // The match starts at version 1, and the first move takes it to 2.
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  fireEvent.click(await screen.findByRole("button", { name: "Pass" }));

  await waitFor(() => {
    expect(sent(requests, PLAY)).toHaveLength(2);
  });
  const [first, second] = sent(requests, PLAY);
  expect(await first?.json()).toEqual({
    version: 1,
    action: { type: "end_redraw" },
  });
  expect(await second?.json()).toEqual({
    version: 2,
    action: { type: "pass" },
  });
});

test("after asking for the match again, a move sends the version that came with it", async () => {
  // The first move was chosen from an old view. The match the page then gets
  // is at version 5.
  const { api, requests } = fakeApi({
    ...A_MATCH,
    [PLAY]: turnedDown(409, "match_changed"),
    "GET /api/matches/a-match": { status: 200, body: aMatch(ROUND_1, 5) },
  });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  const pass = await screen.findByRole("button", { name: "Pass" });
  await waitFor(() => {
    expect(pass).toBeEnabled();
  });
  fireEvent.click(pass);

  await waitFor(() => {
    expect(sent(requests, PLAY)).toHaveLength(2);
  });
  const [, second] = sent(requests, PLAY);
  expect(await second?.json()).toEqual({
    version: 5,
    action: { type: "pass" },
  });
});

test("no move can be made while one is on its way", async () => {
  const answer = later();
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: answer.response });
  renderApp(api);
  await startMatch();

  swapSoldier();

  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Keep this hand" }),
    ).toBeDisabled();
  });
  for (const button of choiceButtons()) {
    expect(button).toBeDisabled();
  }
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });
  await settle();
  expect(sent(requests, PLAY)).toHaveLength(1);

  answer.answer(Response.json(played(ROUND_1).body));
  await screen.findByRole("button", { name: "Pass" });
  expect(screen.getByRole("button", { name: "Pass" })).toBeEnabled();
});

test.each([
  [2, "the second click of a double click"],
  [3, "the third click of a triple click"],
])("a click with a count of %i, %s, isn't a move", async (count) => {
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  // The answer comes before the next click, so it lands on a move of the
  // next view.
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });
  fireEvent.click(await screen.findByRole("button", { name: "Pass" }), {
    detail: count,
  });

  await settle();
  expect(sent(requests, PLAY)).toHaveLength(1);
  expect(choices()).toContain("Pass");
});

test("two clicks in the same instant make one move", async () => {
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  // No person can, but a script can click twice before the page shows the
  // moves disabled.
  swapSoldier();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });

  await screen.findByRole("button", { name: "Pass" });
  await settle();
  const [move, ...others] = sent(requests, PLAY);
  expect(others).toHaveLength(0);
  expect(await move?.json()).toEqual({
    version: 1,
    action: { type: "redraw", card: "soldier" },
  });
});

test.each<[number | null, string]>([
  [0, "You won the match!"],
  [1, "The AI won the match."],
  [null, "The match is a draw."],
])(
  "when the match is over (winner %s), the page says who won, and the player can play again",
  async (winner, result) => {
    const over = view({ match_over: true, winner, legal_actions: [] });
    const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(over) });
    renderApp(api);
    await startMatch();

    fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

    expect(await screen.findByText(result)).toBeInTheDocument();
    // The board stays, to show how the match ended.
    expect(screen.getByRole("region", { name: "Board" })).toBeInTheDocument();
    // No card or move can be chosen.
    expect(
      screen.queryByRole("group", { name: "Moves" }),
    ).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Your hand" })).queryAllByRole(
        "button",
      ),
    ).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Play again" }));

    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toBeInTheDocument();
    // The decks are still in the cache: the page doesn't ask for them again.
    expect(screen.getByRole("button", { name: "Humans" })).toBeEnabled();
    expect(sent(requests, "GET /api/decks")).toHaveLength(1);
  },
);

const LOST = turnedDown(404, "match_not_found");

test.each<[string, Record<string, Answer>, number]>([
  ["a move", { [PLAY]: LOST }, 0],
  [
    "asking for the match after a 409",
    {
      [PLAY]: turnedDown(409, "match_changed"),
      "GET /api/matches/a-match": LOST,
    },
    1,
  ],
  [
    "asking for the match after a move got no answer",
    { "GET /api/matches/a-match": LOST },
    1,
  ],
])(
  "when the server lost the match, found by %s, the page says so, and the player can start a new one",
  async (_, answers, asked) => {
    const { api, requests } = fakeApi({ ...A_MATCH, ...answers });
    renderApp(api);
    await startMatch();

    fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

    // Wait for the end: the page may say something else on the way.
    expect(
      await screen.findByRole("heading", { name: "Match not found" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This match is no longer on the server.",
    );
    expect(
      screen.queryByRole("heading", { name: "Round 1" }),
    ).not.toBeInTheDocument();
    expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(asked);

    fireEvent.click(screen.getByRole("button", { name: "Start a new match" }));

    expect(
      screen.getByRole("heading", { name: "Choose your deck" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  },
);

test.each(["illegal_action", "match_changed"])(
  "when the API turns a move down with %s, the page asks for the match again and shows it",
  async (code) => {
    const answer = later();
    const { api, requests } = fakeApi({
      ...A_MATCH,
      [PLAY]: turnedDown(409, code),
      "GET /api/matches/a-match": answer.response,
    });
    renderApp(api);
    await startMatch();

    fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The match changed. This is where it is now.",
    );
    // No move until the page knows where the match is.
    for (const button of choiceButtons()) {
      expect(button).toBeDisabled();
    }
    expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(1);

    answer.answer(Response.json(aMatch(ROUND_1, 3)));

    expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
    // The cards of the new view: the Soldiers may be played, not Hoarfrost.
    expect(choices()).toEqual([
      "Soldier (4 melee/ranged, agile)",
      "Soldier (4 melee/ranged, agile)",
      "Pass",
    ]);
  },
);

test("when the match can't be asked for again, no move can be made until it can", async () => {
  const answers: Record<string, Answer> = {
    ...A_MATCH,
    [PLAY]: turnedDown(409, "match_changed"),
  };
  const { api, requests } = fakeApi(answers);
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  expect(
    await screen.findByRole("button", { name: "Try again" }),
  ).toBeEnabled();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
  // The moves on the page may be out of date.
  for (const button of choiceButtons()) {
    expect(button).toBeDisabled();
  }

  // Trying again asks for the match, not for the move.
  const answer = later();
  answers["GET /api/matches/a-match"] = answer.response;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Try again" })).toBeDisabled();
  });
  expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(2);
  expect(sent(requests, PLAY)).toHaveLength(1);

  answer.answer(Response.json(aMatch(ROUND_1, 3)));

  expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
  expect(
    screen.queryByRole("button", { name: "Try again" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "The match changed. This is where it is now.",
  );
});

test.each<[string, Answer | undefined, string]>([
  ["no answer", undefined, "Could not reach the server."],
  [
    "an answer without a body",
    new Response(null, { status: 502 }),
    "Could not reach the server.",
  ],
  [
    "a server error",
    turnedDown(500, "server_error"),
    "The API says server_error.",
  ],
  [
    "an answer that turns it down",
    turnedDown(422, "invalid_request"),
    "The API says invalid_request.",
  ],
])(
  "when a move gets %s, the page asks for the match, as the move may have been played",
  async (_, failure, message) => {
    const answer = later();
    const answers: Record<string, Answer> = {
      ...A_MATCH,
      "GET /api/matches/a-match": answer.response,
    };
    if (failure !== undefined) {
      answers[PLAY] = failure;
    }
    const { api, requests } = fakeApi(answers);
    renderApp(api);
    await startMatch();

    fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      `${message} This is where the match is now.`,
    );
    // No move until the page knows where the match is: the moves on the page
    // may be out of date.
    for (const button of choiceButtons()) {
      expect(button).toBeDisabled();
    }
    expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(1);

    // The move was played: the match is in round 1.
    answer.answer(Response.json(aMatch(ROUND_1, 3)));

    expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      `${message} This is where the match is now.`,
    );
    expect(sent(requests, PLAY)).toHaveLength(1);
  },
);

// Whether the browser is online is shared by every test: put it back.
afterEach(() => {
  onlineManager.setOnline(true);
});

test("when the browser says it is offline, the page still sends its requests", async () => {
  onlineManager.setOnline(false);
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);

  // The decks come, the match starts, and a move is played.
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
});

/** Return what happened, as the page shows it: the sentences of each move. */
function log() {
  const entries = within(
    screen.getByRole("log", { name: "What happened" }),
  ).queryAllByRole("listitem");
  return entries.map((entry) =>
    within(entry)
      .getAllByText(/./)
      .map((sentence) => sentence.textContent),
  );
}

test("when the AI starts the match, the page says what it did", async () => {
  const { api } = fakeApi({
    ...THE_DECKS,
    "POST /api/matches": {
      status: 201,
      body: {
        id: "a-match",
        version: 1,
        view: view(),
        events: [
          { type: "opponent_redrew", player: 1 },
          { type: "redraw_ended", player: 1 },
        ],
      } satisfies Played,
    },
  });
  renderApp(api);
  await startMatch();

  expect(log()).toEqual([
    ["The AI swapped a card.", "The AI finished swapping."],
  ]);
});

test("before anything happened, the page says so", async () => {
  renderApp(fakeApi(A_MATCH).api);
  await startMatch();

  const what = screen.getByRole("log", { name: "What happened" });
  expect(log()).toEqual([]);
  expect(within(what).getByText("Nothing yet.")).toBeInTheDocument();
  // No round is over: the place kept for how it went, under the round, is
  // empty.
  expect(
    screen.getByRole("heading", { name: "Round 1" }).nextElementSibling,
  ).toBeEmptyDOMElement();
});

test("after each move, the page says what happened, the latest move first", async () => {
  const answers: Record<string, Answer> = {
    ...A_MATCH,
    [PLAY]: played(ROUND_1, [
      { type: "redraw_ended", player: 0 },
      {
        type: "unit_played",
        player: 1,
        card: "soldier",
        row: "melee",
        side: 1,
      },
    ]),
  };
  const { api } = fakeApi(answers);
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByRole("button", { name: "Pass" });
  answers[PLAY] = played(ROUND_1, [
    { type: "unit_played", player: 0, card: "soldier", row: "ranged", side: 0 },
    { type: "player_passed", player: 1 },
  ]);
  // Choose a Soldier, then its row.
  const [soldier] = screen.getAllByRole("button", { name: /^Soldier/ });
  fireEvent.click(soldier as HTMLElement);
  fireEvent.click(
    screen.getByRole("button", { name: "Play Soldier in the melee row" }),
  );

  await waitFor(() => {
    expect(log()).toHaveLength(2);
  });
  expect(log()).toEqual([
    ["You played Soldier in the ranged row.", "The AI passed."],
    ["You finished swapping.", "The AI played Soldier in the melee row."],
  ]);
});

test("a card that left the view is still named, as the page saw it before", async () => {
  // The AI's Scarecrow takes back its Sniper, which goes to its hand: the
  // view after the move doesn't show it, but the view before did.
  const sniper = {
    ...SOLDIER,
    id: "sniper",
    name: "Sniper",
    rows: ["ranged"],
  } satisfies Card;
  const scarecrow = {
    type: "special",
    id: "scarecrow",
    name: "Scarecrow",
    kind: "scarecrow",
    weather_row: null,
    description: [],
  } satisfies Card;
  const ranged = side().rows.ranged;
  const aiRows = (row: typeof ranged) =>
    side({ rows: { ...side().rows, ranged: row } });
  const before = view({
    players: [
      side(),
      aiRows({ ...ranged, units: [{ card: sniper, strength: 6 }], score: 6 }),
    ],
  });
  const after = view({
    ...ROUND_1,
    players: [side(), aiRows({ ...ranged, scarecrows: [scarecrow] })],
  });
  const { api } = fakeApi({
    ...THE_DECKS,
    "POST /api/matches": {
      status: 201,
      body: {
        id: "a-match",
        version: 1,
        view: before,
        events: [],
      } satisfies Played,
    },
    [PLAY]: played(after, [
      {
        type: "scarecrow_played",
        player: 1,
        card: "scarecrow",
        row: "ranged",
        unit: "sniper",
      },
    ]),
  });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  await waitFor(() => {
    expect(log()).toEqual([
      ["The AI played Scarecrow in the ranged row and took back Sniper."],
    ]);
  });
});

test("when a round ends, the page says how it went over the board, until the next move", async () => {
  const answers: Record<string, Answer> = {
    ...A_MATCH,
    [PLAY]: played(view({ ...ROUND_1, round: 2 }), [
      { type: "player_passed", player: 0 },
      { type: "round_ended", scores: [12, 30], winner: 1 },
    ]),
  };
  const { api } = fakeApi(answers);
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  // Round 1 is over: the view is in round 2 now. The page says so over the
  // board, and in the log.
  const [banner, ...others] = await screen.findAllByText(
    "Round 1: the AI won, 30 to 12.",
  );
  expect(others).toHaveLength(1);
  expect(
    banner?.compareDocumentPosition(
      screen.getByRole("region", { name: "Board" }),
    ),
  ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  expect(screen.getByRole("heading", { name: "Round 2" })).toBeInTheDocument();
  expect(log()).toEqual([["You passed.", "Round 1: the AI won, 30 to 12."]]);

  answers[PLAY] = played(view({ ...ROUND_1, round: 2 }), [
    { type: "player_passed", player: 0 },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Pass" }));

  await waitFor(() => {
    expect(log()).toHaveLength(2);
  });
  // Only in the log now.
  expect(screen.getAllByText("Round 1: the AI won, 30 to 12.")).toHaveLength(1);
});

/** Return the first card in the hand the player may choose. */
function firstCardButton() {
  return within(screen.getByRole("list", { name: "Your hand" })).getAllByRole(
    "button",
  )[0];
}

test("once a match starts, the focus is on the first card the player may choose", async () => {
  renderApp(fakeApi(A_MATCH).api);

  await startMatch();

  // The focus moves once the page is drawn.
  await waitFor(() => {
    expect(firstCardButton()).toHaveFocus();
  });
  expect(firstCardButton()).toHaveAccessibleName(
    "Soldier (4 melee/ranged, agile)",
  );
});

test("after a move, the focus goes to the first card of the new view", async () => {
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  // Hoarfrost is swapped: in the new view, it can't be chosen.
  fireEvent.click(
    screen.getByRole("button", { name: "Hoarfrost (weather on melee)" }),
  );
  const button = screen.getByRole("button", { name: "Swap Hoarfrost" });
  button.focus();
  fireEvent.click(button);

  await screen.findByRole("button", { name: "Pass" });
  await waitFor(() => {
    expect(firstCardButton()).toHaveFocus();
  });
});

test("after a move, the focus stays where the player put it, out of the moves", async () => {
  const answer = later();
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: answer.response });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  // While the move is on its way, the player opens the log to read what
  // happened.
  fireEvent.click(screen.getByRole("button", { name: "Show log" }));
  const what = screen.getByRole("log", { name: "What happened" });
  what.focus();
  answer.answer(Response.json(played(ROUND_1).body));

  await screen.findByRole("button", { name: "Pass" });
  // Once the page has had the time to move the focus.
  await settle();
  expect(what).toHaveFocus();
});

test("once the match is over, the focus is on playing again", async () => {
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(over) });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  expect(
    await screen.findByRole("button", { name: "Play again" }),
  ).toHaveFocus();
});

test("the second click of a double click on playing again doesn't start a match", async () => {
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(over) });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  fireEvent.click(await screen.findByRole("button", { name: "Play again" }), {
    detail: 1,
  });
  // The decks are in the cache, so the second click lands on one.
  fireEvent.click(screen.getByRole("button", { name: "Humans" }), {
    detail: 2,
  });

  await settle();
  expect(sent(requests, "POST /api/matches")).toHaveLength(1);
  expect(
    screen.getByRole("heading", { name: "Choose your deck" }),
  ).toBeInTheDocument();
});

test("two clicks on the decks in the same instant start one match", async () => {
  const { api, requests } = fakeApi(A_MATCH);
  renderApp(api);

  // No person can, but a script can click twice before the page shows the
  // decks disabled.
  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));
  fireEvent.click(screen.getByRole("button", { name: "Robots" }));

  await screen.findByRole("heading", { name: "Round 1" });
  await settle();
  const [started, ...others] = sent(requests, "POST /api/matches");
  expect(others).toHaveLength(0);
  expect(await started?.json()).toEqual({ deck: "humans" });
});

test("after a move that didn't work, the focus goes to the first card once moves can be made", async () => {
  const answer = later();
  const { api } = fakeApi({
    ...A_MATCH,
    [PLAY]: turnedDown(500, "server_error"),
    "GET /api/matches/a-match": answer.response,
  });
  renderApp(api);
  await startMatch();

  fireEvent.click(
    screen.getByRole("button", { name: "Hoarfrost (weather on melee)" }),
  );
  const button = screen.getByRole("button", { name: "Swap Hoarfrost" });
  button.focus();
  fireEvent.click(button);
  // The page asks for the match again, and no move can be made meanwhile.
  await waitFor(() => {
    expect(button).toBeDisabled();
  });
  // The match is as it was: the move wasn't played. The new view lets the
  // card chosen go.
  answer.answer(Response.json(aMatch(view(), 3)));

  await waitFor(() => {
    expect(firstCardButton()).toHaveFocus();
  });
  expect(
    screen.queryByRole("button", { pressed: true }),
  ).not.toBeInTheDocument();
});

test("the second click of a double click on the last move doesn't leave the end of the match", async () => {
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  renderApp(fakeApi({ ...A_MATCH, [PLAY]: played(over) }).api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });
  // The answer came first, so the second click lands on "Play again".
  fireEvent.click(await screen.findByRole("button", { name: "Play again" }), {
    detail: 2,
  });

  await settle();
  expect(screen.getByText("You won the match!")).toBeInTheDocument();
});

test("for a card with nowhere to choose, the page says clicking it again plays it", async () => {
  const turn = view({
    legal_actions: [
      { type: "play_special", card: "hoarfrost" },
      { type: "pass" },
    ],
  });
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(turn) });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));

  fireEvent.click(
    await screen.findByRole("button", { name: "Hoarfrost (weather on melee)" }),
  );

  expect(
    screen.getByText("Click Hoarfrost again to play it."),
  ).toBeInTheDocument();
});

test("the page says what to do, and a card chosen can be let go with Cancel", async () => {
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();
  expect(
    screen.getByText("Choose a card to swap, or keep this hand."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("Choose a card to play, or pass.");

  const [soldier] = screen.getAllByRole("button", { name: /^Soldier/ });
  fireEvent.click(soldier as HTMLElement);

  expect(
    screen.getByText(
      "Choose where to play Soldier, or click it again to put it back.",
    ),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(soldier).toHaveAttribute("aria-pressed", "false");
  expect(
    screen.queryByRole("button", { name: "Cancel" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("Choose a card to play, or pass."),
  ).toBeInTheDocument();
});

/**
 * Let the page move things, as the system of a player who didn't ask for
 * reduced motion does, and make the page's clock the test's, until the test
 * is over. (jsdom has no `matchMedia`: without it the page moves nothing.)
 */
function withMotion(reduced = false) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduced && query === "(prefers-reduced-motion: reduce)",
  }));
  // The rest of the time goes on as well, for the requests.
  vi.useFakeTimers({ shouldAdvanceTime: true });
  onTestFinished(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
}

// After keeping the hand, the AI plays a Soldier in its melee row.
const AI_PLAYED = played(
  view({
    players: [
      side(),
      side({
        rows: {
          ...side().rows,
          melee: {
            ...side().rows.melee,
            units: [{ card: SOLDIER, strength: 4 }],
          },
        },
      }),
    ],
    legal_actions: [{ type: "pass" }],
  }),
  [
    { type: "redraw_ended", player: 0 },
    { type: "unit_played", player: 1, card: "soldier", row: "melee", side: 1 },
  ],
);

/** Return the card on its way to the board, large on the right, if any. */
function showcase() {
  return document.querySelector("[data-showcase]");
}

test("a card played shows on the right, then goes to its place, which shows it only then", async () => {
  withMotion();
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: AI_PLAYED });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("The AI played Soldier in the melee row.");

  // Only a picture: screen readers read the log, and the card in its place.
  expect(showcase()).toHaveAttribute("data-showcase", "soldier");
  // The log is out of sight meanwhile, but still read.
  const log = screen.getByRole("log", { name: "What happened" });
  expect(log.closest("section")).toHaveClass("opacity-0");
  expect(showcase()?.closest("[aria-hidden]")).not.toBeNull();
  const place = document.querySelector('[data-cell="1:melee:0"]');
  expect(place).toHaveClass("opacity-0");
  expect(
    within(place as HTMLElement).getByRole("img", { name: /^Soldier/ }),
  ).toBeInTheDocument();

  await act(() => vi.advanceTimersByTimeAsync(TIMES.show));
  // On its way.
  expect(showcase()).not.toBeNull();
  expect(place).toHaveClass("opacity-0");

  await act(() => vi.advanceTimersByTimeAsync(TIMES.fly));
  expect(showcase()).toBeNull();
  expect(place).not.toHaveClass("opacity-0");
  expect(log.closest("section")).not.toHaveClass("opacity-0");
});

test("a move can be made while the last one plays out: the board shows the new one", async () => {
  withMotion();
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: AI_PLAYED });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("The AI played Soldier in the melee row.");

  expect(screen.getByRole("button", { name: "Pass" })).toBeEnabled();
});

test.each([
  ["asked for reduced motion", true],
  ["can't be asked", undefined],
])("when the system %s, a move shows at once", async (_, reduced) => {
  if (reduced !== undefined) {
    withMotion(reduced);
  }
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: AI_PLAYED });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("The AI played Soldier in the melee row.");

  expect(showcase()).toBeNull();
  expect(document.querySelector('[data-cell="1:melee:0"]')).not.toHaveClass(
    "opacity-0",
  );
});

// A turn with a Hoarfrost, which says what it does, in the hand.
const WITH_HOARFROST = played(
  view({
    hand: [
      {
        ...HOARFROST,
        description: ["Weather: every unit in the melee rows has strength 1."],
      },
    ],
    legal_actions: [
      { type: "play_special", card: "hoarfrost" },
      { type: "pass" },
    ],
  }),
);

/** Return the large card on the right that a card pointed at shows, if any. */
function preview() {
  return document.querySelector("[data-preview]");
}

test("a card pointed at or focused shows large on the right, with what it does, and the log fades out", async () => {
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: WITH_HOARFROST });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("Choose a card to play, or pass.");
  const card = await screen.findByRole("button", {
    name: "Hoarfrost (weather on melee)",
  });
  // Screen readers read what it does from the card itself.
  expect(card).toHaveAttribute(
    "aria-description",
    "Weather: every unit in the melee rows has strength 1.",
  );
  expect(preview()).toBeNull();

  fireEvent.mouseOver(card);

  expect(preview()).toHaveAttribute("data-preview", "hoarfrost");
  expect(preview()).toHaveTextContent(
    "Weather: every unit in the melee rows has strength 1.",
  );
  expect(preview()?.closest("[aria-hidden]")).not.toBeNull();
  const log = screen.getByRole("log", { name: "What happened" });
  expect(log.closest("section")).toHaveClass("opacity-0");

  fireEvent.mouseLeave(
    screen.getByRole("region", { name: "Board" }).parentElement as HTMLElement,
  );
  expect(preview()).toBeNull();
  expect(log.closest("section")).not.toHaveClass("opacity-0");

  // The focus shows it only while the player uses the keyboard: the page
  // moves the focus by itself after a move.
  fireEvent.focus(card);
  expect(preview()).toBeNull();
  fireEvent.blur(card);
  fireEvent.keyDown(card, { key: "Tab" });
  fireEvent.focus(card);
  expect(preview()).toHaveAttribute("data-preview", "hoarfrost");
  fireEvent.blur(card);
  expect(preview()).toBeNull();
});

test("a card played on its way comes before a card pointed at", async () => {
  withMotion();
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: AI_PLAYED });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("The AI played Soldier in the melee row.");

  fireEvent.mouseOver(
    document.querySelector('[data-cell="1:melee:0"] [data-card]') as Element,
  );

  expect(showcase()).not.toBeNull();
  expect(preview()).toBeNull();
});

test("the log is out of sight until the player asks for it, but still read", async () => {
  const { api } = fakeApi(A_MATCH);
  renderApp(api);
  await startMatch();
  const log = screen.getByRole("log", { name: "What happened" });
  const show = screen.getByRole("button", { name: "Show log" });

  expect(log).toHaveClass("sr-only");
  expect(log).not.toHaveAttribute("tabindex");
  expect(show).toHaveAttribute("aria-expanded", "false");
  expect(show).toHaveAttribute("aria-controls", log.id);

  fireEvent.click(show);

  expect(log).not.toHaveClass("sr-only");
  expect(log).toHaveAttribute("tabindex", "0");
  fireEvent.click(screen.getByRole("button", { name: "Hide log" }));
  expect(log).toHaveClass("sr-only");
});

test("a player passing and the end of a round show over the whole page, one after the other", async () => {
  withMotion();
  const after = view({
    round: 2,
    legal_actions: [{ type: "pass" }],
  });
  const { api } = fakeApi({
    ...A_MATCH,
    [PLAY]: played(after, [
      { type: "player_passed", player: 1 },
      { type: "round_ended", scores: [5, 3], winner: 0 },
    ]),
  });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await waitFor(() => {
    expect(document.querySelector("[data-banner]")).not.toBeNull();
  });

  // Only a picture: the log says the same.
  const banner = () => document.querySelector("[data-banner]");
  expect(banner()).toHaveTextContent("The AI passed.");
  expect(banner()).toHaveAttribute("aria-hidden", "true");
  await act(() => vi.advanceTimersByTimeAsync(TIMES.announce));
  expect(banner()).toHaveTextContent("Round 1: you won, 5 to 3.");
  await act(() => vi.advanceTimersByTimeAsync(TIMES.announce));
  expect(banner()).toHaveTextContent("Round 2");
  await act(() => vi.advanceTimersByTimeAsync(TIMES.announce));
  expect(banner()).toBeNull();
});

test("once the last move has played out, the end of the match shows each round and who won", async () => {
  withMotion();
  const over = view({ match_over: true, winner: 0, legal_actions: [] });
  const { api } = fakeApi({
    ...A_MATCH,
    [PLAY]: played(over, [
      { type: "round_ended", scores: [10, 12], winner: 1 },
      { type: "round_ended", scores: [9, 4], winner: 0 },
      { type: "round_ended", scores: [7, 7], winner: null },
      { type: "match_ended", winner: 0 },
    ]),
  });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("Match over. You won the match.");

  // Not while the rounds' ends are still showing.
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  // One wait for each round's end: each step starts once the last is over.
  for (let step = 0; step < 3; step++) {
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(TIMES.announce));
  }

  const end = screen.getByRole("dialog", { name: "You won the match!" });
  expect(
    within(end)
      .getAllByRole("row")
      .map((row) => row.textContent),
  ).toEqual(["RoundYouThe AIWon by", "11012The AI", "294You", "377Tie"]);
  expect(within(end).getByRole("button", { name: "Play again" })).toHaveFocus();
});

test("pointing at a row or a pile, and not at a card in it, shows no card", async () => {
  const turn = view({
    players: [side({ discard: [SOLDIER] }), side()],
    legal_actions: [{ type: "pass" }],
  });
  const { api } = fakeApi({ ...A_MATCH, [PLAY]: played(turn) });
  renderApp(api);
  await startMatch();
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }));
  await screen.findByText("Choose a card to play, or pass.");

  fireEvent.mouseOver(
    screen.getByRole("group", { name: "Your deck and discard pile" }),
  );
  expect(preview()).toBeNull();
  fireEvent.mouseOver(screen.getByRole("group", { name: /^Your melee row/ }));
  expect(preview()).toBeNull();

  // The card itself does.
  fireEvent.mouseOver(
    within(
      screen.getByRole("group", { name: "Your deck and discard pile" }),
    ).getByRole("img", { name: /^Soldier/ }),
  );
  expect(preview()).toHaveAttribute("data-preview", "soldier");
});
