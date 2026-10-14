import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { App } from "./App.tsx";
import { createApi } from "./api/client.ts";
import { DECKS, view } from "./test-data.ts";

/** An answer of the fake API: a status and a JSON body, or any `Response`. */
type Answer = { status: number; body: unknown } | Response;

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
    if (answer instanceof Response) {
      return Promise.resolve(answer);
    }
    return Promise.resolve(
      new Response(JSON.stringify(answer.body), {
        status: answer.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  return { api, requests };
}

const THE_DECKS = { "GET /api/decks": { status: 200, body: { decks: DECKS } } };

const A_MATCH = {
  ...THE_DECKS,
  "POST /api/matches": { status: 201, body: { id: "a-match", view: view() } },
};

test("the page shows the name of the game as its main heading", () => {
  render(<App api={fakeApi(THE_DECKS).api} />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Rowen" }),
  ).toBeInTheDocument();
});

test("the player can choose any of the API's decks", async () => {
  render(<App api={fakeApi(THE_DECKS).api} />);

  expect(screen.getByText("Loading the decks…")).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Humans" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Robots" })).toBeInTheDocument();
  expect(screen.queryByText("Loading the decks…")).not.toBeInTheDocument();
});

test("choosing a deck starts a match with it, and shows the round, the hand and the moves", async () => {
  const { api, requests } = fakeApi(A_MATCH);
  render(<App api={api} />);

  fireEvent.click(await screen.findByRole("button", { name: "Robots" }));

  expect(
    await screen.findByRole("heading", { name: "Round 1" }),
  ).toBeInTheDocument();
  const started = requests.at(-1);
  expect(started?.method).toBe("POST");
  expect(await started?.json()).toEqual({ deck: "robots" });
  const hand = screen.getByRole("list", { name: "Your hand" });
  const moves = screen.getByRole("list", { name: "What you can do" });
  expect(
    within(hand)
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual([
    "Soldier (4 melee/ranged, agile)",
    "Soldier (4 melee/ranged, agile)",
    "Hoarfrost (special)",
  ]);
  expect(
    within(moves)
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual(["Swap Soldier", "Swap Hoarfrost", "Keep this hand"]);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("no deck can be chosen while a match starts", async () => {
  render(<App api={fakeApi(A_MATCH).api} />);

  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

  expect(screen.getByRole("button", { name: "Humans" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Robots" })).toBeDisabled();
  await screen.findByRole("heading", { name: "Round 1" });
});

test("when the API turns a match down, the page shows why, and the player can try again", async () => {
  const turnedDown = {
    code: "unknown_deck",
    message: "There is no such deck.",
  };
  const answers: Record<string, Answer> = {
    ...THE_DECKS,
    "POST /api/matches": { status: 422, body: turnedDown },
  };
  render(<App api={fakeApi(answers).api} />);

  fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "There is no such deck.",
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
    render(<App api={fakeApi(answers).api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Humans" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the server.",
    );
  },
);

test("when the decks can't be loaded, the page says it can't reach the server", async () => {
  render(<App api={fakeApi({}).api} />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
  expect(screen.queryByText("Loading the decks…")).not.toBeInTheDocument();
});

test("an answer for the decks that comes too late is ignored", async () => {
  // A client whose requests wait until the test answers them.
  const late: ((answer: Response) => void)[] = [];
  const slow = createApi(() => new Promise((resolve) => late.push(resolve)));
  // The page gets another client, so it asks for the decks again.
  const { rerender } = render(<App api={slow} />);
  rerender(<App api={fakeApi(THE_DECKS).api} />);
  await screen.findByRole("button", { name: "Humans" });

  // The first client's answers come now, after the second one's.
  await act(async () => {
    for (const answer of late) {
      answer(Response.json({ message: "Too late." }, { status: 500 }));
    }
    await new Promise((resolve) => setTimeout(resolve));
  });

  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
