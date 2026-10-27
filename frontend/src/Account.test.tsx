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
import { createApi } from "./api/client.ts";
import { createQueryClient } from "./api/requests.ts";
import { DECKS } from "./test-data.ts";

/** An answer of the fake API: a status and a JSON body, or any `Response`. */
type Answer = { status: number; body: unknown } | Response | Promise<Response>;

/**
 * Show the page with a fake API, which answers each request with the answer
 * for its method and path, such as `"GET /api/session"`, and return the
 * requests it got. The answers may change during a test.
 */
function renderApp(answers: Record<string, Answer>) {
  const requests: Request[] = [];
  const api = createApi((request) => {
    requests.push(request);
    const answer =
      answers[`${request.method} ${new URL(request.url).pathname}`];
    if (answer === undefined) {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (answer instanceof Response || answer instanceof Promise) {
      return Promise.resolve(answer).then((response) => response.clone());
    }
    return Promise.resolve(
      Response.json(answer.body, { status: answer.status }),
    );
  });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <App api={api} />
    </QueryClientProvider>,
  );
  return requests;
}

/** Return the requests for one method and path. */
function sent(requests: Request[], to: string) {
  return requests.filter(
    (request) => `${request.method} ${new URL(request.url).pathname}` === to,
  );
}

const DECKS_ANSWER = { status: 200, body: { decks: DECKS } };
const GUEST = {
  "GET /api/decks": DECKS_ANSWER,
  "GET /api/session": {
    status: 401,
    body: { code: "not_logged_in", message: "The player isn't logged in." },
  },
};
const RUI = { status: 200, body: { username: "rui" } };

/** Open the dialog, fill it in and send it. */
async function logInWith(username: string, password: string) {
  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: password },
  });
  const dialog = screen.getByRole("dialog");
  fireEvent.submit(dialog.querySelector("form") as HTMLFormElement);
}

test("a guest is asked to log in, and can play without", async () => {
  renderApp(GUEST);

  expect(
    await screen.findByRole("button", { name: "Log in" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("button", { name: "Humans" }),
  ).toBeInTheDocument();
});

test("a player who is logged in sees their username", async () => {
  renderApp({ "GET /api/decks": DECKS_ANSWER, "GET /api/session": RUI });

  expect(await screen.findByText("rui")).toBeInTheDocument();
  expect(screen.getByText(/Logged in as/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Log in" })).toBeNull();
});

test("when the page can't ask, the player is taken for a guest", async () => {
  renderApp({ "GET /api/decks": DECKS_ANSWER });

  expect(
    await screen.findByRole("button", { name: "Log in" }),
  ).toBeInTheDocument();
});

test("nothing shows until the page knows who is logged in", async () => {
  const requests = renderApp({
    "GET /api/decks": DECKS_ANSWER,
    "GET /api/session": new Promise<Response>(() => {}),
  });

  await screen.findByRole("button", { name: "Humans" });
  expect(sent(requests, "GET /api/session")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: /Log/ })).toBeNull();
});

test("logging in sends the username in lower case, and closes the dialog", async () => {
  const answers: Record<string, Answer> = { ...GUEST };
  const requests = renderApp(answers);
  answers["POST /api/session"] = RUI;

  await logInWith("Rui", "dragon123");

  expect(screen.getByLabelText("Username")).toHaveValue("rui");
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  const [request] = sent(requests, "POST /api/session");
  expect(await request?.json()).toEqual({
    username: "rui",
    password: "dragon123",
  });
  expect(screen.getByText("rui")).toBeInTheDocument();
  // The button that opened the dialog is gone: the focus goes to the top.
  expect(screen.getByRole("button", { name: "My matches" })).toHaveFocus();
});

test("the dialog keeps the rest of the page out of reach", async () => {
  renderApp(GUEST);

  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));

  expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  expect(screen.getByRole("main", { hidden: true })).toHaveAttribute("inert");
  expect(screen.getByLabelText("Username")).toHaveFocus();
});

test("a wrong password is said in the dialog, which stays open", async () => {
  renderApp({
    ...GUEST,
    "POST /api/session": {
      status: 401,
      body: {
        code: "wrong_credentials",
        message: "The username or the password is wrong.",
      },
    },
  });

  await logInWith("rui", "dragon124");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The username or the password is wrong.",
  );
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("making an account sends it to /accounts, with the rules shown", async () => {
  const requests = renderApp({ ...GUEST, "POST /api/accounts": RUI });

  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  fireEvent.click(
    screen.getByRole("button", { name: "No account yet? Create one" }),
  );

  expect(
    screen.getByRole("heading", { name: "Create an account" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Username")).toHaveAccessibleDescription(
    "3 to 20 lower-case letters, digits, _ or -.",
  );
  expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(
    "At least 8 characters.",
  );
  expect(screen.getByLabelText("Password")).toHaveAttribute(
    "autocomplete",
    "new-password",
  );
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "rui" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "dragon123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create an account" }));

  await waitFor(() => {
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  expect(sent(requests, "POST /api/accounts")).toHaveLength(1);
  expect(sent(requests, "POST /api/session")).toHaveLength(0);
  expect(screen.getByText("rui")).toBeInTheDocument();
});

test("a taken username is said, and switching back clears it", async () => {
  renderApp({
    ...GUEST,
    "POST /api/accounts": {
      status: 409,
      body: { code: "username_taken", message: "Choose another." },
    },
  });

  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  fireEvent.click(
    screen.getByRole("button", { name: "No account yet? Create one" }),
  );
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "rui" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "dragon123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create an account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose another.");

  fireEvent.click(
    screen.getByRole("button", { name: "I have an account: log in" }),
  );

  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByLabelText("Password")).toHaveAttribute(
    "autocomplete",
    "current-password",
  );
});

test.each(["Cancel", "Escape"])(
  "%s closes the dialog, and the focus goes back to Log in",
  async (how) => {
    const requests = renderApp(GUEST);

    fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
    if (how === "Escape") {
      fireEvent.keyDown(screen.getByLabelText("Username"), { key: "Escape" });
    } else {
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    }

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
    expect(screen.getByRole("button", { name: "Log in" })).toHaveFocus();
    expect(sent(requests, "POST /api/session")).toHaveLength(0);
  },
);

test("a second submit while the first is on its way sends nothing", async () => {
  const requests = renderApp({
    ...GUEST,
    "POST /api/session": new Promise<Response>(() => {}),
  });

  await logInWith("rui", "dragon123");
  fireEvent.submit(
    screen.getByRole("dialog").querySelector("form") as HTMLFormElement,
  );

  await waitFor(() => {
    expect(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Log in",
      }),
    ).toBeDisabled();
  });
  expect(sent(requests, "POST /api/session")).toHaveLength(1);
});

test("the fields ask the browser for the API's rules", async () => {
  renderApp(GUEST);

  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));

  const username = screen.getByLabelText("Username");
  const password = screen.getByLabelText("Password");
  expect(username).toBeRequired();
  expect(username).toHaveAttribute("minlength", "3");
  expect(username).toHaveAttribute("maxlength", "20");
  expect(username).toHaveAttribute("pattern", "[a-z0-9_\\-]{3,20}");
  expect(username).toHaveAttribute("autocomplete", "username");
  expect(password).toBeRequired();
  expect(password).toHaveAttribute("type", "password");
});

test("a password is counted in characters, as the API counts them", async () => {
  renderApp(GUEST);
  fireEvent.click(await screen.findByRole("button", { name: "Log in" }));
  const password = screen.getByLabelText<HTMLInputElement>("Password");
  const type = (value: string) => {
    fireEvent.change(password, { target: { value } });
    return password.validationMessage;
  };

  // 4 characters, though 8 UTF-16 units.
  expect(type("🐉🐉🐉🐉")).toBe("Use at least 8 characters.");
  expect(type("phoenix")).toBe("Use at least 8 characters.");
  expect(type("phoenix4")).toBe("");
  expect(type("a".repeat(129))).toBe("Use at most 128 characters.");
  // 100 characters, though 200 UTF-16 units.
  expect(type("🐉".repeat(100))).toBe("");
  expect(password).toBeValid();
});

test("logging out ends the session, and the page shows Log in", async () => {
  const requests = renderApp({
    "GET /api/decks": DECKS_ANSWER,
    "GET /api/session": RUI,
    "DELETE /api/session": new Response(null, { status: 204 }),
  });

  fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

  expect(
    await screen.findByRole("button", { name: "Log in" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("rui")).toBeNull();
  expect(sent(requests, "DELETE /api/session")).toHaveLength(1);
});

test("a log out that didn't work says so, and the player stays in", async () => {
  renderApp({
    "GET /api/decks": DECKS_ANSWER,
    "GET /api/session": RUI,
    // Asked for on the decks to play: none, so they show no alert.
    "GET /api/my-decks": { status: 200, body: { decks: [], most: 10 } },
    "DELETE /api/session": {
      status: 403,
      body: { code: "forbidden_origin", message: "From another site." },
    },
  });

  fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "From another site.",
  );
  expect(screen.getByText("rui")).toBeInTheDocument();
});

test("a log out with no answer says the server couldn't be reached", async () => {
  renderApp({ "GET /api/decks": DECKS_ANSWER, "GET /api/session": RUI });

  fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reach the server.",
  );
});
