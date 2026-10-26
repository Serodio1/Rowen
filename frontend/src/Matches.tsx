import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useId, useRef } from "react";
import type { Api, Match, MatchSummary } from "./api/client.ts";
import {
  decksQuery,
  matchesQuery,
  matchQuery,
  statsQuery,
} from "./api/requests.ts";
import { onFirstClick } from "./clicks.ts";
import { ALERT, BUTTON } from "./styles.ts";

const PANEL =
  "wood mx-auto flex max-w-xl flex-col items-center gap-4 rounded-xl border-2 border-wood-600 p-6 shadow-2xl shadow-black/60";

/**
 * The matches of the player who is logged in: how many they won, lost and
 * drew with each deck, and then the matches, the newest first, a page at a
 * time. A match that isn't over can be played on.
 *
 * It takes the focus when it opens: the button that opened it is gone.
 *
 * @param onResume - Called with a match the player chose to play on, once
 *   the page has it as it is now.
 * @param onBack - Called when the player is done with the list.
 */
export function MyMatches({
  api,
  onResume,
  onBack,
}: {
  api: Api;
  onResume: (match: Match) => void;
  onBack: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  const queryClient = useQueryClient();
  // The decks' names: the list has their ids.
  const decks = useQuery(decksQuery(api));
  const names = new Map(decks.data?.map((deck) => [deck.id, deck.name]));
  const name = (deck: string) => names.get(deck) ?? deck;
  const stats = useQuery(statsQuery(api));
  const matches = useInfiniteQuery(matchesQuery(api));
  const resume = useMutation({
    mutationKey: ["resume"],
    // Asked for again, even if the cache has it: it may have been played on
    // in another tab since.
    mutationFn: (id: string) =>
      queryClient.query({ ...matchQuery(api, id), staleTime: 0 }),
    onSuccess: onResume,
  });

  return (
    <section className={PANEL}>
      <h2
        ref={heading}
        tabIndex={-1}
        className="font-display text-2xl text-gold-300 outline-none"
      >
        My matches
      </h2>
      {stats.isError && (
        <p role="alert" className={ALERT}>
          {stats.error.message}
        </p>
      )}
      {stats.isSuccess &&
        (stats.data.length === 0 ? (
          <p className="italic">No match finished yet.</p>
        ) : (
          <table className="w-full text-center">
            <caption className="sr-only">Matches won, lost and drawn</caption>
            <thead className="font-display text-sm text-gold-300">
              <tr>
                <th scope="col">Deck</th>
                <th scope="col">Won</th>
                <th scope="col">Lost</th>
                <th scope="col">Drawn</th>
              </tr>
            </thead>
            <tbody>
              {stats.data.map((deck) => (
                <tr key={deck.deck} className="border-t border-gold-600/60">
                  <th scope="row" className="py-1 font-normal">
                    {name(deck.deck)}
                  </th>
                  <td>{deck.won}</td>
                  <td>{deck.lost}</td>
                  <td>{deck.drawn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      {resume.isError && (
        <p role="alert" className={ALERT}>
          {resume.error.message}
        </p>
      )}
      {matches.isPending && <p className="italic">Loading your matches…</p>}
      {matches.isError && (
        <>
          <p role="alert" className={ALERT}>
            {matches.error.message}
          </p>
          {!matches.isFetchNextPageError && (
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                void matches.refetch();
              }}
            >
              Try again
            </button>
          )}
        </>
      )}
      {/* Not only on success: when the next page didn't come, the pages
          that came are still there. */}
      {matches.data !== undefined &&
        (matches.data.pages[0]?.matches.length === 0 ? (
          <p className="italic">No match yet: choose a deck to play one.</p>
        ) : (
          <ol className="flex w-full flex-col gap-2">
            {matches.data.pages
              .flatMap((page) => page.matches)
              .map((match) => (
                <Summary
                  key={match.id}
                  match={match}
                  name={name}
                  resuming={resume.isPending}
                  onResume={() => {
                    // Two clicks in the same instant both come before the
                    // page shows the buttons disabled.
                    if (
                      queryClient.isMutating({ mutationKey: ["resume"] }) > 0
                    ) {
                      return;
                    }
                    resume.mutate(match.id);
                  }}
                />
              ))}
          </ol>
        ))}
      {matches.hasNextPage && (
        <button
          type="button"
          className={BUTTON}
          disabled={matches.isFetchingNextPage}
          onClick={() => {
            void matches.fetchNextPage();
          }}
        >
          Show more
        </button>
      )}
      <button type="button" className={BUTTON} onClick={onBack}>
        Back
      </button>
    </section>
  );
}

/**
 * One match in the list: the decks, when it started, and how it ended, or a
 * button to play on.
 *
 * @param name - Returns a deck's name from its id.
 * @param resuming - Whether a match is being asked for, to play on: no
 *   second one meanwhile.
 */
function Summary({
  match,
  name,
  resuming,
  onResume,
}: {
  match: MatchSummary;
  name: (deck: string) => string;
  resuming: boolean;
  onResume: () => void;
}) {
  const id = useId();
  const result = match.result;
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-gold-600/60 px-3 py-2">
      <div id={id}>
        <p>
          <strong className="text-gold-200">{name(match.deck)}</strong> against{" "}
          {name(match.ai_deck)}
        </p>
        <p className="text-sm opacity-80">
          <time dateTime={match.started_at}>{when(match.started_at)}</time>
        </p>
        {result === null ? (
          <p>Not over yet.</p>
        ) : (
          <p>
            <strong className="text-gold-200">
              {OUTCOMES[result.outcome]}
            </strong>
            {": "}
            {result.rounds
              .map((round) => `${String(round.player)} to ${String(round.ai)}`)
              .join(", ")}
          </p>
        )}
      </div>
      {result === null && (
        <button
          type="button"
          className={BUTTON}
          // Which match: the button's name alone is the same for each.
          aria-describedby={id}
          disabled={resuming}
          onClick={onFirstClick(onResume)}
        >
          Resume
        </button>
      )}
    </li>
  );
}

const OUTCOMES = { won: "Won", lost: "Lost", drawn: "Drawn" } as const;

/** Return when a match started, as the player's browser writes dates. */
function when(time: string): string {
  return new Date(time).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
