# Round plans for the Hard AI, and how long each level thinks

Date: 2026-11-12. Status: pull request 1 measured and not kept (ADR 0018,
update of 12 November 2026). Pull request 2: more samples measured and not
kept; the AI's turn takes at least 1, 2 or 3 s by level (ADR 0018, later
update of the same day).

## Why

The Witcher 3's card game AI first picks a tactic for the round (win with
the least, give the round up, wait for the opponent), then the card that
fits it. Its tactics are fixed rules with dice rolls. The Hard AI here
already plays each sample out to the end of the match (ADR 0018), so it
compares single moves well, but never compares a *plan* for the rest of the
round. The goal is a stronger Hard AI, and it is kept only if measured
stronger.

## Pull request 1: round plans on Hard

### What changes

In `rowen.ai.montecarlo.choose_action`, with `hard=True`, each sample now
scores two kinds of candidates side by side:

- each legal action, as today, played out with `_next` (this is "fight",
  done move by move);
- three plans for the rest of the round. In each, the AI follows the plan
  on all of its turns until the round ends, the opponent plays as `_next`
  says, and from the next round on both play as `_next` says. The score is
  `baseline.score` at the end of the match, as today.

| Plan | What the AI does on each of its turns |
|---|---|
| Minimal | Ahead: pass. Otherwise the play that gains the fewest points among those that put it ahead; if none does, the best play. |
| Give up | A Spy that draws it cards, if it holds one; otherwise pass. |
| Wait | The play that gains the fewest points; it doesn't pass while the opponent plays. |

Once the opponent has passed, every plan plays on as
`baseline.next_play`, as `_next` does.

If a plan scores best over all the samples, the AI plays that plan's first
move. Ties keep the first candidate, and the legal actions come first, so
a plan is played only when it is strictly better. On its next turn the AI
decides again from scratch: it keeps no memory, because the API replays a
match from its seed and actions, and the AI must stay a function of the
view and the seed.

### What doesn't change

`_rule_of_thumb` still comes first. Before round 1, once the opponent has
passed, and when reviving, the baseline still decides. Easy and Normal,
the engine, the API, the database and the frontend don't change.

### Tests

- Each plan on small hand-made states (Minimal 3 points behind with cards
  of 2, 5 and 9 plays the 5; Give up passes without a Spy and plays one
  with it; Wait plays the cheapest card).
- Hard picks a plan when it is clearly better.
- The same view and seed give the same action.
- Coverage stays at 100 %, and the plans pass a round of mutations.

### Kept only if (Rui's rule of 2 November)

Measured with `rowen-arena`, against the current Hard, with the source
decks and with `docs/decks/spies.json`:

1. the new Hard wins more than the current one, by more than the margin;
2. it doesn't lose to Easy;
3. its time per move is judged by pull request 2 (5 to 7 s online at most),
   not by the 25 % of 2 November (Rui, 12 November).

If it fails, the code isn't merged: the numbers go into ADR 0018 as a
measured idea, as on 2 November.

## Pull request 2: how long each level thinks (after PR 1)

- **Easy and Normal** keep their strength. They only *look* like they
  think: the page shows "The AI is thinking…" for at least 1 s on Easy and
  2 s on Normal, a wait in the browser that costs the server nothing.
- **Hard** thinks longer only if longer helps. First measure in
  `rowen-arena` whether more samples (for example 16 against 48) win more,
  by more than the margin. If they do, raise `HARD_SAMPLES` to a fixed
  number (the same view and seed still give the same move) that thinks
  5 to 7 s online. If they don't, the Hard keeps its samples, at most
  about 1 s longer than today.
- **Money:** before merging, check that the extra CPU time stays inside
  Cloud Run's free tier, from Google's own pricing page. The "Rowen cap"
  budget of 2 € and `maxScale: "1"` stay as they are.
- **Known cost:** the server has one CPU and one instance, so while a Hard
  AI thinks, other players wait longer.
