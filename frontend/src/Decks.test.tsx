import { focusManager } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { expect, onTestFinished, test } from "vitest";
import {
  type Choices,
  type Played,
  type PlayerDeck,
  type PlayerDecks,
} from "./api/client.ts";
import { later, sent, settle, showApp, to, type Answer } from "./fake-api.tsx";
import { CAPTAIN, DECKS, HOARFROST, SOLDIER, view } from "./test-data.ts";

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
function decks(
  list: PlayerDeck[],
  most = 10,
): { status: number; body: PlayerDecks } {
  return { status: 200, body: { decks: list, most } };
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
  showApp({
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
  showApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
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
  showApp({ ...RUI, "GET /api/my-decks": decks([]) });
  await openDecks();

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
});

test("the player's decks that didn't come to their list can be asked for again", async () => {
  const answers: Record<string, Answer> = { ...RUI };
  showApp(answers);
  await openDecks();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );

  answers["GET /api/my-decks"] = decks([MINE]);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("list", { name: "Your decks" }),
  ).toHaveTextContent("Mine");
});

test("the cards that didn't come to the editor can be asked for again", async () => {
  const answers: Record<string, Answer> = {
    "GET /api/decks": { status: 200, body: { decks: DECKS } },
    "GET /api/session": { status: 200, body: { username: "rui" } },
    "GET /api/my-decks": decks([]),
  };
  showApp(answers);
  await openDecks();
  fireEvent.click(
    await screen.findByRole("button", { name: "New Humans deck" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );

  answers["GET /api/decks/humans/choices"] = { status: 200, body: CHOICES };
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(await screen.findByRole("list", { name: "Cards" })).toBeVisible();
});

test("a deck is built by adding cards from one column to the other", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([]),
  };
  const requests = showApp(answers);
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
  // At the most a card may have, it can't be added again, but keeps the
  // focus.
  const soldier = card("Cards", /^Add Soldier/);
  soldier.focus();
  expect(soldier).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(soldier);
  expect(soldier).toHaveAccessibleName(/3 of 3$/);
  expect(soldier).toHaveFocus();
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
  expect(await sent(requests, "POST /api/my-decks")[0]?.json()).toEqual({
    name: "Soldiers",
    deck: "humans",
    copies: { soldier: 3, hoarfrost: 1 },
  });
});

test("a card taken out to none is left out of the deck", async () => {
  const requests = showApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.click(card("Your deck", /^Take out Captain/));
  fireEvent.click(card("Cards", /^Add Hoarfrost/));
  fireEvent.click(card("Cards", /^Add Captain/));
  fireEvent.click(card("Your deck", /^Take out Hoarfrost/));
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(sent(requests, "PUT /api/my-decks/d1")).toHaveLength(1);
  });
  expect(await sent(requests, "PUT /api/my-decks/d1")[0]?.json()).toEqual({
    name: "Mine",
    deck: "humans",
    copies: { soldier: 3, captain: 1 },
  });
});

test("taking out a card's last copy moves the focus to the next card, the one before, or the deck", async () => {
  showApp({
    ...RUI,
    "GET /api/my-decks": decks([
      { ...MINE, copies: { soldier: 1, captain: 1, hoarfrost: 1 } },
    ]),
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.click(card("Your deck", /^Take out Soldier/));
  expect(card("Your deck", /^Take out Captain/)).toHaveFocus();
  fireEvent.click(card("Your deck", /^Take out Hoarfrost/));
  expect(card("Your deck", /^Take out Captain/)).toHaveFocus();
  fireEvent.click(card("Your deck", /^Take out Captain/));
  expect(screen.getByRole("heading", { name: "Your deck" })).toHaveFocus();
});

test("taking out a copy that isn't the last leaves the focus on the card", async () => {
  showApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  const soldier = card("Your deck", /^Take out Soldier/);
  soldier.focus();
  fireEvent.click(soldier);
  expect(card("Your deck", /^Take out Soldier/)).toHaveFocus();
});

test("a deck is changed in place, with its copies to start from", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
  };
  const requests = showApp(answers);
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
  expect(await sent(requests, "PUT /api/my-decks/d1")[0]?.json()).toEqual({
    name: "Mine",
    deck: "humans",
    copies: { soldier: 2, captain: 1, hoarfrost: 1 },
  });
});

test("a deck with a name of only spaces can't be saved", async () => {
  showApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "   " } });

  // Enter doesn't send the form either: a browser doesn't, with its Save off.
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

test("Cancel leaves the deck as it was", async () => {
  const requests = showApp({ ...RUI, "GET /api/my-decks": decks([MINE]) });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });
  fireEvent.click(card("Your deck", /^Take out Soldier/));

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(
    await screen.findByRole("heading", { name: "My decks" }),
  ).toHaveFocus();
  expect(requests.some((request) => to(request).startsWith("PUT"))).toBe(false);
});

test("a deck the API turns down says why, and stays to be changed", async () => {
  showApp({
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

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("This deck breaks the rules.");
  // Next to Save, where a phone shows it.
  expect(alert.closest("form")).toContainElement(
    screen.getByRole("button", { name: "Save" }),
  );
  expect(screen.getByRole("heading", { name: "Change Mine" })).toBeVisible();
});

test("a deck saved after the player left its editor doesn't close the next one", async () => {
  const answer = later();
  const other = { ...MINE, id: "d2", name: "Other" };
  showApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE, other]),
    "PUT /api/my-decks/d1": answer.response,
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(await screen.findByRole("button", { name: "Change Other" }));
  await screen.findByRole("list", { name: "Cards" });

  await act(async () => {
    answer.answer(Response.json(MINE));
    await Promise.resolve();
  });

  expect(screen.getByRole("heading", { name: "Change Other" })).toBeVisible();
});

test("the decks can't start a match before the page knows who is logged in", async () => {
  const answer = later();
  showApp({ ...RUI, "GET /api/session": answer.response });
  const deck = await screen.findByRole("button", { name: "Humans" });
  expect(deck).toBeDisabled();

  answer.answer(Response.json({ username: null }));

  await waitFor(() => {
    expect(deck).toBeEnabled();
  });
});

test("a deck is saved once, however fast Save is pressed", async () => {
  const requests = showApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    // No answer yet.
    "PUT /api/my-decks/d1": new Promise<Response>(() => undefined),
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Change Mine" }));
  await screen.findByRole("list", { name: "Cards" });

  // Two presses of Enter in the same instant, before the page shows Save
  // disabled.
  const form = screen.getByRole("button", { name: "Save" }).closest("form");
  if (form === null) {
    throw new Error("Save isn't in a form.");
  }
  fireEvent.submit(form);
  fireEvent.submit(form);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });
  expect(
    requests.filter((request) => to(request).startsWith("PUT")),
  ).toHaveLength(1);
});

test("deleting a deck asks first", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
  };
  const requests = showApp(answers);
  await openDecks();

  const ask = await screen.findByRole("button", { name: "Delete Mine" });
  fireEvent.click(ask);
  // The question names the buttons, and the focus is on Keep: a second
  // Enter keeps the deck.
  const question = screen.getByRole("group", { name: "Delete Mine?" });
  expect(within(question).getByRole("button", { name: "Keep" })).toHaveFocus();
  expect(ask).not.toBeInTheDocument();
  fireEvent.click(within(question).getByRole("button", { name: "Keep" }));
  expect(requests.some((request) => to(request).startsWith("DELETE"))).toBe(
    false,
  );
  expect(screen.getByRole("button", { name: "Delete Mine" })).toHaveFocus();

  fireEvent.click(screen.getByRole("button", { name: "Delete Mine" }));
  answers["DELETE /api/my-decks/d1"] = { status: 204, body: null };
  answers["GET /api/my-decks"] = decks([]);
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
  // The row went with the focus: it goes to the list's heading.
  expect(screen.getByRole("heading", { name: "My decks" })).toHaveFocus();
  expect(requests.map(to)).toContain("DELETE /api/my-decks/d1");
});

test("a deck is deleted once, however fast Delete is clicked", async () => {
  const requests = showApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    // No answer yet.
    "DELETE /api/my-decks/d1": new Promise<Response>(() => undefined),
  });
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Delete Mine" }));

  // Two clicks in the same instant, before the page shows Delete disabled.
  const remove = screen.getByRole("button", { name: "Delete" });
  fireEvent.click(remove);
  fireEvent.click(remove);

  await waitFor(() => {
    expect(remove).toBeDisabled();
  });
  expect(
    requests.filter((request) => to(request).startsWith("DELETE")),
  ).toHaveLength(1);
});

test("a player with as many decks as they may keep can build no other", async () => {
  showApp({ ...RUI, "GET /api/my-decks": decks([MINE], 1) });
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
  showApp({
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

test("after a player logs out, the next one doesn't see their decks", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "DELETE /api/session": { status: 204, body: null },
  };
  showApp(answers);
  await openDecks();
  await screen.findByRole("list", { name: "Your decks" });
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  fireEvent.click(screen.getByRole("button", { name: "Log out" }));

  answers["POST /api/session"] = { status: 200, body: { username: "ana" } };
  answers["GET /api/my-decks"] = decks([]);
  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Username"), {
    target: { value: "ana" },
  });
  fireEvent.change(within(dialog).getByLabelText("Password"), {
    target: { value: "phoenix456" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "Log in" }));
  await openDecks();

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
  expect(screen.queryByText("Mine")).not.toBeInTheDocument();
});

test("logging in asks for the player's decks once", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/session": {
      status: 401,
      body: { code: "not_logged_in", message: "The player isn't logged in." },
    },
    "POST /api/session": { status: 200, body: { username: "rui" } },
    "GET /api/my-decks": decks([MINE]),
  };
  const requests = showApp(answers);
  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Username"), {
    target: { value: "rui" },
  });
  fireEvent.change(within(dialog).getByLabelText("Password"), {
    target: { value: "dragon123" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "Log in" }));

  await (await yourDecks()).findByRole("button", { name: "Mine (Humans)" });
  await settle();
  expect(sent(requests, "GET /api/my-decks")).toHaveLength(1);
});

test("logging out from the player's decks asks for them no more", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "DELETE /api/session": { status: 204, body: null },
  };
  const requests = showApp(answers);
  await openDecks();
  await screen.findByRole("list", { name: "Your decks" });
  const before = sent(requests, "GET /api/my-decks").length;

  fireEvent.click(screen.getByRole("button", { name: "Log out" }));

  await screen.findByRole("button", { name: "Log in" });
  await settle();
  // A guest's request would only get a 401.
  expect(sent(requests, "GET /api/my-decks")).toHaveLength(before);
});

/** Return the part of the decks to play with the player's own. */
async function yourDecks() {
  return within(await screen.findByRole("region", { name: "Your decks" }));
}

test("a player plays a deck they built from the decks to play", async () => {
  const requests = showApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "POST /api/matches": {
      status: 201,
      body: {
        id: "m1",
        version: 0,
        view: view(),
        moves: [],
        rounds: [],
      } satisfies Played,
    },
  });

  // Its name, and its faction's.
  const mine = await (
    await yourDecks()
  ).findByRole("button", { name: "Mine (Humans)" });
  // At the level the player chose, as with a faction's own deck.
  fireEvent.click(screen.getByRole("radio", { name: "Easy" }));
  fireEvent.click(mine, { detail: 1 });

  expect(
    await screen.findByRole("button", { name: "Keep this hand" }),
  ).toBeEnabled();
  const started = sent(requests, "POST /api/matches");
  expect(started).toHaveLength(1);
  expect(await started[0]?.json()).toEqual({ my_deck: "d1", level: "easy" });
});

test("a guest has no decks of their own to play", async () => {
  const requests = showApp({
    ...RUI,
    "GET /api/session": {
      status: 401,
      body: { code: "not_logged_in", message: "The player isn't logged in." },
    },
  });

  await screen.findByRole("button", { name: "Log in" });
  expect(screen.getByRole("button", { name: "Humans" })).toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Your decks" }),
  ).not.toBeInTheDocument();
  // The API would turn them down.
  expect(requests.map(to)).not.toContain("GET /api/my-decks");
});

test("a player with no deck of their own is told where to build one", async () => {
  showApp({ ...RUI, "GET /api/my-decks": decks([]) });

  expect(
    await (
      await yourDecks()
    ).findByText("No deck of your own yet: build one in My decks."),
  ).toBeInTheDocument();
});

test("the player's decks that didn't come can be asked for again", async () => {
  const answers: Record<string, Answer> = { ...RUI };
  showApp(answers);

  const decksToPlay = await yourDecks();
  expect(await decksToPlay.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );

  answers["GET /api/my-decks"] = decks([MINE]);
  fireEvent.click(decksToPlay.getByRole("button", { name: "Try again" }));
  expect(
    await decksToPlay.findByRole("button", { name: "Mine (Humans)" }),
  ).toBeInTheDocument();
});

test("a deck deleted in another tab says so, and its button goes", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "POST /api/matches": {
      status: 404,
      body: { code: "deck_not_found", message: "The player has no such deck." },
    },
  };
  showApp(answers);

  const decksToPlay = await yourDecks();
  const mine = await decksToPlay.findByRole("button", {
    name: "Mine (Humans)",
  });
  answers["GET /api/my-decks"] = decks([]);
  fireEvent.click(mine, { detail: 1 });

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The player has no such deck.",
  );
  expect(
    await decksToPlay.findByText(
      "No deck of your own yet: build one in My decks.",
    ),
  ).toBeInTheDocument();
});

test("while a match starts with one of the player's decks, no other can", async () => {
  showApp({
    ...RUI,
    "GET /api/my-decks": decks([MINE, { ...MINE, id: "d2", name: "Other" }]),
    // No answer yet.
    "POST /api/matches": new Promise<Response>(() => undefined),
  });

  const decksToPlay = await yourDecks();
  fireEvent.click(
    await decksToPlay.findByRole("button", { name: "Mine (Humans)" }),
    { detail: 1 },
  );

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Humans" })).toBeDisabled();
  });
  for (const name of ["Mine (Humans)", "Other (Humans)"]) {
    expect(decksToPlay.getByRole("button", { name })).toBeDisabled();
  }
});

test("a deck the API turns down as too many asks for the decks again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([]),
    // Built in another tab meanwhile.
    "POST /api/my-decks": {
      status: 409,
      body: { code: "too_many_decks", message: "The player has 10 decks." },
    },
  };
  const requests = showApp(answers);
  await openDecks();
  fireEvent.click(
    await screen.findByRole("button", { name: "New Humans deck" }),
  );
  await screen.findByRole("list", { name: "Cards" });
  for (let n = 0; n < 3; n++) {
    fireEvent.click(card("Cards", /^Add Soldier/));
  }
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The player has 10 decks.",
  );
  await waitFor(() => {
    expect(sent(requests, "GET /api/my-decks")).toHaveLength(2);
  });
});

test("a deck already deleted in another tab asks for the decks again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
    "DELETE /api/my-decks/d1": {
      status: 404,
      body: { code: "deck_not_found", message: "The player has no such deck." },
    },
  };
  showApp(answers);
  await openDecks();
  fireEvent.click(await screen.findByRole("button", { name: "Delete Mine" }));
  answers["GET /api/my-decks"] = decks([]);
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
});

test("coming back to the tab asks for the decks again", async () => {
  const answers: Record<string, Answer> = {
    ...RUI,
    "GET /api/my-decks": decks([MINE]),
  };
  showApp(answers);
  await openDecks();
  await screen.findByRole("list", { name: "Your decks" });

  // Deleted in another tab, while this one was hidden.
  answers["GET /api/my-decks"] = decks([]);
  act(() => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
  });
  onTestFinished(() => {
    focusManager.setFocused(undefined);
  });

  expect(await screen.findByText("No deck built yet.")).toBeInTheDocument();
});
