# ADR 0018: Let a Monte Carlo AI guess the hidden cards

- **Status:** Accepted; the AI skips the legality check, may import
  `dataclasses`, and plays each sample out to the end of the match (see the
  updates at the end)
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
   of the match, and the AI scores the end of it with the baseline's score
   (who won, then the cards left). It plays the action with the best total
   over all the samples. (Until 2026-10-29, the rest of the round only: see
   the second update.)
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
  Measured again with more samples and more matches, it won clearly: it is
  the decision now (second update).
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

## Update (2026-10-29, later): play each sample out to the end of the match

`rowen-arena` (#153) plays two levels of the AI against each other with both
decks in both seats. Against the baseline, Hard (16 samples) played the
rounds out as before, and then the whole match, in 400 matches each with the
same two seeds:

| Play-out | Seed 0 | Seed 1 | Both | Time per move |
| --- | --- | --- | --- | --- |
| To the end of the round | 56.6% ± 5.1% | 62.9% ± 5.0% | 59.8% ± 3.5% | 0.14 s |
| To the end of the match | 65.6% ± 4.8% | 69.6% ± 4.6% | 67.6% ± 3.3% | 0.19 s |

The difference, 8 points, is larger than both margins. Normal (8 samples)
won 56.7% ± 5.0% with the whole match, in 0.10 s per move. Why the first
measurement above disagreed is not known: it used 4 samples, fewer matches
and a one-off script.

- Each sample is now played out until the match ends, and scored with the
  baseline's score: who won the match, and then the cards left.
- A move takes about 1.4 times as long, under the limit of twice the time
  set for this change. Normal and Hard keep 8 and 16 samples.
- Giving up a round in the play-outs when far behind was measured too: 58.4%
  ± 5.0% with seed 0, no clear gain, so it was left out.

## Update (2026-11-02): two changes measured, neither kept

A player beat the Hard AI in every match with a deck they built
(`docs/decks/spies.json`: more Spies and Medics, two Scarecrows, no
weather), ending each match with many more cards in hand. Two changes that
could make the AI care more about its cards were measured against the Hard
AI as it is, with `rowen-arena` and the faction decks, 160 matches each
(the same seeds):

| Change | New Hard won | Time per move, new / old |
| --- | --- | --- |
| Play the match out also once the opponent has passed, instead of the baseline's choice, which spends up to two cards to win a round | 49.7% ± 7.8% | 0.49 s / 0.39 s |
| A card in hand worth 8 points instead of 5 (`baseline.CARD_VALUE`) | 49.1% ± 7.8% | 0.42 s / 0.41 s |

Neither is ahead by more than its margin, and the first is 26% slower, over
the 25% allowed. Both were left out. What makes that deck so strong is the
deck itself: with the Hard AI on both sides, it won 87.4% ± 5.2% of the
decisive matches against Robots (`docs/balance.md`).

## Update (2026-11-02, later): guess from the deck the player really built

The Watch Man and the Firewall (rules, section 7.4) took the Spies deck from
87.4% to 78.1% against the Hard AI. Three ways to make the Hard AI think
harder, each with 48 samples a move (about 1.3 s a move in the container,
four times the Hard's), were then measured against the Hard AI as it is,
400 matches each, with the faction decks:

| Change | New Hard won |
| --- | --- |
| 48 samples instead of 16 | 49.0% ± 5.0% |
| Play-outs that take the lead with the weakest card that does, instead of the strongest | 46.6% ± 4.9% |
| Successive halving: after a few samples, drop the worse half of the actions and give their samples to the rest | 51.0% ± 4.9% |

None is ahead by more than its margin: none was kept.

Then the alternative turned down above, guessing from the deck the player
really built, was measured with the Hard AI on both sides and the Spies deck
against Robots, 320 matches: the Spies deck won **69.4% ± 5.1%** of the
decisive matches, against 78.1% ± 6.5% with the faction's own deck.

So point 2 of the decision changes: **the AI guesses each player's hidden
cards from the list of the deck they play, a built one too.** It is what a
player who knows the opponent's decklist knows: which cards the deck has,
never which are in the hand or in what order they come. With a faction's own
deck, nothing changes. The API gives the AI the decks of the match
(`_ai_choice` in `backend/src/rowen/api/app.py`), and `rowen-arena` does the
same, so it keeps measuring the AI as it plays on the site.

## Update (2026-11-04): the Hard level gives up lost rounds and follows rules of thumb

After the Humans' passive went back to 1 card (ADR 0019, `docs/balance.md`),
changes to the Hard level were measured with `rowen-arena`, each on a fixed
copy of `main` and the same seeds, in two ways:

- **(a)**: the new Hard against the Hard as it was, faction decks, 400
  matches. Kept if it wins more than about 55%.
- **(b)**: the new Hard on both sides, the Spies deck (`docs/decks/spies.json`)
  against Robots, 320 matches: the Spies deck's share. The Hard as it was
  gives **75.2% ± 4.8%**; lower is better.

| Change | (a) new Hard won | (b) Spies won |
| --- | --- | --- |
| In the play-outs, a player 10 or more points behind, with a life to spare, gives up the round (playing a Spy first) | 56.4% | 82.5% |
| The same, only when not behind in cards in the hand (**kept**) | **58.4% ± 4.9%** | 80.0% |
| …and in the play-outs, a Spy is played first | 55.5% | 78.4% |
| …and in the play-outs, a Scarecrow takes an opponent's Spy back | 57.4% | 82.0% |
| …and before round 1, a better choice of cards to swap | 62.4% | 80.6% |
| …and a Ward unit first, where the opponent's Spies would go (**kept**) | **60.2% ± 4.8%** | **75.9% ± 4.7%** |
| …and four rules about Spies before the samples (**kept**, below) | **61.2% ± 4.8%** | 78.6% |

The rows without a margin were measured on 3 November 2026 with the same
bench (branch `experiment/hard-ai`, never merged); the others on 4 November.
Giving up at 5, 10 or 15 points behind won as often. Giving up whatever the
cards offered rounds to an opponent ahead in cards, which a deck of Spies
always is: hence "not behind in cards". Three more changes won no more than
the Hard as it was (48.6% for the Hard against itself): reviving by the
samples instead of the baseline (48.6%), a Scarecrow rule in the play-outs
without giving up (49.2%), and a tie-break between equal totals (48.8%). A
prototype of information-set Monte Carlo tree search (ISMCTS) won 44.4%.

So the Hard level (`hard=True` in `choose_action`) now:

1. In its play-outs, gives up a round 10 or more points behind (`GIVE_UP_BEHIND`)
   when it has a life to spare and no fewer cards than the opponent, playing
   a Spy first if it holds one (`_next`).
2. Before the samples, follows rules of thumb (`_rule_of_thumb`): after a
   Medic, revive a Spy; take an opponent's Spy back with a Scarecrow; play a
   Spy; play a Medic while a Spy is in the discard pile; play a Ward unit in
   a row where the opponent's Spies would go. A Spy draws 2 cards, which the
   play-outs, scoring each move by its points only, never see.

Normal and Easy don't change. In 12 matches, this code took the same 375
decisions as the version measured on the bench.

None of these brings (b) near 50%: the Spies deck won 69.8% with the Easy AI
on both sides and 78.3% with the Normal, so most of its lead is the deck's,
not the AI's. The rules about Spies help most when the Robots' deck has the
cards to use them: on the bench, with these rules on the Robots' side only
and a Robots deck of three Scarecrows, three Spies, three Mechanics and three
Firewalls, the Spies deck won 58.0%. Changes to the Robots'
deck are separate decisions, made after this one.

## Update (2026-11-04, later): on Hard, the Robots answer a deck of Spies with a deck against them

The AI knows the list of the player's deck (above). On Hard, against a deck
of 3 Spies or more (`SPIES_TO_COUNTER` in `backend/src/rowen/api/app.py`),
the Robots play a deck built against Spies (`ROBOTS_AGAINST_SPIES`): one more
Computer Spy and Scarecrow and two more Mechanics than the faction's own, one
Drone and one War Horn fewer. The Scarecrows take the player's Spies back,
the Spies and Mechanics draw and revive, and the Firewalls keep Spies out.
Measured with `rowen-arena`, the Hard AI on both sides, the Spies deck
(`docs/decks/spies.json`), seeds 1 to 4, 80 matches each:

| Robots' deck | Spies won |
| --- | --- |
| Their own | 75.9% ± 4.7% |
| Against Spies | **63.1% ± 5.3%** |

These seeds differ from the update above (seeds 4000 and on), so its 78.6%
compares with these only roughly, and the 58.0% of the bench, with the rules
on one side only, not at all.

Against everyone it would be too strong: on the bench, against the Humans'
own deck, it won 63.1% where the Robots' own won 49.0%. So it is only the
answer to a deck of Spies, as a player who knows the opponent's decklist
would build one. The player isn't told. A match still keeps only the id of
the AI's faction: the deck follows from the player's deck and the level, so
every request makes the same one again (`_played`). Only the Robots have such
a deck; the Humans don't yet.
