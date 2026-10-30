# Balance report

Whether the two decks, Humans and Robots, are fair: how often each one wins
when the same AI plays both sides. Measured on 30 October 2026, at commit
`9811e2d` (v0.5.0 in progress), with the faction decks and their leaders'
passives ([ADR 0019](adr/0019-faction-passives-belong-to-the-deck.md)).

## How it is measured

`rowen-arena` lets two AIs play each other
(`backend/src/rowen/cli/arena.py`). With the same level on both sides, the
AI's skill cancels out, and what is left is the decks. Every match is Humans
against Robots; the decks swap seats from one match to the next, and the coin
flip in `start_match` decides who starts, as on the site.

The share is of the decisive matches (draws apart), with a 95% margin of
error. A fair game is 50%: a share whose margin doesn't reach 50% is not luck.

```sh
cd backend
uv run rowen-arena easy easy --matches 4000 --seed 1
uv run rowen-arena normal normal --matches 250 --seed 1   # and seeds 2, 3, 4
```

The Normal AI takes about 3.5 seconds a match, so its 1000 matches ran as
four runs of 250, side by side, added up below.

## Results

| AI on both sides | Matches | Decisive | Draws | Robots won | Humans won |
|---|---|---|---|---|---|
| Easy | 4000 | 3863 | 137 | **64.0% ± 1.5%** | 36.0% |
| Normal | 1000 | 970 | 30 | **56.9% ± 3.1%** | 43.1% |
| Easy, without the passives | 4000 | 3220 | 780 | 54.3% ± 1.7% | 45.7% |

The last row was measured on a copy of the decks with the leaders taken out,
so with no passive on either side; it is not a way the game can be played.

## What it shows

- **Robots win more, with both AIs.** Neither margin reaches 50%: this is not
  luck.
- **The cards give Robots about 4 percentage points.** Without the passives
  they still win 54.3%. The decks are mirrors except for three cards: the
  Drone (5) is weaker than the Sniper (6), but the AI (5) is stronger than the
  Smart Guy (3), and the Computer Spy gives the opponent 2 points where the
  Informant gives 3. Leaving the Spies out, Robots' units add up to 80 and
  Humans' to 77, and Robots' two Spies give the opponent 2 points fewer in
  all.
- **The passives add about 10 more**, with the Easy AI (64.0% against 54.3%):
  Robots' (one unit stays on the board after a round) is worth more than
  Humans' (a card after winning a round). With them, draws are much rarer (137
  against 780).
- **The Normal AI's gap is smaller** (57% against 64%). Why was not measured.

## Next

Changing the cards or the passives is a choice of rules, made apart from this
report: then the same commands are run again, and this report is updated with
the new figures.
