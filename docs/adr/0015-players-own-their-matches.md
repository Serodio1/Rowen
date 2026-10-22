# ADR 0015: Give a logged-in player's matches an owner, keep their results and list them by cursor

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Phase 4 lets a player who is logged in see their past matches, resume one
that isn't over, and see how often they won with each deck ([plan](../plan.md),
issue #109). Until now a match was anybody's who had its id
([ADR 0013](0013-keep-matches-in-postgresql.md)), and the store kept only what
it takes to play it again: the decks, the seed and the actions. Three things
had to be chosen: who may see a match, what is kept about how it ended, and
how the list comes a page at a time.

What matters: guests must still play as before; the API must not say whether
an id belongs to somebody else's match; the database is Neon's free tier,
small and asleep when idle, so a query should read only what it needs.

## Decision

- **A match started while logged in has the account as its owner**
  (`matches.account_id`, a foreign key). Only the owner may see it or play
  it. To anybody else, the answer is the same `404 match_not_found` as for an
  id that doesn't exist, so it doesn't confirm that the id is right (a `403`
  would). A guest's match has no owner and is anybody's who has its id.
  Deleting an account leaves its matches with no owner (`ON DELETE SET NULL`).
- **The result is kept when the match ends**, in three columns that are
  empty until then: `outcome` (`won`, `lost` or `drawn`, for the player),
  `rounds` (each round's totals, as JSON) and `ended_at`. The API works it out
  when an action ends the match and writes it in the same `UPDATE` as the
  actions. Two CHECK constraints keep an outcome known and a result whole.
- **Stats are counted by the database** (`GROUP BY` the player's deck, and
  `COUNT(*) FILTER (WHERE outcome = ...)` for each outcome) from those
  columns, never by playing matches again.
- **The list comes 20 at a time, newest first, by cursor:** the next page is
  `GET /matches?before=<id of the last match of this page>`, the matches
  whose `(created_at, id)` comes before that one's. An index on
  `(account_id, created_at, id)` gives them in order. The answer says whether
  there are `more`.

## Alternatives considered

- **`403 Forbidden` for somebody else's match.** Truer to HTTP, but it tells
  whoever tries ids which ones exist. The 404 tells nothing.
- **Working results out when asked**, by playing each match again. Nothing
  more to keep, but the list and the stats would play every match of the
  player on each request: about 1.5 ms each, so most of a second for 500.
- **Pages by `OFFSET`** (`?page=3`). Simpler, but the database reads and
  skips every match of the pages before, and a match started meanwhile moves
  every page along by one, so a match shows twice or never.
- **A table of results of its own.** Cleaner if a match had many results;
  it has one, so three columns of `matches` are enough.

## Consequences

- A player who logs out can't reach their own matches until they log in
  again, even with the id. A guest who logs in doesn't get the matches they
  played as a guest.
- The matches kept before this change have no owner and no result; they were
  all a guest's.
- In the store in memory (development only), a player's matches are pushed
  out with the others once there are 1,000.
- The result is only as right as the code that writes it: the API's tests
  play whole matches and check it against the events the player was sent.
