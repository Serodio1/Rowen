import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import type {
  Api,
  Card,
  Event,
  Level,
  Match,
  Move,
  NewMatch,
  Played,
  PlayerDeck,
  PlayerDecks,
  View,
} from "./api/client.ts";
import {
  decksQuery,
  forgetDecks,
  forgetMatches,
  matchQuery,
  playerDecksQuery,
  playMove,
  sessionQuery,
  startMatch,
  type RequestError,
} from "./api/requests.ts";
import { Board } from "./Board.tsx";
import { CardFace } from "./CardFace.tsx";
import { Banner, CardPreview, Showcase } from "./Showcase.tsx";
import {
  cardsById,
  mayMove,
  NO_STEPS,
  stageOf,
  stepsOfMoves,
  usePlayOut,
  viewAt,
  type Step,
} from "./stage.ts";
import { onFirstClick } from "./clicks.ts";
import { AccountBar, AccountDialog } from "./Account.tsx";
import { MyDecks } from "./Decks.tsx";
import { MyMatches } from "./Matches.tsx";
import { ALERT, BUTTON, PANEL } from "./styles.ts";
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
  cardText,
  eventText,
  happened,
  resultText,
  type Happened,
} from "./text.ts";

/**
 * The game's page: choose a deck to start a match against the AI, then play
 * it one move at a time, until it is over. A player who is logged in can
 * also see their matches, and play on one that isn't over.
 *
 * The requests go through TanStack Query, so the page needs a
 * `QueryClientProvider` around it, as in `main.tsx`.
 *
 * @param api - The client for the web API: the one `main.tsx` makes, or one
 *   with a fake `fetch` in tests.
 */
export function App({ api }: { api: Api }) {
  const queryClient = useQueryClient();
  // The match being played, as it started or as the player came back to it,
  // and the account it is played with (null for a guest), or null while
  // there is none.
  const [match, setMatch] = useState<{
    played: Played;
    owner: string | null;
  } | null>(null);
  // Whether the end of the match is shown, over the whole page: the top of
  // the page is out of reach meanwhile too.
  const [ended, setEnded] = useState(false);
  // What is shown in the decks' place while no match is played: the
  // player's matches, the decks they built, or neither.
  const [showing, setShowing] = useState<"matches" | "decks" | null>(null);
  // Whether the player left a match: the focus then goes to the decks.
  const [left, setLeft] = useState(false);
  // The level of the AI for the next match. It is kept here, so the player
  // finds it as they chose it when they play again.
  const [level, setLevel] = useState<Level>("normal");
  // Whether the dialog to log in is open: the rest of the page is out of
  // reach meanwhile (inert), and the focus goes back to the top once it
  // closes, since the button that opened it may be gone.
  const [loggingIn, setLoggingIn] = useState(false);
  // Who is logged in: a username, null for a guest, or undefined while the
  // page doesn't know yet.
  // From the last answer that came: a request that didn't work after it
  // leaves the page as it was, and doesn't make it forget who it was.
  const session = useQuery(sessionQuery(api));
  const username =
    session.data === undefined ? undefined : (session.data?.username ?? null);
  // Whether the page left a match because its account logged out, here or
  // in another tab: the decks then say why.
  const [loggedOut, setLoggedOut] = useState(false);
  const lastUsername = useRef(username);
  const owner = match?.owner;
  useEffect(() => {
    // Someone else is logged in now: the player logged out, here or in
    // another tab, or logged in with another account. Their matches are
    // theirs alone: the page forgets the list, and leaves the match if it
    // was played with the account that is gone (it is kept, to play on once
    // that account logs in again). A guest's match goes on.
    const before = lastUsername.current;
    lastUsername.current = username;
    if (before === undefined || username === undefined || before === username) {
      return;
    }
    forgetMatches(queryClient);
    forgetDecks(queryClient);
    setLoggedOut(before !== null && owner === before);
    if (before !== null) {
      setMatch((match) => (match?.owner === before ? null : match));
      setShowing(null);
      setLeft(true);
    }
  }, [username, queryClient, owner]);
  const top = useRef<HTMLDivElement>(null);
  const wasLoggingIn = useRef(false);
  useEffect(() => {
    if (wasLoggingIn.current && !loggingIn) {
      top.current?.querySelector("button")?.focus();
    }
    wasLoggingIn.current = loggingIn;
  }, [loggingIn]);

  return (
    <>
      <main
        className="mx-auto max-w-384 px-2 py-3 lg:px-4 lg:py-2"
        inert={loggingIn}
      >
        <div
          ref={top}
          className="mb-2 flex flex-col items-center gap-1 sm:grid sm:grid-cols-[1fr_auto_1fr] lg:mb-1"
          inert={ended}
        >
          <h1 className="text-center font-display sm:col-start-2 text-3xl font-bold tracking-wide text-gold-300 drop-shadow">
            Rowen
          </h1>
          <AccountBar
            api={api}
            onLogIn={() => {
              setLoggingIn(true);
            }}
            // Not during a match: the button would leave it without a word,
            // and a guest's match is in no list to come back to.
            onShowMatches={
              match === null && showing !== "matches"
                ? () => {
                    setShowing("matches");
                  }
                : undefined
            }
            onShowDecks={
              match === null && showing !== "decks"
                ? () => {
                    setShowing("decks");
                  }
                : undefined
            }
          />
        </div>
        {match === null ? (
          showing === "decks" ? (
            <MyDecks
              api={api}
              onBack={() => {
                setShowing(null);
                setLeft(true);
              }}
            />
          ) : showing === "matches" ? (
            <MyMatches
              api={api}
              onResume={(resumed) => {
                // It ended in another tab, and the list doesn't say so yet.
                if (resumed.view.match_over) {
                  forgetMatches(queryClient);
                }
                setLoggedOut(false);
                setMatch({
                  played: { ...resumed, moves: [] },
                  owner: username ?? null,
                });
                setShowing(null);
              }}
              onBack={() => {
                setShowing(null);
                setLeft(true);
              }}
            />
          ) : (
            <ChooseDeck
              api={api}
              onStart={(played) => {
                setLoggedOut(false);
                setMatch({ played, owner: username ?? null });
              }}
              focus={left}
              loggedOut={loggedOut}
              loggedIn={username !== undefined && username !== null}
              waiting={session.isPending}
              level={level}
              onLevel={setLevel}
            />
          )
        ) : (
          <PlayMatch
            // A new match is a new PlayMatch, with its own log.
            key={match.played.id}
            api={api}
            started={match.played}
            onEnded={setEnded}
            onLeave={() => {
              setMatch(null);
              setLeft(true);
            }}
          />
        )}
      </main>
      {loggingIn && (
        <AccountDialog
          api={api}
          onClose={() => {
            setLoggingIn(false);
          }}
        />
      )}
    </>
  );
}

/**
 * The decks the player can choose from: choosing one starts a match with it.
 * A player who is logged in can also choose one of the decks they built.
 *
 * @param onStart - Called with the match once it has started.
 * @param focus - Whether to put the focus on the heading, as when the player
 *   left a match: the button they pressed is gone.
 * @param loggedIn - Whether the player is logged in, and so has decks of
 *   their own.
 * @param loggedOut - Whether the page left a match because its account
 *   logged out: it says so.
 * @param level - The level of the AI the match starts with.
 * @param onLevel - Called with the level the player chooses.
 */
function ChooseDeck({
  api,
  onStart,
  focus,
  loggedIn,
  loggedOut,
  waiting,
  level,
  onLevel,
}: {
  api: Api;
  onStart: (match: Played) => void;
  focus: boolean;
  loggedIn: boolean;
  // Whether the page doesn't know yet who is logged in: a match started
  // then wouldn't know whose it is.
  waiting: boolean;
  loggedOut: boolean;
  level: Level;
  onLevel: (level: Level) => void;
}) {
  const queryClient = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focus) {
      heading.current?.focus();
    }
  }, [focus]);
  const decks = useQuery(decksQuery(api));
  // A guest has none: the API would turn them down.
  const playerDecks = useQuery({
    ...playerDecksQuery(api),
    enabled: loggedIn,
  });
  const start = useMutation({
    mutationKey: ["start"],
    mutationFn: (deck: NewMatch) => startMatch(api, deck),
    onSuccess: () => {
      // The match is in the player's list now.
      forgetMatches(queryClient);
    },
    onError: (error) => {
      // The deck is gone: the player deleted it in another tab. Ask for
      // their decks again, so its button goes too.
      if (error.code === "deck_not_found") {
        forgetDecks(queryClient);
      }
    },
  });
  // One match at a time: no second click while one starts.
  const startWith = (deck: NewMatch) =>
    onFirstClick(() => {
      // Two clicks in the same instant both come before the page shows the
      // buttons disabled.
      if (queryClient.isMutating({ mutationKey: ["start"] }) > 0) {
        return;
      }
      // Given here, and not to useMutation, so it isn't called once the
      // decks are gone, as when the player opened their matches meanwhile.
      start.mutate(deck, { onSuccess: onStart });
    });
  // The name of a faction's deck, from its id.
  const factionName = (id: string) =>
    decks.data?.find((deck) => deck.id === id)?.name ?? id;

  return (
    <section className={PANEL}>
      <h2
        ref={heading}
        tabIndex={-1}
        className="font-display text-2xl text-gold-300 outline-none"
      >
        Choose your deck
      </h2>
      {loggedOut && (
        <p role="status" className="italic">
          You were logged out, so the match was left: log in to play on.
        </p>
      )}
      {start.isError && (
        <p role="alert" className={ALERT}>
          {start.error.message}
        </p>
      )}
      <LevelChoice level={level} onLevel={onLevel} disabled={start.isPending} />
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
              disabled={start.isPending || waiting}
              onClick={startWith({ deck: deck.id, level })}
            >
              {deck.name}
            </button>
          ))}
        </div>
      )}
      {loggedIn && (
        <YourDecks
          decks={playerDecks}
          factionName={factionName}
          starting={start.isPending}
          onStart={(deck) => startWith({ my_deck: deck.id, level })}
        />
      )}
    </section>
  );
}

// The levels of the AI, from the weakest, with what the player sees of each.
const LEVELS: readonly { level: Level; name: string }[] = [
  { level: "easy", name: "Easy" },
  { level: "normal", name: "Normal" },
  { level: "hard", name: "Hard" },
];

/**
 * The level of the AI, chosen before the deck: a click on a deck starts the
 * match at once. A group of radio buttons, so the arrow keys move between
 * the levels and a screen reader says which one is chosen.
 *
 * @param level - The level chosen.
 * @param onLevel - Called with the level the player chooses.
 * @param disabled - Whether a match is starting: the level can't change
 *   meanwhile.
 */
function LevelChoice({
  level,
  onLevel,
  disabled,
}: {
  level: Level;
  onLevel: (level: Level) => void;
  disabled: boolean;
}) {
  const name = useId();
  const about = useId();
  return (
    <fieldset
      disabled={disabled}
      aria-describedby={about}
      className="flex flex-col items-center gap-2 disabled:opacity-50"
    >
      <legend className="mb-2 text-center font-display text-xl text-gold-300">
        AI level
      </legend>
      <div className="flex flex-wrap justify-center gap-2">
        {LEVELS.map((choice) => (
          <label
            key={choice.level}
            className="flex cursor-pointer items-center gap-2 rounded-md border border-gold-600 px-3 py-1.5 font-display text-gold-200 has-checked:bg-wood-600 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-gold-300"
          >
            <input
              type="radio"
              name={name}
              value={choice.level}
              checked={level === choice.level}
              onChange={() => {
                onLevel(choice.level);
              }}
              className="accent-gold-400"
            />
            {choice.name}
          </label>
        ))}
      </div>
      <p id={about} className="text-center text-sm opacity-80">
        Easy plays at once. Normal and Hard guess the cards you hold, and think
        a little longer.
      </p>
    </fieldset>
  );
}

/**
 * The decks the player built, in the decks' place: choosing one starts a
 * match with it.
 *
 * @param decks - The query for the player's decks.
 * @param factionName - Returns the name of a faction's deck from its id.
 * @param starting - Whether a match is starting: no second one meanwhile.
 * @param onStart - Returns what a click on the deck's button does.
 */
function YourDecks({
  decks,
  factionName,
  starting,
  onStart,
}: {
  decks: UseQueryResult<PlayerDecks>;
  factionName: (id: string) => string;
  starting: boolean;
  onStart: (deck: PlayerDeck) => ReturnType<typeof onFirstClick>;
}) {
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      className="flex flex-col items-center gap-3"
    >
      <h3 id={heading} className="font-display text-xl text-gold-300">
        Your decks
      </h3>
      {decks.isPending && <p className="italic">Loading your decks…</p>}
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
      {decks.isSuccess &&
        (decks.data.decks.length === 0 ? (
          <p className="italic">
            No deck of your own yet: build one in My decks.
          </p>
        ) : (
          <div className="flex flex-wrap justify-center gap-3">
            {decks.data.decks.map((deck) => (
              <button
                key={deck.id}
                type="button"
                className={`${BUTTON} max-w-full wrap-anywhere`}
                disabled={starting}
                onClick={onStart(deck)}
              >
                {deck.name} ({factionName(deck.deck)})
              </button>
            ))}
          </div>
        ))}
    </section>
  );
}

/** What happened after one request, numbered from 1 in the match. */
type Entry = Happened & { number: number };

/** The end of a round, as the API sends it. */
type RoundEnded = Extract<Event, { type: "round_ended" }>;

/** Return the events of the moves played, in order. */
function eventsOf(played: Played): Event[] {
  return played.moves.flatMap((move) => move.events);
}

/** Return the names of the cards in the views of the moves played, by id. */
function namesOf(played: Played): [string, string][] {
  return played.moves.flatMap((move) => [...cardNames(move.view)]);
}

/**
 * The match being played: the round, the board and the moves the player can
 * make, or who won once it is over, and what happened so far.
 *
 * @param started - The match as it started, with what the AI did if it
 *   started, or as the player came back to it, with no moves.
 * @param onEnded - Called with whether the end of the match is shown over
 *   the whole page.
 * @param onLeave - Called when the player is done with the match.
 */
function PlayMatch({
  api,
  started,
  onEnded,
  onLeave,
}: {
  api: Api;
  started: Played;
  onEnded: (ended: boolean) => void;
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
    started.moves.length === 0
      ? []
      : [
          {
            number: 1,
            ...happened(
              eventsOf(started),
              started.view.player,
              new Map(namesOf(started)),
              // The AI's first moves are in the first round.
              1,
            ),
          },
        ],
  );
  // The animation of the last move, or of the AI's first one: none with
  // reduced motion.
  const [steps, setSteps] = useState<readonly Step[]>(() =>
    mayMove() ? stepsOfMoves(started.moves, undefined) : NO_STEPS,
  );
  const progress = usePlayOut(steps);
  const showing = steps[progress.step];
  // The card pointed at or focused, by id, to show it large, with its
  // strength on the board.
  const [pointed, setPointed] = useState<Pointed | null>(null);
  /** Point at a card, or at none: the same card is no change. */
  function point(next: Pointed | null) {
    setPointed((last) =>
      last?.id === next?.id && last?.strength === next?.strength ? last : next,
    );
  }
  // The player whose discard pile is listed, if one is.
  const [pile, setPile] = useState<number | null>(null);
  // The pile's button that listed it: the focus goes back to it on Close.
  const pileButton = useRef<HTMLElement | null>(null);
  // Whether the player is using the keyboard: the page moves the focus by
  // itself after each move, which must not show a card then.
  const typing = useRef(false);
  // Whether the page is moving the focus by itself, which must not show a
  // card either, even while the player uses the keyboard.
  const focusing = useRef(false);
  // The button to ask for the match again, when the page couldn't.
  const tryAgain = useRef<HTMLButtonElement>(null);
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
        ...namesOf(played),
      ]);
      const entry = happened(
        eventsOf(played),
        played.view.player,
        names,
        before?.round ?? played.view.round,
      );
      setLog((log) => [{ number: log.length + 1, ...entry }, ...log]);
      setSteps(mayMove() ? stepsOfMoves(played.moves, before) : NO_STEPS);
      queryClient.setQueryData(query.queryKey, matchOf(played));
      if (played.view.match_over) {
        // How it ended is in the player's list now.
        forgetMatches(queryClient);
      }
    },
    onError: (error) => {
      // Ask for the match as it is now, unless it is gone. When no answer
      // came, or the server failed, the move may have been played all the
      // same, and the view on the page is then out of date: a move chosen
      // from it would be turned down.
      if (error.code !== "match_not_found") {
        void queryClient.invalidateQueries({ queryKey: query.queryKey });
      }
      // The card chosen may not be the player's to play any more.
      setChosen(null);
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
      focusing.current = true;
      (
        boardArea.current?.querySelector<HTMLElement>(
          "[data-choosable]:not(:disabled)",
        ) ??
        movesArea.current?.querySelector<HTMLElement>("button:not(:disabled)")
      )?.focus();
      focusing.current = false;
    }
  }, [version, ready]);
  // Whether the end of the match is shown (see `over` below), for the rest
  // of the page, which is then out of reach too.
  const ended = match.data.view.match_over && progress.step >= steps.length;
  useEffect(() => {
    onEnded(ended);
    return () => {
      onEnded(false);
    };
  }, [ended, onEnded]);
  const failed = match.isError;
  useEffect(() => {
    // The moves are disabled: the focus goes to what the player can do.
    if (failed) {
      tryAgain.current?.focus();
    }
  }, [failed]);
  const notFound =
    play.error?.code === "match_not_found" ||
    match.error?.code === "match_not_found";
  const notFoundHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!notFound) {
      return;
    }
    // The moves are gone, with the focus.
    notFoundHeading.current?.focus();
    // The match may be gone because the player logged out in another tab:
    // the API gives another account's match, or a guest, a 404. Asking who
    // is logged in then leaves the match (see App), and says why.
    void queryClient.invalidateQueries({
      queryKey: sessionQuery(api).queryKey,
    });
  }, [notFound, queryClient, api]);

  if (notFound) {
    // The server doesn't know the match: it was kept in the memory of a
    // server that restarted, or the link is wrong.
    return (
      <section className={PANEL}>
        <h2
          ref={notFoundHeading}
          tabIndex={-1}
          className="font-display text-2xl text-gold-300 outline-none"
        >
          Match not found
        </h2>
        <p role="alert" className={ALERT}>
          The server has no such match, or it is another account&apos;s.
        </p>
        <button type="button" className={BUTTON} onClick={onLeave}>
          Start a new match
        </button>
      </section>
    );
  }

  const view = match.data.view;
  // While moves play out, the board shows the match as it was then: its
  // round and both sides. The hand and the moves the player can make are
  // those of the match as it is, as moves never wait for the animation.
  const then = viewAt(steps, progress);
  const board =
    then === undefined
      ? view
      : { ...view, round: then.round, players: then.players };
  const shown =
    pointed === null ? undefined : cardsById([board, view]).get(pointed.id);
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
  // How the last round went, until the next move; while the round that ended
  // in the last moves is still on the board, the one before. In a match the
  // player came back to, before their first move, the last round that ended
  // in it, if one did.
  const lastRound = match.data.rounds.at(-1);
  const round =
    log.length === 0
      ? lastRound === undefined
        ? null
        : eventText(lastRound, view.player, new Map(), match.data.rounds.length)
      : ((board.round === view.round ? log[0]?.round : log[1]?.round) ?? null);
  // Once the match is over and its last move played out, the end of the
  // match is over the whole page: the rest is out of reach meanwhile, for the
  // keyboard too.
  const over = ended;
  // On a wide screen, the board is on the left, and on its right the round,
  // how the last one went, what to do and what happened, so it all fits on
  // one screen. On a narrow one, they are in that order, with the board
  // after how the last round went.
  return (
    <section className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_17rem] lg:grid-rows-[auto_auto_minmax(0,1fr)]">
      <div className="flex flex-col gap-2 lg:col-start-2" inert={over}>
        <h2 className="text-center font-display text-xl text-gold-300 lg:text-2xl">
          Round {board.round}
        </h2>
        {match.isError ? (
          // The page couldn't ask for the match after a move that didn't
          // work, so its view may be out of date: no move until it can.
          <div className="flex flex-wrap items-center justify-center gap-2">
            <p role="alert" className={ALERT}>
              {match.error.message}
            </p>
            <button
              ref={tryAgain}
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
        inert={over}
        // Any card on the board or in the hand, pointed at or focused, shows
        // large on the right, with what it does.
        onMouseOver={(event) => {
          point(cardIn(event.target));
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
          if (typing.current && !focusing.current) {
            point(cardIn(event.target));
          }
        }}
        onBlur={() => {
          setPointed(null);
        }}
      >
        <Board
          view={board}
          playing={view.match_over ? undefined : playing}
          stage={stageOf(steps, progress)}
          onPile={(side) => {
            pileButton.current =
              document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
            setPile(side);
          }}
        />
        {showing?.kind === "announce" && <Banner text={showing.text} />}
        {showing?.kind === "play" ? (
          // A new element for each card, which comes up from nothing.
          <Showcase
            key={progress.step}
            step={showing}
            flying={progress.flying}
          />
        ) : (
          // A card played comes first.
          shown !== undefined && (
            <CardPreview card={shown} strength={pointed?.strength} />
          )
        )}
      </div>
      <div ref={movesArea} className="lg:col-start-2 lg:row-start-2">
        {view.match_over ? (
          over && (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby={resultId}
              className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
            >
              <div className="wood flex w-full max-w-md flex-col items-center gap-4 rounded-xl border-2 border-gold-400 p-6 shadow-2xl shadow-black">
                <h2
                  id={resultId}
                  className="text-center font-display text-3xl text-gold-200"
                >
                  {resultText(view)}
                </h2>
                <Rounds rounds={match.data.rounds} viewer={view.player} />
                <button
                  type="button"
                  className={BUTTON}
                  // The moves are gone: the focus goes on from here, and
                  // screen readers read who won with it.
                  autoFocus
                  aria-describedby={resultId}
                  // The second click of a double click on the last move
                  // could land here, and skip who won.
                  onClick={onFirstClick(onLeave)}
                >
                  Play again
                </button>
              </div>
            </div>
          )
        ) : (
          <Controls view={view} playing={playing} />
        )}
      </div>
      {/* Out of sight while a card is shown on the right, which it would
          be under. */}
      {/* What happened, and above it the discard pile listed, if one is. */}
      <div
        className="flex flex-col gap-2 lg:col-start-2 lg:row-start-3 lg:contain-size"
        inert={over}
      >
        {pile !== null && (
          <DiscardPile
            cards={board.players[pile]?.discard ?? []}
            name={
              pile === view.player
                ? "Your discard pile"
                : "The AI's discard pile"
            }
            onClose={() => {
              setPile(null);
              pileButton.current?.focus();
            }}
          />
        )}
        <Log
          entries={log}
          faded={showing?.kind === "play" || shown !== undefined}
        />
      </div>
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
        : `Choose ${name} again to swap it.`;
  } else if (
    chosen !== null &&
    selfPlay(playsOf(view.legal_actions, chosen.card)) !== undefined
  ) {
    // Weather, Clear Skies and Wildfire have nowhere to choose: choosing
    // the card again, with a click or the keyboard, plays it.
    hint = `Choose ${name} again to play it.`;
  } else if (chosen !== null) {
    // A Scarecrow goes in the place of a unit, which it takes back.
    const scarecrow = view.hand.some(
      (card) =>
        card.id === chosen.card &&
        card.type === "special" &&
        card.kind === "scarecrow",
    );
    hint = scarecrow
      ? `Choose a unit to take back with ${name}, or choose ${name} again to put it back.`
      : `Choose where to play ${name}, or choose it again to put it back.`;
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
  const logId = useId();
  // Out of sight until the player asks for it: the cards and the big
  // messages show what happens. Screen readers read it all the same.
  const [open, setOpen] = useState(false);
  return (
    // On a wide screen, it fills the rest of the column beside the board,
    // and scrolls; its size doesn't count, so it never makes the page taller.
    // Faded, it only can't be seen: screen readers still read what is added.
    <section
      className={`mx-auto flex w-full max-w-3xl flex-col rounded-lg p-2 transition-opacity duration-300 lg:min-h-0 lg:flex-1 ${
        open
          ? "border border-wood-600 bg-wood-900/85 shadow-inner shadow-black/50"
          : ""
      } ${faded ? "opacity-0" : ""}`}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3
          id={id}
          className="font-display text-xs tracking-widest text-gold-300/80 uppercase"
        >
          What happened
        </h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={logId}
          className="rounded border border-gold-600 px-2 py-0.5 font-display text-xs text-gold-200 hover:bg-wood-700 focus-visible:outline-2 focus-visible:outline-gold-300"
          onClick={() => {
            setOpen((open) => !open);
          }}
        >
          {open ? "Hide log" : "Show log"}
        </button>
      </div>
      {/* A log: screen readers read what is added to it, but not what was
          there already. Open, it scrolls, so the keyboard can reach it too. */}
      <div
        id={logId}
        role="log"
        aria-labelledby={id}
        tabIndex={open ? 0 : undefined}
        className={
          open
            ? "max-h-48 overflow-y-auto rounded-sm px-1 text-sm focus-visible:outline-2 focus-visible:outline-gold-300 lg:max-h-none lg:min-h-0 lg:flex-1"
            : "sr-only"
        }
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
  return {
    id: played.id,
    version: played.version,
    view: played.view,
    rounds: played.rounds,
  };
}

/**
 * Return the id of the card at `target` (its face, or a button around it),
 * or null if it isn't one.
 *
 * Only a button may hold the card: any other element around cards, such as
 * a row or a pile, isn't one of them.
 */
function cardIn(target: EventTarget): Pointed | null {
  if (!(target instanceof Element)) {
    return null;
  }
  const card =
    target.closest("[data-card]") ??
    (target instanceof HTMLButtonElement
      ? target.querySelector("[data-card]")
      : null);
  const id = card?.getAttribute("data-card");
  if (id === undefined || id === null) {
    return null;
  }
  const strength = card?.getAttribute("data-strength");
  return {
    id,
    strength:
      strength === undefined || strength === null
        ? undefined
        : Number(strength),
  };
}

/** A card pointed at: its id, and its strength on the board, if it has one. */
interface Pointed {
  id: string;
  strength: number | undefined;
}

/**
 * How each round went, in a table: the player's score, the AI's and who
 * won it.
 *
 * @param viewer - The player of the view: 0 or 1.
 */
function Rounds({
  rounds,
  viewer,
}: {
  rounds: readonly RoundEnded[];
  viewer: number;
}) {
  return (
    <table className="w-full text-center">
      <caption className="sr-only">The rounds</caption>
      <thead className="font-display text-sm text-gold-300">
        <tr>
          <th scope="col">Round</th>
          <th scope="col">You</th>
          <th scope="col">The AI</th>
          <th scope="col">Won by</th>
        </tr>
      </thead>
      <tbody>
        {rounds.map((round, index) => (
          <tr key={index} className="border-t border-gold-600/60">
            <th scope="row" className="py-1 font-normal">
              {index + 1}
            </th>
            <td>{round.scores[viewer]}</td>
            <td>{round.scores[1 - viewer]}</td>
            <td>
              {round.winner === null
                ? "Tie"
                : round.winner === viewer
                  ? "You"
                  : "The AI"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * The cards in a discard pile, the most recent first, beside the board.
 * Close or Escape puts it away; it takes the focus when it opens, so the
 * keyboard can go through it.
 */
function DiscardPile({
  cards,
  name,
  onClose,
}: {
  cards: readonly Card[];
  name: string;
  onClose: () => void;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onClose();
        }
      }}
      className="mx-auto flex max-h-96 w-full max-w-3xl flex-col gap-2 rounded-lg border border-gold-600 bg-wood-900/95 p-2 shadow-lg shadow-black/60 lg:max-h-none lg:min-h-0 lg:flex-2"
    >
      <div className="flex items-center justify-between gap-2">
        <h3
          id={id}
          className="font-display text-xs tracking-widest text-gold-300 uppercase"
        >
          {name}
        </h3>
        <button
          type="button"
          // Opened by a click on the pile: the keyboard goes on from here.
          autoFocus
          aria-keyshortcuts="Escape"
          className="rounded border border-gold-600 px-2 py-0.5 font-display text-xs text-gold-200 hover:bg-wood-700 focus-visible:outline-2 focus-visible:outline-gold-300"
          onClick={onClose}
        >
          Close
        </button>
      </div>
      {cards.length === 0 ? (
        <p className="text-sm italic opacity-70">No cards yet.</p>
      ) : (
        <ul
          role="list"
          className="flex min-h-0 flex-wrap content-start gap-1 overflow-y-auto"
        >
          {[...cards].reverse().map((card, index) => (
            // Copies of a card share its id: the place in the pile is the key.
            <li key={index}>
              <CardFace card={card} name={cardText(card)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
