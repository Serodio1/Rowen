import { useEffect, useState } from "react";
import type { Api, Deck, View } from "./api/client.ts";
import { actionText, cardNames, cardText } from "./text.ts";

// What the page says when no answer came, or none from the API: the network
// is down, the API isn't running, or a proxy answered in its place.
const UNREACHABLE = "Could not reach the server.";

/**
 * The game's page: choose a deck to start a match against the AI, then see
 * the round, the cards in hand and the moves that can be made.
 *
 * @param api - The client for the web API: the one `main.tsx` makes, or one
 *   with a fake `fetch` in tests.
 */
export function App({ api }: { api: Api }) {
  const [decks, setDecks] = useState<Deck[] | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    // React may run this again, and does in development to catch mistakes:
    // only the answer to the latest run is kept.
    let latest = true;
    api.GET("/decks").then(
      ({ data, error }) => {
        if (!latest) {
          return;
        }
        if (data) {
          setDecks(data.decks);
        } else {
          setError(failure(error));
        }
      },
      () => {
        if (latest) {
          setError(UNREACHABLE);
        }
      },
    );
    return () => {
      latest = false;
    };
  }, [api]);

  async function start(deck: string) {
    setStarting(true);
    setError(null);
    try {
      const { data, error } = await api.POST("/matches", { body: { deck } });
      if (data) {
        setView(data.view);
      } else {
        setError(failure(error));
      }
    } catch {
      setError(UNREACHABLE);
    } finally {
      setStarting(false);
    }
  }

  return (
    <main>
      <h1>Rowen</h1>
      {error !== null && <p role="alert">{error}</p>}
      {view !== null ? (
        <Match view={view} />
      ) : (
        <section>
          <h2>Choose your deck</h2>
          {decks === null
            ? error === null && <p>Loading the decks…</p>
            : decks.map((deck) => (
                <button
                  key={deck.id}
                  type="button"
                  // One match at a time: no second click while one starts.
                  disabled={starting}
                  onClick={() => {
                    void start(deck.id);
                  }}
                >
                  {deck.name}
                </button>
              ))}
        </section>
      )}
    </main>
  );
}

/** The match as text: the round, the cards in hand and the legal actions. */
function Match({ view }: { view: View }) {
  const names = cardNames(view);
  return (
    <section>
      <h2>Round {view.round}</h2>
      <h3>Your hand</h3>
      <ul>
        {view.hand.map((card, index) => (
          // Copies of a card share its id, so the place in the hand is the key.
          <li key={index}>{cardText(card)}</li>
        ))}
      </ul>
      <h3>What you can do</h3>
      <ul>
        {view.legal_actions.map((action, index) => (
          <li key={index}>{actionText(action, names)}</li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Return what to show when the API turned a request down: its message, if it
 * sent one. An answer without one didn't come from the API.
 */
function failure(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return error.message;
  }
  return UNREACHABLE;
}
