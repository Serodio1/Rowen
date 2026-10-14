import { onlineManager, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { App } from "./App.tsx";
import { createApi, type View } from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";
import { DECKS, HOARFROST, view } from "./test-data.ts";

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
  "POST /api/matches": { status: 201, body: { id: "a-match", view: view() } },
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

/** Return the API's answer to a move: the view after it, with no events. */
function played(after: View) {
  return { status: 200, body: { id: "a-match", view: after, events: [] } };
}

/** Return an answer of the API that turns a request down. */
function turnedDown(status: number, code: string): Answer {
  return { status, body: { code, message: `The API says ${code}.` } };
}

/** Return the button of each move the page offers. */
function movesButtons() {
  return within(
    screen.getByRole("list", { name: "What you can do" }),
  ).getAllByRole("button");
}

/** Return each card in the player's hand, as a screen reader names it. */
function hand() {
  return within(screen.getByRole("list", { name: "Your hand" }))
    .getAllByRole("img")
    .map((card) => card.getAttribute("aria-label"));
}

/** Return the text of each move the page offers. */
function moves() {
  return movesButtons().map((button) => button.textContent);
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
  expect(moves()).toEqual(["Swap Soldier", "Swap Hoarfrost", "Keep this hand"]);
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
  // The action goes back as the view listed it.
  expect(await move?.json()).toEqual({ type: "end_redraw" });
  expect(hand()).toEqual(["Hoarfrost (weather on melee)"]);
  expect(moves()).toEqual(["Pass"]);
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

test("no move can be made while one is on its way", async () => {
  const answer = later();
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: answer.response });
  renderApp(api);
  await startMatch();

  fireEvent.click(screen.getByRole("button", { name: "Swap Soldier" }), {
    detail: 1,
  });

  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Keep this hand" }),
    ).toBeDisabled();
  });
  for (const button of movesButtons()) {
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
  expect(moves()).toContain("Pass");
});

test("two clicks in the same instant make one move", async () => {
  const { api, requests } = fakeApi({ ...A_MATCH, [PLAY]: played(ROUND_1) });
  renderApp(api);
  await startMatch();

  // No person can, but a script can click twice before the page shows the
  // moves disabled.
  fireEvent.click(screen.getByRole("button", { name: "Swap Soldier" }), {
    detail: 1,
  });
  fireEvent.click(screen.getByRole("button", { name: "Keep this hand" }), {
    detail: 1,
  });

  await screen.findByRole("button", { name: "Pass" });
  await settle();
  const [move, ...others] = sent(requests, PLAY);
  expect(others).toHaveLength(0);
  expect(await move?.json()).toEqual({ type: "redraw", card: "soldier" });
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
    expect(
      screen.queryByRole("list", { name: "What you can do" }),
    ).not.toBeInTheDocument();

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
    for (const button of movesButtons()) {
      expect(button).toBeDisabled();
    }
    expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(1);

    answer.answer(Response.json({ id: "a-match", view: ROUND_1 }));

    expect(await screen.findByRole("button", { name: "Pass" })).toBeEnabled();
    expect(moves()).toEqual([
      "Play Soldier in the melee row",
      "Play Soldier in the ranged row",
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
  for (const button of movesButtons()) {
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

  answer.answer(Response.json({ id: "a-match", view: ROUND_1 }));

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
    for (const button of movesButtons()) {
      expect(button).toBeDisabled();
    }
    expect(sent(requests, "GET /api/matches/a-match")).toHaveLength(1);

    // The move was played: the match is in round 1.
    answer.answer(Response.json({ id: "a-match", view: ROUND_1 }));

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
