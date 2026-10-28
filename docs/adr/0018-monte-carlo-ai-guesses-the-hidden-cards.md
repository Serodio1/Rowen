# ADR 0018: Let a Monte Carlo AI guess the hidden cards

- **Status:** Accepted; the AI skips the legality check and may import
  `dataclasses` (see the end)
- **Date:** 2026-10-28

## Context

The baseline AI (ADR 0006) imagines every card it can't see as an unknown
card, with no strength. So while the opponent still plays, it can't tell
whether they hold enough to catch up: whether to pass is a rule of thumb, a
lead of 10 points. Phase 5 asks for a stronger AI, with difficulty levels
(`docs/plan.md`).

The AI must still only use its player view (ADR 0002, ADR 0003): a stronger
AI must never be one that peeks. Its moves are stored with the match, so a
replay doesn't run the AI again: the AI may use randomness of its own.

## Decision

1. **Guess the hidden cards, many times.** Each guess, a *sample*, fills the
   opponent's hand and both decks with real cards, in a random order. In each
   sample, the AI tries every legal action. Both players then play the rest
   of the round, and the AI scores the end of it with the baseline's score
   (cards 5 points, lives 7). It plays the action with the best total over
   all the samples.
2. **The cards come from two lists.** The AI knows its own deck. For the
   opponent, it guesses their faction's own deck, which anyone can look up,
   not the deck they built. From each list, it takes away the cards the view
   shows of that player (board, weather, discard pile; a Spy counts for the
   player who played it, on the other side), and draws the hidden cards from
   what is left. When too few are left, the rest are unknown cards.
3. **A fixed number of samples**, not a time limit, and a seed for their
   randomness: the same view and seed always give the same action.
4. **A quick play-out.** In a sample, each player passes when ahead by 10
   points and not on their last life, plays the card with the best score
   right after it otherwise, and plays on as the baseline does once the other
   player has passed. This is the baseline without its search after a pass,
   which took 86% of the time in a profile when it was used in the play-outs.
5. **The baseline decides where the hidden cards change nothing:** the
   redraw before round 1, the turns after the opponent has passed (they play
   no more cards that round) and the unit to revive after a Medic.
6. **Levels:** Easy is the baseline AI, Normal is 8 samples and Hard is 16.
   Choosing the level when a match starts is the next pull request (#136).

## Alternatives considered

- **Play each sample out to the end of the match.** The score is then only
  who won. With 4 samples it won 46% of the decisive matches against the
  baseline, against 49% for playing out the round, and took 40% longer.
- **Use the baseline itself in the play-outs.** It plays better after a pass,
  but a decision with 4 samples took 276 ms on average, against 60 ms.
- **A time limit for each decision.** The time is easier to predict, but the
  choice then depends on the speed of the machine, so the tests and the CI
  could choose differently from the server.
- **Guess from the deck the player really built.** The guesses would be
  better, but a human opponent doesn't know that deck either.

## Consequences

- Measured against the baseline, with both decks in both seats, in 160 to
  320 matches each: 8 samples won 52% of the decisive matches, 16 won 57%
  and 32 won 55%. With about 4% of error on each, only 16 is clearly ahead,
  and only a little. 32 samples took twice the time of 16 for no gain. The
  limit is the play-out, not the number of samples: a better play-out is
  the next step to a stronger AI.
- The guess of the opponent's deck can be wrong: against a deck the player
  built, the AI expects their faction's own cards.
- A decision takes longer. On the container, one match at a time, 8 samples
  took 114 ms on average and 0.7 s at most, and 16 took 203 ms and 1.4 s at
  most. The baseline takes under 1 ms (ADR 0006). The server runs one
  decision for most requests, since the AI plays as the baseline once the
  player has passed.
- The rules are still only in the engine: a new card needs no change to
  either AI.

## Update (2026-10-29)

- **The AI skips the legality check.** `apply` checks each action against
  `legal_actions` before carrying it out, and in the play-outs that was about
  a quarter of the AI's time, for actions it had just taken from
  `legal_actions` itself. The AI now calls `apply_legal`, which carries the
  action out without the check. The API still calls `apply`, so a player's
  move is always checked. On the container, 96 decisions of 16 samples took
  16.5 s instead of 22.5 s, with the same actions.
- **The AI may import `dataclasses`.** The guess rebuilt the match field by
  field, so a field added to the state later, such as a leader used once a
  match, would have been dropped in every guess with no error. It now uses
  `dataclasses.replace`, which changes the hidden cards and keeps every other
  field. The AI's import contract allows `dataclasses` and still nothing else
  outside the engine.
