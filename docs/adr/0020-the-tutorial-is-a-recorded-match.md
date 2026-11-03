# ADR 0020: Teach the game with a tutorial that is a recorded match

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

Issue #159 asks for a tutorial. Someone who opens the link, such as a
recruiter, has seconds, and has never played: they must learn rows, strength,
totals, passing, rounds, a Spy, weather and a Medic quickly, and without it
getting in the way of someone who wants to play at once.

The rules live in the engine only (ADR 0002): the page decides nothing. And
the game costs money to run (Cloud Run and the database, ADR 0010): a
tutorial should not add API calls or stored matches.

## Decision

1. **The tutorial is a guided match on the real board**, always identical,
   reached by an optional **Tutorial** button on the main menu. The Humans
   (the player) play the Robots (the AI) for 2 rounds, about 3 minutes.
2. **It is a recorded match, played back in the page.** A script of 16 steps
   (`rowen.api.tutorial`) says what the player does at each step and how the
   AI answers. A generator plays it with the engine from a fixed seed, with
   `apply` checking every action, and records, at each step, the player's
   view and the moves, in the API's own JSON shapes. The output is
   `frontend/src/tutorial.json`, loaded only when the tutorial opens.
3. **Only the asked move is on.** In each recorded view the legal actions are
   cut down to the one the balloon asks for; the other cards and rows are off.
4. **A stale file fails the build.** A backend test generates the tutorial
   again and compares it with the file, as it does for `openapi.json`
   (ADR 0008). The fix is `uv run python -m rowen.api.tutorial`.
5. The recorded views hold only what the player sees: the AI's hand is never
   in them (a test checks it).

## Alternatives considered

- **A scripted match on the server.** The real API, with a fixed seed and a
  fixed AI. It needs no recorded file, but it adds endpoints, API calls and
  stored matches, and the tutorial would depend on the server being awake.
- **A "How to play" page.** The cheapest, but text and pictures teach worse
  than playing, and nobody reads it. It would also say nothing the engine
  could check, so it could drift from the rules unnoticed.

## Consequences

- No API calls, no database and no cost; the tutorial works even if the
  server is cold or down. Nothing changes in the rules, the endpoints or
  nginx.
- The rules are still only in the engine: the file is what the engine did.
  Changing the cards, the rules or the script means generating the file again,
  and CI says so when it is forgotten. The seed is found by search; changing
  the deal means searching for a new one.
- The file is large (about 300 KB indented, about 134 KB compact as bundled,
  which nginx gzips to about 4 KB, since every step repeats the whole
  view), which is why it is loaded lazily and not with the first page.
- The page gets a second mode of the board, fed with recorded views instead of
  the API's answers (the next pull request).
