import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import type { Api, Credentials } from "./api/client.ts";
import {
  forgetMatches,
  logIn,
  logOut,
  register,
  sessionQuery,
} from "./api/requests.ts";
import { ALERT, BUTTON } from "./styles.ts";

/**
 * Who is logged in, at the top of the page: "Log in" for a guest, or the
 * username, "My matches" and "Log out". A guest needn't log in to play (ADR
 * 0014).
 *
 * While the page doesn't know yet, it shows nothing, so "Log in" doesn't
 * flash before the username. If it can't ask, the player is taken for a
 * guest: playing would fail anyway, and say so.
 *
 * @param onLogIn - Called when the player asks to log in: the page opens the
 *   dialog.
 * @param onShowMatches - Called when the player asks for their matches, or
 *   `undefined` when the page can't show them now: there is no button then.
 * @param onLogOut - Called once the player is logged out.
 */
export function AccountBar({
  api,
  onLogIn,
  onShowMatches,
  onLogOut,
}: {
  api: Api;
  onLogIn: () => void;
  onShowMatches: (() => void) | undefined;
  onLogOut: () => void;
}) {
  const queryClient = useQueryClient();
  const session = useQuery(sessionQuery(api));
  const leave = useMutation({
    mutationKey: ["log_out"],
    mutationFn: () => logOut(api),
    onSuccess: () => {
      queryClient.setQueryData(sessionQuery(api).queryKey, null);
      forgetMatches(queryClient);
      onLogOut();
    },
  });

  if (session.isPending) {
    return null;
  }
  const account = session.data ?? null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 text-sm sm:col-start-3 sm:justify-self-end">
      {leave.isError && (
        <p role="alert" className={`${ALERT} py-1`}>
          {leave.error.message}
        </p>
      )}
      {account === null ? (
        <button type="button" className={BUTTON} onClick={onLogIn}>
          Log in
        </button>
      ) : (
        <>
          <span>
            Logged in as{" "}
            <strong className="text-gold-200">{account.username}</strong>
          </span>
          {onShowMatches !== undefined && (
            <button type="button" className={BUTTON} onClick={onShowMatches}>
              My matches
            </button>
          )}
          <button
            type="button"
            className={BUTTON}
            disabled={leave.isPending}
            onClick={() => {
              leave.mutate();
            }}
          >
            Log out
          </button>
        </>
      )}
    </div>
  );
}

const FIELD =
  "rounded-md border border-gold-600 bg-wood-900 px-2 py-1 text-parchment focus-visible:outline-2 focus-visible:outline-gold-300";

/**
 * The dialog to log in or to make an account, one or the other: a button
 * switches. Once in, the page knows who is logged in and the dialog closes.
 * Cancel or Escape closes it too.
 *
 * The browser checks the fields before sending them (the same rules as the
 * API's), and the username is turned to lower case as it is typed, since
 * that is all the API takes. The API still checks everything.
 *
 * @param onClose - Called when the dialog is done: the page closes it.
 */
export function AccountDialog({
  api,
  onClose,
}: {
  api: Api;
  onClose: () => void;
}) {
  const id = useId();
  const [making, setMaking] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const queryClient = useQueryClient();
  const enter = useMutation({
    mutationKey: ["log_in"],
    mutationFn: (credentials: Credentials) =>
      making ? register(api, credentials) : logIn(api, credentials),
    onSuccess: (account) => {
      queryClient.setQueryData(sessionQuery(api).queryKey, account);
      // Those of whoever was logged in before, if anybody.
      forgetMatches(queryClient);
      onClose();
    },
  });
  const title = making ? "Create an account" : "Log in";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${id}-title`}
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onClose();
        }
      }}
    >
      <form
        className="wood flex w-full max-w-sm flex-col gap-3 rounded-xl border-2 border-gold-400 p-6 shadow-2xl shadow-black"
        onSubmit={(event) => {
          event.preventDefault();
          // Two submits in the same instant (Enter pressed twice) both come
          // before the page shows the button disabled.
          if (queryClient.isMutating({ mutationKey: ["log_in"] }) > 0) {
            return;
          }
          enter.mutate({ username, password });
        }}
      >
        <h2
          id={`${id}-title`}
          className="text-center font-display text-2xl text-gold-200"
        >
          {title}
        </h2>
        {enter.isError && (
          <p role="alert" className={ALERT}>
            {enter.error.message}
          </p>
        )}
        <label className="flex flex-col gap-1">
          Username
          <input
            className={FIELD}
            // The dialog opens on a click: the keyboard goes on from here.
            autoFocus
            required
            minLength={3}
            maxLength={20}
            pattern="[a-z0-9_\-]{3,20}"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            aria-describedby={making ? `${id}-username` : undefined}
            value={username}
            onChange={(event) => {
              setUsername(event.target.value.toLowerCase());
            }}
          />
        </label>
        {making && (
          <p id={`${id}-username`} className="-mt-2 text-sm opacity-80">
            3 to 20 lower-case letters, digits, _ or -.
          </p>
        )}
        <label className="flex flex-col gap-1">
          Password
          <input
            className={FIELD}
            type="password"
            required
            minLength={8}
            maxLength={128}
            autoComplete={making ? "new-password" : "current-password"}
            aria-describedby={making ? `${id}-password` : undefined}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        </label>
        {making && (
          <p id={`${id}-password`} className="-mt-2 text-sm opacity-80">
            At least 8 characters.
          </p>
        )}
        <button type="submit" className={BUTTON} disabled={enter.isPending}>
          {title}
        </button>
        <button
          type="button"
          className="text-sm text-gold-300 underline hover:text-gold-200"
          onClick={() => {
            setMaking(!making);
            enter.reset();
          }}
        >
          {making ? "I have an account: log in" : "No account yet? Create one"}
        </button>
        <button type="button" className={BUTTON} onClick={onClose}>
          Cancel
        </button>
      </form>
    </div>
  );
}
