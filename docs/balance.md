# Balance report

Whether the two decks, Humans and Robots, are fair: how often each one wins
when the same AI plays both sides. First measured on 30 October 2026, at
commit `9811e2d` (v0.5.0 in progress), with the faction decks and their
leaders' passives ([ADR 0019](adr/0019-faction-passives-belong-to-the-deck.md)).

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

## Results, before the change

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

## After the change: the Humans draw 2 cards

To even them out, The Commander's passive changed from 1 card to 2 after
winning a round (rules, section 12; ADR 0019). Of the changes tried on copies
of the decks with the Easy AI, it was the only one to reach a fair game:

| Change tried (Easy AI, 4000 matches) | Robots won |
|---|---|
| Smart Guy 3 → 4 and AI 5 → 4 | 57.5% ± 1.6% |
| **Humans draw 2 cards** | **51.4% ± 1.6%** |
| Both of the above | 44.7% ± 1.6% |
| Smart Guy 3 → 5, and Humans draw 2 cards | 45.5% ± 1.6% |

Measured again, on the game as it now is (the same commands):

| AI on both sides | Matches | Decisive | Draws | Robots won | Humans won |
|---|---|---|---|---|---|
| Easy | 4000 | 3901 | 99 | **51.4% ± 1.6%** | 48.6% |
| Normal | 1000 | 973 | 27 | **46.9% ± 3.1%** | 53.1% |

Both margins reach 50%, the Normal one only just (43.8% to 50.0%): close to
fair, with Robots a little ahead against the Easy AI and Humans a little
ahead against the Normal one. A change to the cards or the passives should be
measured again the same way, and this report updated.

## After the Watch Man and the Firewall

Each faction's deck then got two Ward units (rules, section 7.4): the Watch
Man and the Firewall, melee, strength 5, which keep every Spy out of their
row. Measured again on 2 November 2026, with the same commands:

| AI on both sides | Matches | Decisive | Draws | Robots won | Humans won |
|---|---|---|---|---|---|
| Easy | 4000 | 3900 | 100 | **53.5% ± 1.6%** | 46.5% |
| Normal | 1000 | 972 | 28 | **51.5% ± 3.1%** | 48.5% |

The Normal margin reaches 50%; the Easy one just misses it (51.9% to 55.1%),
2 points more for Robots than before. Why was not measured. A guess: a Ward
unit stops the opponent's Spies, and Humans' Informant draws the same 2 cards
as the Computer Spy but gives Robots 3 points where the Computer Spy gives
Humans 2. Left as it
is, close enough to fair; the Normal AI, which the site offers, is even.

## After the change: the Humans draw 1 card, with stronger cards

With 2 cards after each round won, a deck of Spies ended the match with far
more cards than its opponent (see below), so on 3 November 2026 the
Commander's passive went back to 1 card. With only that change, Robots won
65.3% ± 2.1% (Easy AI, 2000 matches, seed 7). Changes to the Human cards
were tried on copies of the deck, with the passive at 1 card and the same
command:

| Change tried (Easy AI, 2000 matches) | Robots won |
|---|---|
| Smart Guy 3 → 5 | 60.3% ± 2.2% |
| Smart Guy 3 → 5, Informant 3 → 2 | 58.0% ± 2.2% |
| Smart Guy 3 → 4, Informant 3 → 2 | 60.4% ± 2.2% |
| Smart Guy 3 → 5, Informant 3 → 2, Plane 3 → 4 | 53.9% ± 2.2% |
| Smart Guy 3 → 5, Informant 3 → 2, Human 1 → 2 | 50.3% ± 2.2% |
| **Smart Guy 3 → 5, Human 1 → 2** | **52.2% ± 2.2%** |
| Smart Guy 3 → 5, Human 1 → 2, Plane 3 → 4 | 47.8% ± 2.2% |

The one in bold was kept: the Informant stays at 3, since a weaker one gives
the opponent fewer points and makes a deck of Spies stronger. Measured with
the commands at the top:

| AI on both sides | Matches | Decisive | Draws | Robots won | Humans won |
|---|---|---|---|---|---|
| Easy | 4000 | 3928 | 72 | **52.7% ± 1.6%** | 47.3% |
| Normal | 1000 | 976 | 24 | **48.2% ± 3.1%** | 51.8% |

Both margins reach 50%: fair, as before the change.

## A deck a player built: Spies

The faction decks are close to fair, but a player builds their own. One who
beat the Hard AI in every match played [`docs/decks/spies.json`](decks/spies.json):
the Humans' cards with three Informants (Spies) and three Medics, two
Scarecrows, and no weather. Spies draw cards, Medics bring them back, and the
Commander's passive drew two more after each round won (one since 3 November
2026): the player ended with far more cards than the AI. The figures below
were measured with two; with one, they were not measured again. `rowen-arena --deck` plays it in place of the
Humans' own deck. Until 2 November 2026, the AIs guessed that the Humans
played their own deck; since then, as on the site, they guess from the list
of the deck played (ADR 0018).

| AI on both sides | Matches | Decisive | Draws | Spies won | Robots won |
|---|---|---|---|---|---|
| Hard | 160 | 159 | 1 | **87.4% ± 5.2%** | 12.6% |
| Hard, with the Watch Man and the Firewall | 160 | 155 | 5 | **78.1% ± 6.5%** | 21.9% |
| Hard, with the Watch Man and the Firewall, the AIs knowing the deck's list | 320 | 317 | 3 | **69.4% ± 5.1%** | 30.6% |

Even with the Hard AI playing it, and without the player's own tactic
(taking an opponent's Spy back with a Scarecrow, to play it again), this
deck wins most matches: a built deck can be much stronger than the faction's
own. The rules for building a deck (at most 3 copies of a card) don't hold
it back. The Firewall, which keeps the Spies out of the Robots' melee row,
takes about 9 points from it, but it still wins most matches.

Measured again on 4 November 2026, with the Humans' passive at 1 card and
the cards above, 320 matches each (seeds 4000 and on, 16 runs of 20):

| AI on both sides | Spies won |
|---|---|
| Easy | **69.8% ± 5.1%** |
| Normal | **78.3% ± 4.6%** |
| Hard, before 4 November 2026 | **75.2% ± 4.8%** |
| Hard, with its rules of thumb (ADR 0018, update of 4 November 2026) | **78.6% ± 4.5%** |

The deck wins as often with the Easy AI as with the Hard one: its lead comes
from the deck, and a better AI on both sides doesn't take it away.
