import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import type { Api, Match, Move, Played, View } from "./api/client.ts";
import {
  decksQuery,
  matchQuery,
  playMove,
  startMatch,
  type RequestError,
} from "./api/requests.ts";
import { Board } from "./Board.tsx";
import { CardPreview, Showcase } from "./Showcase.tsx";
import {
  cardsById,
  mayMove,
  NO_STEPS,
  stageOf,
  stepsOf,
  usePlayOut,
  type Step,
} from "./stage.ts";
import { onFirstClick } from "./clicks.ts";
import {
  otherActions,
  playsOf,
  selfPlay,
  type Chosen,
  type Playing,
} from "./plays.ts";
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
    <main className="mx-auto max-w-384 px-2 py-3 lg:px-4 lg:py-2">
      <h1 className="mb-2 text-center font-display text-3xl font-bold tracking-wide text-gold-300 drop-shadow lg:mb-1">
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
  // The match starts as the one that came when it started, so the page
  // doesn't ask for it. Each move then puts the match of its answer in the
  // cache.
  const match = useQuery({ ...query, initialData: matchOf(started) });
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
  // The animation of the last move, or of the AI's first one: none with
  // reduced motion.
  const [steps, setSteps] = useState<readonly Step[]>(() =>
    mayMove() ? stepsOf(started.events, undefined, started.view) : NO_STEPS,
  );
  const progress = usePlayOut(steps);
  const showing = steps[progress.step];
  // The card pointed at or focused, by id, to show it large.
  const [pointed, setPointed] = useState<string | null>(null);
  // Whether the player is using the keyboard: the page moves the focus by
  // itself after each move, which must not show a card then.
  const typing = useRef(false);
  const resultId = useId();
  // The card the player chose, with the version of the view it was chosen
  // in: a new view lets it go.
  const [chosen, setChosen] = useState<{
    version: number;
    chosen: Chosen;
  } | null>(null);
  // Where the cards and the moves are: the board, and the buttons beside it.
  const boardArea = useRef<HTMLDivElement>(null);
  const movesArea = useRef<HTMLDivElement>(null);
  const play = useMutation({
    mutationKey: ["play"],
    mutationFn: (move: Move) => playMove(api, started.id, move),
    onSuccess: (played) => {
      // The view the move was played from: the events start in its round.
      // (The cache always has one, from `initialData`: `undefined` is only
      // for the types.)
      const before = queryClient.getQueryData(query.queryKey)?.view;
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
      setSteps(
        mayMove() ? stepsOf(played.events, before, played.view) : NO_STEPS,
      );
      queryClient.setQueryData(query.queryKey, matchOf(played));
    },
    onError: (error) => {
      // Ask for the match as it is now, unless it is gone. When no answer
      // came, or the server failed, the move may have been played all the
      // same, and the view on the page is then out of date: a move chosen
      // from it would be turned down.
      if (error.code !== "match_not_found") {
        void queryClient.invalidateQueries({ queryKey: query.queryKey });
      }
    },
  });

  const ready = !(play.isPending || match.isFetching || match.isError);
  const version = match.data.version;
  useEffect(() => {
    // After a move, the focus was on the button played, or on nothing once
    // the button was disabled or gone: the next Tab would go on from a card
    // or a place that may now be another one. And once a match starts, the
    // deck chosen is gone. So once moves can be made, the focus goes to the
    // first card the player may choose, or else to the first button (Pass),
    // unless the player put it somewhere else. (After a move that didn't
    // work, the view may be the same: the cards become usable again. While
    // they are disabled, none can take the focus.)
    const focused = document.activeElement;
    const areas = [boardArea.current, movesArea.current];
    if (
      ready &&
      (focused === document.body ||
        areas.some((area) => area?.contains(focused)))
    ) {
      (
        boardArea.current?.querySelector<HTMLElement>(
          "[data-choosable]:not(:disabled)",
        ) ??
        movesArea.current?.querySelector<HTMLElement>("button:not(:disabled)")
      )?.focus();
    }
  }, [version, ready]);

  if (
    play.error?.code === "match_not_found" ||
    match.error?.code === "match_not_found"
  ) {
    // The server doesn't know the match: it was kept in the memory of a
    // server that restarted, or the link is wrong.
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

  const view = match.data.view;
  const shown = pointed === null ? undefined : cardsById([view]).get(pointed);
  const playing: Playing = {
    actions: view.legal_actions,
    chosen: chosen?.version === match.data.version ? chosen.chosen : null,
    // No move while one is on its way, or while the moves on the page may be
    // out of date: the page is asking for the match, or couldn't.
    disabled: play.isPending || match.isFetching || match.isError,
    onChoose: (card) => {
      setChosen(
        card === null ? null : { version: match.data.version, chosen: card },
      );
    },
    onPlay: (action) => {
      // Two clicks in the same instant both come before the page shows the
      // buttons disabled; the cache already knows about the first.
      if (queryClient.isMutating({ mutationKey: ["play"] }) > 0) {
        return;
      }
      // With the version of the view these moves come from: if the match is
      // at another one when the move reaches the server, the move isn't
      // played, however late it gets there.
      play.mutate({ version: match.data.version, action });
    },
  };
  // How the last round went, until the next move.
  const round = log[0]?.round ?? null;
  // On a wide screen, the board is on the left, and on its right the round,
  // how the last one went, what to do and what happened, so it all fits on
  // one screen. On a narrow one, they are in that order, with the board
  // after how the last round went.
  return (
    <section className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_17rem] lg:grid-rows-[auto_auto_minmax(0,1fr)]">
      <div className="flex flex-col gap-2 lg:col-start-2">
        <h2 className="text-center font-display text-xl text-gold-300 lg:text-2xl">
          Round {view.round}
        </h2>
        {match.isError ? (
          // The page couldn't ask for the match after a move that didn't
          // work, so its view may be out of date: no move until it can.
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
        {/* How the last round went, in a place kept for it even while
            there is none: nothing moves when it shows or goes. It holds the
            longest sentence: one line on a narrow screen, two in the column
            of a wide one. */}
        <div className="flex min-h-11 items-center justify-center lg:min-h-18">
          {round !== null && (
            <p
              // A new round's result fades in.
              key={log[0]?.number}
              className="rounded-md border border-gold-400 bg-wood-900/90 px-4 py-1.5 text-center font-display text-lg text-gold-200 shadow-md shadow-black/50 motion-safe:animate-fade-in"
            >
              {round}
            </p>
          )}
        </div>
      </div>
      <div
        ref={boardArea}
        className="lg:col-start-1 lg:row-span-3 lg:row-start-1"
        // Any card on the board or in the hand, pointed at or focused, shows
        // large on the right, with what it does.
        onMouseOver={(event) => {
          setPointed(cardIn(event.target));
        }}
        onMouseLeave={() => {
          setPointed(null);
        }}
        onKeyDown={() => {
          typing.current = true;
        }}
        onMouseDown={() => {
          typing.current = false;
        }}
        onFocus={(event) => {
          if (typing.current) {
            setPointed(cardIn(event.target));
          }
        }}
        onBlur={() => {
          setPointed(null);
        }}
      >
        <Board
          view={view}
          playing={view.match_over ? undefined : playing}
          stage={stageOf(steps, progress)}
        />
        {showing?.kind === "play" ? (
          // A new element for each card, which comes up from nothing.
          <Showcase
            key={progress.step}
            step={showing}
            flying={progress.flying}
          />
        ) : (
          // A card played comes first.
          shown !== undefined && <CardPreview card={shown} />
        )}
      </div>
      <div ref={movesArea} className="lg:col-start-2 lg:row-start-2">
        {view.match_over ? (
          <div className="flex flex-col items-center gap-3">
            <p
              id={resultId}
              className="text-center font-display text-2xl text-gold-200"
            >
              {resultText(view)}
            </p>
            <button
              type="button"
              className={BUTTON}
              // The moves are gone: the focus goes on from here, and screen
              // readers read who won with it.
              autoFocus
              aria-describedby={resultId}
              // The second click of a double click on the last move could
              // land here, and skip who won.
              onClick={onFirstClick(onLeave)}
            >
              Play again
            </button>
          </div>
        ) : (
          <Controls view={view} playing={playing} />
        )}
      </div>
      {/* Out of sight while a card is shown on the right, which it would
          be under. */}
      <Log
        entries={log}
        faded={showing?.kind === "play" || shown !== undefined}
      />
    </section>
  );
}

/**
 * What the player is to do now, in words, and the moves that are no card:
 * passing, or keeping the hand before round 1. While a card is chosen, a
 * button lets it go (as Escape does on the board).
 */
function Controls({ view, playing }: { view: View; playing: Playing }) {
  const names = cardNames(view);
  const chosen = playing.chosen;
  const name = chosen === null ? "" : (names.get(chosen.card) ?? chosen.card);
  let hint = "Choose a card to play, or pass.";
  if (view.reviving) {
    hint =
      chosen === null
        ? "Choose a unit to revive."
        : `Choose the row to revive ${name} in.`;
  } else if (
    view.legal_actions.some((action) => action.type === "end_redraw")
  ) {
    hint =
      chosen === null
        ? "Choose a card to swap, or keep this hand."
        : `Click ${name} again to swap it.`;
  } else if (
    chosen !== null &&
    selfPlay(playsOf(view.legal_actions, chosen.card)) !== undefined
  ) {
    // Weather, Clear Skies and Wildfire have nowhere to choose: clicking
    // the card again plays it.
    hint = `Click ${name} again to play it.`;
  } else if (chosen !== null) {
    hint = `Choose where to play ${name}, or click it again to put it back.`;
  }
  return (
    <div className="flex flex-col items-center gap-2">
      <p className="text-center text-sm text-gold-200">{hint}</p>
      <div
        role="group"
        aria-label="Moves"
        className="flex flex-wrap justify-center gap-2"
      >
        {chosen !== null && (
          <button
            type="button"
            className={BUTTON}
            aria-keyshortcuts="Escape"
            disabled={playing.disabled}
            onClick={() => {
              playing.onChoose(null);
            }}
          >
            Cancel
          </button>
        )}
        {otherActions(view.legal_actions).map((action) => (
          <button
            key={action.type}
            type="button"
            className={BUTTON}
            disabled={playing.disabled}
            onClick={onFirstClick(() => {
              playing.onPlay(action);
            })}
          >
            {actionText(action, names)}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * What happened in the match so far, the latest first: the sentences of
 * each move and of the AI's answer. Screen readers read what is added.
 */
function Log({ entries, faded }: { entries: Entry[]; faded: boolean }) {
  const id = useId();
  return (
    // On a wide screen, it fills the rest of the column beside the board,
    // and scrolls; its size doesn't count, so it never makes the page taller.
    // Faded, it only can't be seen: screen readers still read what is added.
    <section
      className={`mx-auto flex w-full max-w-3xl flex-col rounded-lg border border-wood-600 bg-wood-900/85 p-2 shadow-inner shadow-black/50 transition-opacity duration-300 lg:col-start-2 lg:row-start-3 lg:contain-size ${faded ? "opacity-0" : ""}`}
    >
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
        className="max-h-48 overflow-y-auto rounded-sm px-1 text-sm focus-visible:outline-2 focus-visible:outline-gold-300 lg:max-h-none lg:min-h-0 lg:flex-1"
      >
        {entries.length === 0 ? (
          <p className="italic opacity-70">Nothing yet.</p>
        ) : (
          <ol role="list" className="flex flex-col divide-y divide-gold-600/80">
            {entries.map((entry) => (
              <li key={entry.number} className="py-1">
                {entry.sentences.map((sentence, index) => (
                  // A move can make the same sentence twice, such as two
                  // copies of a unit mustered: the place is the key. How the
                  // round went stands out, as it is easy to miss over the
                  // board once the page is scrolled down to the moves.
                  <p
                    key={index}
                    className={
                      sentence === entry.round
                        ? "font-display text-gold-200"
                        : undefined
                    }
                  >
                    {sentence}
                  </p>
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
 * out of date: the move isn't legal now, or the match is at another version.
 */
function outOfDate(error: RequestError): boolean {
  return error.code === "illegal_action" || error.code === "match_changed";
}

/** The match of an answer, without what happened, as the cache keeps it. */
function matchOf(played: Played): Match {
  return { id: played.id, version: played.version, view: played.view };
}

/**
 * Return the id of the card at `target` (its face, or a button around it),
 * or null if it isn't one.
 */
function cardIn(target: EventTarget): string | null {
  if (!(target instanceof Element)) {
    return null;
  }
  const card =
    target.closest("[data-card]") ?? target.querySelector("[data-card]");
  return card?.getAttribute("data-card") ?? null;
}
