# ADR 0005: Let the AI judge each move by trying it in the engine

- **Status:** Accepted
- **Date:** 2026-10-02

## Context

The AI opponent must choose good moves: which card to play, in which row, and
when to use abilities and special cards. To judge a move, it has to know what
the move would do on the board, and that depends on most of the rules:
weather, Bond, Inspire, War Horn, Spy, Medic, Muster, Wildfire and Scarecrow.

Two constraints apply. The AI may only see its own player view, as a human
player does (ADR 0002, rules section 11): not the opponent's hand, not the
decks and not the random number generator. And every rule must live in one
place, the engine (ADR 0003). More cards and factions will be added later.

## Decision

The AI judges each legal action by trying it in the engine:

1. It imagines the match from its view. What the view shows is copied as it
   is, and each hidden card (the opponent's hand and both decks) becomes an
   unknown card with no strength and no ability. The imagined match offers
   the same legal actions as the real one.
2. It applies each legal action to the imagined match with `apply`, which
   returns a new state and leaves the imagined match unchanged.
3. It scores each result with an evaluation function: the points, cards in
   hand and lives it has more of than the opponent. Once the match is over,
   only who won counts. It plays the action with the best score.

Whether to pass depends on what the opponent does next, which the engine
cannot tell. So passing is decided by rules of thumb instead.

## Alternatives considered

- **A formula in the AI for each kind of card** (a unit adds its strength, a
  War Horn doubles a row, and so on). No imagined match is needed, but each
  formula repeats a rule of the engine, and the two can drift apart: for
  example, a formula that forgets the War Horn, or Wildfire's rule for
  Legends (D8). Every new card would also need code in the AI.
- **Give the AI the whole game state.** Simulating would be simpler, but the
  AI would see the opponent's hand and could cheat, even by accident. It
  would also break the rule that the AI uses the same API as a human player.

## Consequences

- The rules exist only in the engine. A new card or ability works for the AI
  with no change to it, and the AI always agrees with the engine.
- The hidden cards are only a guess, so the AI misjudges what depends on
  them: a Muster calls no units from the deck, and the cards a Spy draws only
  count as cards. The Monte Carlo AI (Phase 5) will improve the guess by
  trying many random ones for the hidden cards.
- Each decision applies every legal action once, and more after a Medic. This
  is fast: about 0.3 ms per decision on average, and 5 ms at most, over 100
  matches against a random player. A deeper search will need new
  measurements.
- The weights of the evaluation function (a card is worth 5 points, a life
  10) were chosen by hand, then checked by playing versions of the AI against
  each other. They can be tuned later.
