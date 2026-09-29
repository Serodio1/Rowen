# ADR 0002: Run the game on the server

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

Rowen has hidden information ([rules, section 11](../rules.md#11-information)):
a player must not see the cards in the opponent's hand, and nobody may see the
order of the cards in a deck. Anything that is sent to the browser can be read
with the developer tools, and any request can be forged, so the client cannot
be trusted with the full game state or with deciding what is legal.

The AI opponent also needs the full game state to play, and the rules should
exist in exactly one place: two implementations (for example Python on the
server and TypeScript in the browser) would drift apart over time.

## Decision

The server is the single source of truth for every match (server-authoritative):

- The game state lives only on the server, and the engine runs only there.
- The client sends **intents** such as "play card X on row Y" or "pass". The
  server accepts an intent only if it is one of the player's legal actions in
  the current state, applies it and saves the result.
- The server answers with a **player view**: a projection of the state that
  contains only what that player may see (the board, both discard piles, their
  own hand, and the *number* of cards in the opponent's hand and in each deck),
  plus the player's legal actions and the events produced by the last action.
- Producing the player view is an engine function. What each player may see is
  part of the rules, so it is tested together with them.
- The frontend contains no game rules. It renders the view, offers only the
  actions the server listed as legal and animates the events it receives.

## Alternatives considered

- **Engine in the client, server stores the results.** Simple and fast, but
  the full state (including the opponent's hand) would be in the browser, and a
  player could submit any result they like.
- **Engine on both sides** (a TypeScript copy, or Python in the browser with
  Pyodide) for instant feedback. The server would still have to validate every
  move, so this means either two implementations to keep in sync or a large
  download, only to save a round trip in a turn-based game.

## Consequences

- Hidden information stays hidden, and editing the client cannot bend the
  rules. This needs tests at two levels: the engine's player view, and the API
  responses, which must never contain the opponent's hand.
- Every move needs a request to the server, so the frontend has to show a
  pending state while it waits.
- The server has to store matches between requests (PostgreSQL, Phase 2).
- The AI runs on the server next to the engine and uses the same engine API as
  a human player.
- Player versus player (planned after `v1.0.0`) does not need a redesign: the
  second player becomes a human instead of the AI, and the server pushes
  updates to both clients.
