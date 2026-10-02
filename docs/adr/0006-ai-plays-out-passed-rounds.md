# ADR 0006: Let the AI try moves in the engine, and play out passed rounds

- **Status:** Accepted
- **Date:** 2026-10-02
- **Supersedes:** ADR 0005

## Context

ADR 0005 decided how the AI opponent chooses a move: it imagines the match
from its player view and tries each legal action there with the engine. It
also decided that passing is a rule of thumb, because the engine cannot tell
what the opponent will do next.

That rule of thumb was weakest once the opponent had passed. The AI then kept
playing until it was ahead, even when the round could not be won. In one
seeded match, it played all 7 of its cards, still lost round 1 by 34 to 19,
and then had nothing left for round 2.

But once the opponent has passed, they take no more turns in that round. The
rest of the round then depends only on the AI, so the engine can tell how it
ends.

## Decision

1. **As in ADR 0005**, the AI only gets its player view. It imagines the match
   from it, with an unknown card in place of each hidden card (no strength,
   and a Legend, so nothing can change that). It tries each legal action with
   `apply` and scores the result.
2. **The score** is what the AI has more of than the opponent: points on the
   board, cards in hand (5 points each) and lives (7 points each). Once the
   match is over, winning or losing outweighs everything, and the cards left
   only break ties.
3. **While the opponent still plays**, the AI plays the action with the best
   score. It passes first when it leads by 10 points or more, unless it is on
   its last life.
4. **Once the opponent has passed**, the AI plays the rest of the round in the
   imagined match, for passing now and for each play. After the play, it
   either passes at once or plays on, and the better of the two counts. When
   it plays on, it passes once ahead. Until then, it plays the action with the
   best score among those that raise its lead, and passes when none does. It
   scores the end of the round and chooses the best action. Pass is tried
   first, so on equal scores it keeps its cards.
5. **A life is worth 7 points**, so winning a round instead of losing it is
   worth 14 points: more than two cards and less than three. The AI spends up
   to two cards to win round 1, and any number to win a round that decides the
   match.
6. **Before round 1**, the AI swaps its spare Muster cards: a second card of a
   group in the hand comes from the deck anyway when the first one is played.
   The engine's `muster_group` says which cards muster together.

## Alternatives considered

- **Keep ADR 0005's rule once the opponent has passed:** pass as soon as the
  AI is ahead, otherwise play the best card. It is simpler, but it wastes cards
  on rounds that are lost. The new AI won 68.8% of the decisive matches against
  it, over 4,000 matches.
- **Play on with the best score at each step**, Spies included. The cards a Spy
  draws are unknown in the imagined match, so after a Spy the AI could not
  catch up there. It then gave up rounds, and even matches, that it could have
  won.
- **Try every order of the cards left.** That would give the exact best line,
  but the number of orders grows too fast with the size of the hand.

## Consequences

- The rules are still only in the engine, so a new card still needs no change
  to the AI.
- The play-out is greedy: it can miss a better order of plays. The unknown
  cards are still a guess, so a Muster calls no units from the deck. The Monte
  Carlo AI (Phase 5) will try many random guesses for the hidden cards.
- Decisions take longer, but stay fast. Over 1,000 matches against the
  previous AI, a decision took 0.6 ms on average and 30 ms at most. A state
  built to be slow, with 16 real cards in hand, took 0.5 s. A made-up state
  with four different Medics took 20 s, because each Medic multiplies the
  lines to try. The data decks hold one Medic each. Decks with more Medics
  will need a limit on the search.
- The weights (a card is worth 5 points, a life 7, a 10-point lead to pass
  first) were chosen by hand. They were then checked by playing versions of the
  AI against each other. A life worth 6 makes the same choices.
