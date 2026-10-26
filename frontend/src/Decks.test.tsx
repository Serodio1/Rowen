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
  type Choices,
  type PlayerDeck,
  type PlayerDecks,
} from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";
import { CAPTAIN, DECKS, HOARFROST, SOLDIER } from "./test-data.ts";

/** An answer of the fake API: a status and a JSON body. */
type Answer = { status: number; body: unknown };

/** A request the fake API got: its method and path, and its JSON body. */
type Sent = { to: string; body: unknown };

/**
 * Show the page with a fake API, which answers each request with the answer
 * for its method and path, such as `"GET /api/my-decks"`, and return the
 * requests it got. The answers may change during a test.
 */
function renderApp(answers: Record<string, Answer>) {
  const sent: Sent[] = [];
  const api = createApi(async (request) => {
    const to = `${request.method} ${new URL(request.url).pathname}`;
    const text = await request.text();
    sent.push({ to, body: text === "" ? null : JSON.parse(text) });
    const answer = answers[to];
    if (answer === undefined) {
      throw new TypeError("Failed to fetch");
    }
    return answer.status === 204
      ? new Response(null, { status: 204 })
      : Response.json(answer.body, { status: answer.status });
  });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <App api={api} />
    </QueryClientProvider>,
  );
  return sent;
}

// The rules are the API's: these small numbers keep the tests short.
const CHOICES = {
  deck: "humans",
  cards: [
    { card: SOLDIER, most: 3 },
    { card: CAPTAIN, most: 1 },
    { card: HOARFROST, most: 3 },
  ],
  min_units: 3,
  max_specials: 1,
} satisfies Choices;

const MINE = {
  id: "d1",
  name: "Mine",
  deck: "humans",
  copies: { soldier: 3, captain: 1 },
} satisfies PlayerDeck;

/** Return the answer with the player's decks. */
function decks(list: PlayerDeck[], most = 10): Answer {
  return { status: 200, body: { decks: list, most } satisfies PlayerDecks };
}

const RUI: Record<string, Answer> = {
  "GET /api/decks": { status: 200, body: { decks: DECKS } },
  "GET /api/session": { status: 200, body: { username: "rui" } },
  "GET /api/decks/humans/choices": { status: 200, body: CHOICES },
};

/** Open the player's decks. */
async function openDecks() {
  fireEvent.click(await screen.findByRole("button", { name: "My decks" }));
}

/** Return the button of a card in one of the editor's columns. */
function card(column: "Cards" | "Your deck", name: RegExp) {
  return within(screen.getByRole("list", { name: column })).getByRole(
    "button",
    { name },
  );
}

test("a guest has no decks to open", async () => {
  renderApp({
    ...RUI,
    "GET /api/session": {
      status: 401,
      body: { code: "not_logged_in", message: "The player isn't logged in." },
    },
  });

  await screen.findByRole("button", { name: "Log in" });
  expect(
    screen.queryByRole("button", { name: "My decks" }),
  ).not.toBeInTheDocument();
});

test("the player's decks are listed, and Back goes to the decks to play", async () => {
  renderApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();

  expect(screen.getByRole("heading", { name: "My decks" })).toHaveFocus();
  const list = await screen.findByRole("list", { name: "Your decks" });
  expect(list).toHaveTextContent("Mine Humans, 4 cards");
  // The button that would open them again is gone meanwhile.
  expect(
    screen.queryByRole("button", { name: "My decks" }),
  ).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(
    await screen.findByRole("heading", { name: "Choose your deck" }),
  ).toHaveFocus();
});

test("a player with no deck is told so", async () => {
  renderApp({ ...RUI, "GET /api/my-decks": decks([]) });
  await openDecks();

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
});

test("a deck is built by adding cards from one column to the other", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([]),
  };
  const sent = renderApp(answers);
  await openDecks();
  fireEvent.click(
    await screen.findByRole("button", { name: "New Humans deck" }),
  );

  expect(
    screen.getByRole("heading", { name: "New Humans deck" }),
  ).toHaveFocus();
  await screen.findByRole("list", { name: "Cards" });
  const save = screen.getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  expect(
    screen.getByText("Choose cards on the left to add them."),
  ).toBeVisible();

  for (let n = 0; n < 3; n++) {
    fireEvent.click(card("Cards", /^Add Soldier/));
  }
  // At the most a card may have, it can't be added again.
  expect(card("Cards", /^Add Soldier/)).toBeDisabled();
  expect(card("Cards", /^Add Soldier/)).toHaveAccessibleName(/3 of 3$/);
  expect(card("Your deck", /^Take out Soldier/)).toHaveAccessibleName(
    /3 in the deck$/,
  );
  expect(screen.getByText("Units: 3 (at least 3)")).toBeVisible();
  expect(save).toBeEnabled();

  // Too many special cards, then one fewer.
  fireEvent.click(card("Cards", /^Add Hoarfrost/));
  fireEvent.click(card("Cards", /^Add Hoarfrost/));
  expect(screen.getByText("Special cards: 2 (at most 1)")).toBeVisible();
  expect(save).toBeDisabled();
  fireEvent.click(card("Your deck", /^Take out Hoarfrost/));
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "  Soldiers  " },
  });

  answers["GET /api/my-decks"] = decks([
    { id: "d2", name: "Soldiers", deck: "humans", copies: {} },
  ]);
  answers["POST /api/my-decks"] = { status: 201, body: MINE };
  fireEvent.click(save);

  const list = await screen.findByRole("list", { name: "Your decks" });
  expect(list).toHaveTextContent("Soldiers");
  expect(sent.find((request) => request.to === "POST /api/my-decks")).toEqual({
    to: "POST /api/my-decks",
    body: {
      name: "Soldiers",
      deck: "humans",
      copies: { soldier: 3, hoarfrost: 1 },
    },
  });
});

test("a card taken out to none is left out of the deck", async () => {
  const sent = renderApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.click(card("Your deck", /^Take out Captain/));
  fireEvent.click(card("Cards", /^Add Hoarfrost/));
  fireEvent.click(card("Cards", /^Add Captain/));
  fireEvent.click(card("Your deck", /^Take out Hoarfrost/));
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(
      sent.find((request) => request.to === "PUT /api/my-decks/d1")?.body,
    ).toEqual({
      name: "Mine",
      deck: "humans",
      copies: { soldier: 3, captain: 1 },
    });
  });
});

test("a deck is changed in place, with its copies to start from", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
  };
  const sent = renderApp(answers);
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));

  expect(screen.getByRole("heading", { name: "Change Mine" })).toHaveFocus();
  await screen.findByRole("list", { name: "Cards" });
  expect(screen.getByLabelText("Name")).toHaveValue("Mine");
  expect(card("Your deck", /^Take out Soldier/)).toHaveAccessibleName(
    /3 in the deck$/,
  );
  fireEvent.click(card("Your deck", /^Take out Soldier/));
  fireEvent.click(card("Cards", /^Add Hoarfrost/));
  answers["PUT /api/my-decks/d1"] = { status: 200, body: MINE };
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  // Back to the list, which takes the focus.
  expect(
    await screen.findByRole("heading", { name: "My decks" }),
  ).toHaveFocus();
  expect(
    sent.find((request) => request.to === "PUT /api/my-decks/d1")?.body,
  ).toEqual({
    name: "Mine",
    deck: "humans",
    copies: { soldier: 2, captain: 1, hoarfrost: 1 },
  });
});

test("Cancel leaves the deck as it was", async () => {
  const sent = renderApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });
  fireEvent.click(card("Your deck", /^Take out Soldier/));

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(
    await screen.findByRole("heading", { name: "My decks" }),
  ).toHaveFocus();
  expect(sent.some((request) => request.to.startsWith("PUT"))).toBe(false);
});

test("a deck the API turns down says why, and stays to be changed", async () => {
  renderApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "PUT /api/my-decks/d1": {
      status: 422,
      body: { code: "invalid_deck", message: "This deck breaks the rules." },
    },
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This deck breaks the rules.",
  );
  expect(screen.getByRole("heading", { name: "Change Mine" })).toBeVisible();
});

test("deleting a deck asks first", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
  };
  const sent = renderApp(answers);
  await openDecks();

  fireEvent.click(await screen.findByRole("button", { name: "Delete Mine" }));
  expect(screen.getByText("Delete Mine?")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  expect(sent.some((request) => request.to.startsWith("DELETE"))).toBe(false);

  fireEvent.click(screen.getByRole("button", { name: "Delete Mine" }));
  answers["DELETE /api/my-decks/d1"] = { status: 204, body: null };
  answers["GET /api/my-decks"] = decks([]);
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
  expect(sent.map((request) => request.to)).toContain(
    "DELETE /api/my-decks/d1",
  );
});

test("a player with as many decks as they may keep can build no other", async () => {
  renderApp({ ...RUI, "GET /api/my-decks": decks([MINE], 1) });
  await openDecks();

  expect(
    await screen.findByText(
      "You have 1 decks, the most you may keep: delete one to build another.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "New Humans deck" }),
  ).not.toBeInTheDocument();
});

test("a deck the player can't save because they logged out elsewhere shows them as a guest", async () => {
  renderApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "PUT /api/my-decks/d1": {
      status: 401,
      body: { code: "not_logged_in", message: "The player isn't logged in." },
    },
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  // The cache says so (createQueryClient), and the page leaves the decks.
  expect(await screen.findByRole("button", { name: "Log in" })).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: /Change Mine|My decks/ }),
  ).not.toBeInTheDocument();
});
