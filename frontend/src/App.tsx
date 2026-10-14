import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import type { Action, Api, Match, View } from "./api/client.ts";
import {
  decksQuery,
  matchQuery,
  playAction,
  startMatch,
  type RequestError,
} from "./api/requests.ts";
import { actionText, cardNames, cardText, resultText } from "./text.ts";

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
  const [match, setMatch] = useState<Match | null>(null);

  return (
    <main>
      <h1>Rowen</h1>
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
  onStart: (match: Match) => void;
}) {
  const decks = useQuery(decksQuery(api));
  const start = useMutation({
    mutationFn: (deck: string) => startMatch(api, deck),
    onSuccess: onStart,
  });

  return (
    <section>
      <h2>Choose your deck</h2>
      {start.isError && <p role="alert">{start.error.message}</p>}
      {decks.isPending && <p>Loading the decks…</p>}
      {decks.isError && (
        <>
          <p role="alert">{decks.error.message}</p>
          <button
            type="button"
            onClick={() => {
              void decks.refetch();
            }}
          >
            Try again
          </button>
        </>
      )}
      {decks.isSuccess &&
        decks.data.map((deck) => (
          <button
            key={deck.id}
            type="button"
            // One match at a time: no second click while one starts.
            disabled={start.isPending}
            onClick={() => {
              start.mutate(deck.id);
            }}
          >
            {deck.name}
          </button>
        ))}
    </section>
  );
}

/**
 * The match being played: the round, the cards in hand and the moves the
 * player can make, or who won once it is over.
 *
 * @param started - The match as it started.
 * @param onLeave - Called when the player is done with the match.
 */
function PlayMatch({
  api,
  started,
  onLeave,
}: {
  api: Api;
  started: Match;
  onLeave: () => void;
}) {
  const queryClient = useQueryClient();
  const query = matchQuery(api, started.id);
  // The view starts as the one that came with the match, so the page doesn't
  // ask for it. Each move then puts the view of its answer in the cache.
  const match = useQuery({ ...query, initialData: started.view });
  const play = useMutation({
    mutationKey: ["play"],
    mutationFn: (action: Action) => playAction(api, started.id, action),
    onSuccess: (played) => {
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
      <section>
        <h2>Match not found</h2>
        <p role="alert">This match is no longer on the server.</p>
        <button type="button" onClick={onLeave}>
          Start a new match
        </button>
      </section>
    );
  }

  const view = match.data;
  return (
    <section>
      <h2>Round {view.round}</h2>
      {match.isError ? (
        // The page couldn't ask for the match after a move that didn't work,
        // so its view may be out of date: no move until it can.
        <>
          <p role="alert">{match.error.message}</p>
          <button
            type="button"
            disabled={match.isFetching}
            onClick={() => {
              void match.refetch();
            }}
          >
            Try again
          </button>
        </>
      ) : (
        play.isError && (
          <p role="alert">
            {outOfDate(play.error)
              ? "The match changed. This is where it is now."
              : `${play.error.message} This is where the match is now.`}
          </p>
        )
      )}
      <Hand view={view} />
      {view.match_over ? (
        <>
          <p>{resultText(view)}</p>
          <button type="button" onClick={onLeave}>
            Play again
          </button>
        </>
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
    </section>
  );
}

/** The cards in the player's hand. */
function Hand({ view }: { view: View }) {
  const id = useId();
  return (
    <>
      <h3 id={id}>Your hand</h3>
      <ul aria-labelledby={id}>
        {view.hand.map((card, index) => (
          // Copies of a card share its id, so the place in the hand is the key.
          <li key={index}>{cardText(card)}</li>
        ))}
      </ul>
    </>
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
  return (
    <>
      <h3 id={id}>What you can do</h3>
      <ul aria-labelledby={id}>
        {view.legal_actions.map((action, index) => (
          <li key={index}>
            <button
              type="button"
              disabled={disabled}
              onClick={(event) => {
                // The answer comes before the second click of a double click,
                // which would land on a move of the next view: ignore it.
                // (`detail` counts the clicks in a row, and a key press gives
                // 0. Some systems count a fourth quick click as 1 again: this
                // stops double and triple clicks.)
                if (event.detail > 1) {
                  return;
                }
                onPlay(action);
              }}
            >
              {actionText(action, names)}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

/**
 * Whether the API turned a move down because the page's view of the match is
 * out of date: the move isn't legal now, or the match changed meanwhile.
 */
function outOfDate(error: RequestError): boolean {
  return error.code === "illegal_action" || error.code === "match_changed";
}
