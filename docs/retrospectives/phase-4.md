# Phase 4 retrospective: accounts and persistence

Phase 4 ends with the release `v0.4.0`. It ran from 22 to 27 October 2026, in
20 pull requests (#113 to #132). At the end of it, a player may still play at
once as a guest, or make an account: then their matches are kept for them,
listed and counted, an unfinished one can be resumed, and they can build decks
of their own and play with them. This document looks back at what was built,
which decisions shaped it and why, and what to change next.

## What was built

| Part | What it does |
|---|---|
| Accounts | Making an account, logging in and out, on the page and through the API. Passwords are hashed with Argon2id; a session is a row in PostgreSQL and a cookie (#113, #114). |
| My matches | A logged-in player's matches, newest first, 20 at a time, with how each one ended. "Resume" plays on one that isn't over (#115, #116). |
| Statistics | How many matches a player won, lost and drew with each deck (#115). |
| My decks | Building a deck from a faction's cards, within the engine's rules (at least 22 units, at most 10 special cards, up to 3 copies of a card); changing it, deleting it, and playing with it. Up to 10 decks a player (#122 to #126). |
| Safer deployments | Each new version starts beside the one that answers now, is checked at an address of its own, and only then gets the requests. If the check fails, the requests never move (#121, #128). |
| Logged out elsewhere | Logging out in one tab is noticed in the others, even in the middle of a match (#119, #131). |

## Decisions and why

Four new ADRs:

- **Sessions in PostgreSQL, not tokens the browser keeps** ([ADR 0014](../adr/0014-accounts-with-sessions-in-postgresql.md)).
  Logging out deletes the session's row, so it really ends; a signed token
  would stay valid until it expires. The table keeps only a hash of each
  session's token, so a copy of the database logs nobody in. The cookie is
  `__Host-session`, `HttpOnly`, `Secure` and `SameSite=Lax`, and the API turns
  down a request that changes something and comes from another site
  (`Origin`). Logging in with a wrong username takes as long as with a wrong
  password, so the time of the answer doesn't tell which usernames exist.
- **A match belongs to the player who started it** ([ADR 0015](../adr/0015-players-own-their-matches.md)).
  Another player asking for it gets "not found", not "forbidden", so the
  answer doesn't say that it exists. Each match keeps how it ended, so the
  statistics are one query, not every match played again. The list goes page
  by page from the last match seen (a cursor), not by counting rows to skip.
- **A new version is checked before it gets the requests** ([ADR 0016](../adr/0016-check-a-revision-before-it-gets-the-requests.md)).
  The images it is built from are fixed by their digest, not by a name that
  can move. The database migrations only add, so the old version keeps working
  while the new one starts.
- **A match keeps a copy of the deck it was played with** ([ADR 0017](../adr/0017-keep-a-copy-of-a-built-deck-in-each-match.md)).
  Matches are kept as their seed and moves (ADR 0013) and played again when
  they are asked for, so they need the deck as it was. With a copy, changing
  or deleting a deck later changes no match. The AI plays the other faction's
  own deck.

And some smaller ones, in the pull requests:

- **Guests stay.** Nothing needs an account to play; it only keeps the
  matches and decks.
- **The engine checks a built deck.** The page only shows what the API sends
  (`GET /decks/{id}/choices`), so a deck's rules are written once, in Python.
- **Passwords are put in one Unicode form (NFKC) before they are hashed,** as
  NIST advises, so the same password typed on two keyboards is the same.
- **Two decks built at once by a player with 9 can't make 11:** the account's
  row is locked while the decks are counted.

## Testing

- **892 backend tests,** covering 100% of statements and branches, as in the
  phases before. The tests of the PostgreSQL stores run in CI against a real
  PostgreSQL; they caught a JSON `null` kept where the database needed an SQL
  `NULL` (#124).
- **293 frontend tests,** with Vitest and Testing Library.
- **Five Playwright tests in CI,** against the Docker images, through nginx: a
  whole match, the layout on a laptop and a phone, an account, a player's
  matches, and a deck built, played and deleted.
- **Mutation testing by hand,** on every pull request.
- **Two reviews with AI agents.** One in the middle of the phase (26 October),
  asked for because the pull requests in between were not reviewed by agents,
  was fixed in #119 to #121. The one before the release (27 October) had three
  reviewers, a sceptic checking each one, and two tester agents playing in
  Chromium as a guest and with an account. It found nothing blocking. Two
  medium findings (going back to the version before a migration, and the focus
  falling to the page's body in the deck editor and the lists) and the low ones were fixed in #128 to #132;
  the smallest ones wait in #133. The testers played 13 matches with every
  kind of card, and the page always said what the server sent. The agents
  also checked the database role's permissions, the races, the cookie, the
  login times, and the page's accessibility (no axe violations, contrast of
  at least 7:1).

## What went well

- **The engine barely changed.** Accounts, owners and history live in the API
  and the database; the engine only gained the rules of a built deck.
- **Keeping matches as seed and moves paid off again.** A match's rounds, its
  result and a resumed match all come from playing the moves again.
- **Deployments became safe to get wrong.** The check before the traffic
  worked the first time, and a failed new version never answers a player.
- **Generated types again.** Each change to the API showed in the page's type
  checker every place to change.
- **Reviews found real problems before players did,** and every one of them
  came with a way to reproduce it.

## What could be better

- **`main` went red three times after a merge, each time because of a new
  browser test:** a test that counted the log before the board was there
  (#117), tests in parallel that went over nginx's limit for one address
  (#118), and tests faster than nginx's limit per second (#127). All three
  passed before the merge by chance, or were not run through nginx.
- **The pull requests in the middle were not reviewed by agents,** to save
  time, and problems passed. The review in the middle of the phase found
  them; next time, a smaller review may be worth it earlier.
- **A test proved less than it said** (#132): it reloaded a match before any
  round had ended, so it passed with or without the code it tested. A mutation
  that the old test let through showed it.
- **Some numbers were stated before they were measured,** such as the
  coverage of a pull request run without `--cov` (#123), and a limit nginx
  doesn't accept (caught by `nginx -t`).
- **Not tried with everything production uses.** nginx 1.30 (only 1.24 here),
  the real Cloud Run tags and the database's timings in Neon were not tested
  before the release; nor a real screen reader.
- **The statistics take 30 to 48 ms with about 40 000 matches;** an index
  made for them would be faster (#133).

## Next

- **Phase 5:** the rest of the rules (leaders and faction passives), a Monte
  Carlo AI with difficulty levels, and a headless simulator; a Scarecrow in
  the place of the unit it took back (#105); a player written with an LLM that
  plays against the AI through the API (#112).
- **The smallest findings of the review** (#133).
- **Before then:** try the page with a screen reader (Windows Narrator), and
  the animations' timings with more players.
- **Moved to "Later":** a leaderboard, which says little while everyone plays
  against the same AI.
- **Still to decide, from Phase 2:** answering a match that can no longer be
  played with "not found" instead of a 500; deleting matches left alone for
  long.
