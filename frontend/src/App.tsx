import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type MouseEvent } from "react";
import type { Action, Api, Played, View } from "./api/client.ts";
import {
  decksQuery,
  matchQuery,
  playAction,
  startMatch,
  type RequestError,
} from "./api/requests.ts";
import { Board } from "./Board.tsx";
import {
  actionText,
  cardNames,
  happened,
  resultText,
  type Happened,
} from "./text.ts";

// The look of the page's buttons and warnings (the wood and gold colours are
// in index.css).
const BUTTON =
  "rounded-md border border-gold-600 bg-wood-700 px-3 py-1.5 font-display text-gold-200 shadow shadow-black/50 hover:bg-wood-600 hover:text-gold-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold-300 disabled:cursor-not-allowed disabled:opacity-50";
const ALERT =
  "rounded-md border border-red-400/60 bg-red-950/70 px-3 py-2 text-red-100";

/**
 * Return a click handler that ignores the second click of a double click.
 *
 * The answer to the first click can come before the second, and change what
 * is under the mouse: the second click would land on a move of the next
 * view, or on a deck once the player chose to play again. (`detail` counts
 * the clicks in a row, and a key press gives 0. Some systems count a fourth
 * quick click as 1 again: this stops double and triple clicks.)
 */
function onFirstClick(onClick: () => void) {
  return (event: MouseEvent) => {
    if (event.detail > 1) {
      return;
    }
    onClick();
  };
}

/**
 * The game's page: choose a deck to start a match against the AI, then play
 * it one move at a time, until it is over.
 *
 * The requests go through TanStack Query, so the page needs a
 * `QueryClientProvider` around it, as in `main.tsx`.
 *
 * @param api - The client for the web API: the one `main.tsx` makes, or one
 *   with a fake `fetch` in tests.
 */
export function App({ api }: { api: Api }) {
  // The match being played, as it started, or null while there is none.
  const [match, setMatch] = useState<Played | null>(null);

  return (
    <main className="mx-auto max-w-7xl px-2 py-3 lg:px-4">
      <h1 className="mb-2 text-center font-display text-3xl font-bold tracking-wide text-gold-300 drop-shadow lg:text-4xl">
        Rowen
      </h1>
      {match === null ? (
        <ChooseDeck api={api} onStart={setMatch} />
      ) : (
        <PlayMatch
          api={api}
          started={match}
          onLeave={() => {
            setMatch(null);
          }}
        />
      )}
    </main>
  );
}

/**
 * The decks the player can choose from: choosing one starts a match with it.
 *
 * @param onStart - Called with the match once it has started.
 */
function ChooseDeck({
  api,
  onStart,
}: {
  api: Api;
  onStart: (match: Played) => void;
}) {
  const queryClient = useQueryClient();
  const decks = useQuery(decksQuery(api));
  const start = useMutation({
    mutationKey: ["start"],
    mutationFn: (deck: string) => startMatch(api, deck),
    onSuccess: onStart,
  });

  return (
    <section className="wood mx-auto flex max-w-xl flex-col items-center gap-4 rounded-xl border-2 border-wood-600 p-6 shadow-2xl shadow-black/60">
      <h2 className="font-display text-2xl text-gold-300">Choose your deck</h2>
      {start.isError && (
        <p role="alert" className={ALERT}>
          {start.error.message}
        </p>
      )}
      {decks.isPending && <p className="italic">Loading the decks…</p>}
      {decks.isError && (
        <>
          <p role="alert" className={ALERT}>
            {decks.error.message}
          </p>
          <button
            type="button"
            className={BUTTON}
            onClick={() => {
              void decks.refetch();
            }}
          >
            Try again
          </button>
        </>
      )}
      {decks.isSuccess && (
        <div className="flex flex-wrap justify-center gap-3">
          {decks.data.map((deck) => (
            <button
              key={deck.id}
              type="button"
              className={`${BUTTON} px-8 py-4 text-xl`}
              // One match at a time: no second click while one starts.
              disabled={start.isPending}
              onClick={onFirstClick(() => {
                // Two clicks in the same instant both come before the page
                // shows the buttons disabled.
                if (queryClient.isMutating({ mutationKey: ["start"] }) > 0) {
                  return;
                }
                start.mutate(deck.id);
              })}
            >
              {deck.name}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

/** What happened after one request, numbered from 1 in the match. */
type Entry = Happened & { number: number };

/**
 * The match being played: the round, the board and the moves the player can
 * make, or who won once it is over, and what happened so far.
 *
 * @param started - The match as it started, with what the AI did if it
 *   started.
 * @param onLeave - Called when the player is done with the match.
 */
function PlayMatch({
  api,
  started,
  onLeave,
}: {
  api: Api;
  started: Played;
  onLeave: () => void;
}) {
  const queryClient = useQueryClient();
  const query = matchQuery(api, started.id);
  // The view starts as the one that came with the match, so the page doesn't
  // ask for it. Each move then puts the view of its answer in the cache.
  const match = useQuery({ ...query, initialData: started.view });
  // What happened, the latest first.
  const [log, setLog] = useState<Entry[]>(() =>
    started.events.length === 0
      ? []
      : [
          {
            number: 1,
            ...happened(
              started.events,
              started.view.player,
              cardNames(started.view),
              started.view.round,
            ),
          },
        ],
  );
  const play = useMutation({
    mutationKey: ["play"],
    mutationFn: (action: Action) => playAction(api, started.id, action),
    onSuccess: (played) => {
      // The view the move was played from: the events start in its round.
      const before = queryClient.getQueryData(query.queryKey);
      // Events name their cards by id. A card can leave the view, such as a
      // unit a Scarecrow takes back to the AI's hand, but it was in the view
      // before.
      const names = new Map([
        ...(before === undefined ? [] : cardNames(before)),
        ...cardNames(played.view),
      ]);
      const entry = happened(
        played.events,
        played.view.player,
        names,
        before?.round ?? played.view.round,
      );
      setLog((log) => [{ number: log.length + 1, ...entry }, ...log]);
      queryClient.setQueryData(query.queryKey, played.view);
    },
    onError: (error) => {
      // Ask for the match as it is now, unless it is gone. When no answer
      // came, or the server failed, the move may have been played all the
      // same: a move from the old view could then be played twice.
      if (error.code !== "match_not_found") {
        void queryClient.invalidateQueries({ queryKey: query.queryKey });
      }
    },
  });

  if (
    play.error?.code === "match_not_found" ||
    match.error?.code === "match_not_found"
  ) {
    // The server lost the match, as it does when it restarts.
    return (
      <section className="wood mx-auto flex max-w-xl flex-col items-center gap-4 rounded-xl border-2 border-wood-600 p-6 shadow-2xl shadow-black/60">
        <h2 className="font-display text-2xl text-gold-300">Match not found</h2>
        <p role="alert" className={ALERT}>
          This match is no longer on the server.
        </p>
        <button type="button" className={BUTTON} onClick={onLeave}>
          Start a new match
        </button>
      </section>
    );
  }

  const view = match.data;
  // How the last round went, until the next move.
  const round = log[0]?.round ?? null;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-center font-display text-xl text-gold-300 lg:text-2xl">
        Round {view.round}
      </h2>
      {match.isError ? (
        // The page couldn't ask for the match after a move that didn't work,
        // so its view may be out of date: no move until it can.
        <div className="flex flex-wrap items-center justify-center gap-2">
          <p role="alert" className={ALERT}>
            {match.error.message}
          </p>
          <button
            type="button"
            className={BUTTON}
            disabled={match.isFetching}
            onClick={() => {
              void match.refetch();
            }}
          >
            Try again
          </button>
        </div>
      ) : (
        play.isError && (
          <p role="alert" className={`${ALERT} text-center`}>
            {outOfDate(play.error)
              ? "The match changed. This is where it is now."
              : `${play.error.message} This is where the match is now.`}
          </p>
        )
      )}
      {round !== null && (
        <p className="mx-auto rounded-md border border-gold-400 bg-wood-900/90 px-4 py-1.5 text-center font-display text-lg text-gold-200 shadow-md shadow-black/50">
          {round}
        </p>
      )}
      <Board view={view} />
      {view.match_over ? (
        <div className="flex flex-col items-center gap-3">
          <p className="font-display text-2xl text-gold-200">
            {resultText(view)}
          </p>
          <button
            type="button"
            className={BUTTON}
            // The moves are gone: the focus goes on from here.
            autoFocus
            onClick={onLeave}
          >
            Play again
          </button>
        </div>
      ) : (
        <Moves
          view={view}
          // No move while one is on its way, or while the moves on the page
          // may be out of date: the page is asking for the match, or couldn't.
          disabled={play.isPending || match.isFetching || match.isError}
          onPlay={(action) => {
            // Two clicks in the same instant both come before the page shows
            // the buttons disabled; the cache already knows about the first.
            if (queryClient.isMutating({ mutationKey: ["play"] }) > 0) {
              return;
            }
            play.mutate(action);
          }}
        />
      )}
      <Log entries={log} />
    </section>
  );
}

/**
 * The legal actions of the view, as buttons.
 *
 * @param onPlay - Called with the action of the button the player clicked.
 */
function Moves({
  view,
  disabled,
  onPlay,
}: {
  view: View;
  disabled: boolean;
  onPlay: (action: Action) => void;
}) {
  const names = cardNames(view);
  const id = useId();
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    // After a move, the focus was on the button played, or on nothing once
    // the button was disabled: the next Tab would go on from a move that
    // may now be another one. And once a match starts, the deck chosen is
    // gone. So the focus goes to the first move of the new view, unless the
    // player put it somewhere else.
    const focused = document.activeElement;
    if (focused === document.body || list.current?.contains(focused)) {
      list.current?.querySelector("button")?.focus();
    }
  }, [view]);
  return (
    <div className="flex flex-col items-center gap-2">
      <h3
        id={id}
        className="font-display text-xs tracking-widest text-gold-300/80 uppercase"
      >
        What you can do
      </h3>
      {/* Tailwind takes the bullets off lists, and with them Safari drops the
          list from what VoiceOver reads: role="list" puts it back. */}
      <ul
        ref={list}
        role="list"
        aria-labelledby={id}
        className="flex flex-wrap justify-center gap-2"
      >
        {view.legal_actions.map((action, index) => (
          <li key={index}>
            <button
              type="button"
              className={BUTTON}
              disabled={disabled}
              onClick={onFirstClick(() => {
                onPlay(action);
              })}
            >
              {actionText(action, names)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * What happened in the match so far, the latest first: the sentences of
 * each move and of the AI's answer. Screen readers read what is added.
 */
function Log({ entries }: { entries: Entry[] }) {
  const id = useId();
  return (
    <section className="mx-auto w-full max-w-3xl rounded-lg border border-wood-600 bg-wood-900/85 p-2 shadow-inner shadow-black/50">
      <h3
        id={id}
        className="mb-1 font-display text-xs tracking-widest text-gold-300/80 uppercase"
      >
        What happened
      </h3>
      {/* A log: screen readers read what is added to it, but not what was
          there already. It scrolls, so the keyboard can reach it too. */}
      <div
        role="log"
        aria-labelledby={id}
        tabIndex={0}
        className="max-h-48 overflow-y-auto rounded-sm text-sm focus-visible:outline-2 focus-visible:outline-gold-300"
      >
        {entries.length === 0 ? (
          <p className="italic opacity-70">Nothing yet.</p>
        ) : (
          <ol role="list" className="flex flex-col divide-y divide-wood-600">
            {entries.map((entry) => (
              <li key={entry.number} className="py-1">
                {entry.sentences.map((sentence, index) => (
                  // A move can make the same sentence twice, such as two
                  // copies of a unit mustered: the place is the key.
                  <p key={index}>{sentence}</p>
                ))}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

/**
 * Whether the API turned a move down because the page's view of the match is
 * out of date: the move isn't legal now, or the match changed meanwhile.
 */
function outOfDate(error: RequestError): boolean {
  return error.code === "illegal_action" || error.code === "match_changed";
}
