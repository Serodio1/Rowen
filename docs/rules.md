# Rowen — Game Rules

> **Status: draft, awaiting approval.** Sections marked **Decision needed** list
> options and a recommendation. Nothing in this document is implemented until it
> is approved.

Rowen follows the rules of the Gwent minigame from *The Witcher 3* closely, with
original names for cards and abilities.

> **Decision needed (D1):** every name in this document (rows, lives, abilities,
> special cards) is a proposal and can be changed.

## 1. Overview

Two players each play from their own deck. A match is **best of three rounds**.
In each round, players take turns placing cards on the board; when both have
passed, the player with the higher total strength wins the round.

Cards are **not** drawn at the start of each round. The hand dealt at the start
has to last the whole match, so the core skill is card advantage: winning rounds
while spending fewer cards than the opponent, and knowing when to pass.

## 2. Components

### Cards

| Type | Description |
|---|---|
| **Unit** | Has a base strength, a row, and at most one ability. |
| **Legend** | A unit that is immune to every special card and ability (section 7.3). |
| **Special** | Has no strength; produces an effect (section 8). |

Every deck belongs to one **faction**. **Neutral** cards can be put in any deck.
The MVP has two factions with preconstructed decks; their card lists are defined
in a separate pull request.

### Board

Each player has three **rows**: **Melee**, **Ranged** and **Siege**. Each row
has one **horn slot** (see *War Horn*). A **weather area** is shared by both
players.

Each player also has a **deck** (face down), a **hand** and a **discard pile**
(face up).

### Lives

Each player starts the match with **2 lives**.

## 3. Match setup

1. Each deck is shuffled.
2. A random draw decides who plays first in round 1.
3. Each player draws **10 cards**.
4. **Redraw:** each player may swap up to **2 cards** from their hand, one at a
   time. A replacement is drawn first and the swapped card is then shuffled back
   into the deck, so a swapped card is never drawn straight back.

All randomness comes from a seed stored in the game state, so a match can be
replayed exactly.

## 4. Turns

On their turn, a player does exactly one of the following:

- **Play one card** from their hand.
- **Pass.** A player who has passed takes no more turns this round. The opponent
  keeps taking turns until they pass too.

A player with no cards in hand passes automatically.

## 5. Playing units

- A unit is placed on its row, on the side of the player who plays it.
- An **Agile** unit can be placed in the Melee or the Ranged row; the player
  chooses.
- A **Spy** is placed on the opponent's side (section 7.2).

## 6. Strength and score

A **row's score** is the sum of the current strength of its units. A **player's
total** is the sum of their three rows' scores.

The current strength of a unit that is not a Legend is computed in this order:

1. Start from its **base strength**.
2. **Weather** on its row: the strength becomes **1**.
3. **Bond:** multiply by the number of units in the row that share its bond
   group, including itself.
4. **Inspire:** add **+1** for each *other* unit with Inspire in the row.
5. **War Horn** in the row's horn slot: multiply by **2**.

Legends always keep their base strength.

*Example:* three Bond units with base strength 4 in a row under frost, with a
War Horn: each unit is 1 (weather) → 3 (×3 Bond) → 3 (no Inspire) → **6** (×2
horn), so the row scores 18.

> **Decision needed (D2):** confirm this order of calculation.
> **Recommendation:** keep it as written. As far as I know it matches the
> original game, and it keeps weather meaningful without making Bond and
> War Horn useless.

## 7. Abilities (MVP)

### 7.1 Placement

| Ability | Effect |
|---|---|
| **Agile** | Can be placed in the Melee or the Ranged row. |

### 7.2 On play (trigger once, when the card is played)

| Ability | Effect |
|---|---|
| **Spy** | Placed on the **opponent's** side, where its strength counts for the opponent. The player who played it draws **2 cards** from their deck (fewer if the deck has fewer). |
| **Medic** | The player chooses a unit (not a Legend) from **their own** discard pile and plays it immediately. Its ability triggers too, so a revived Medic or Spy works normally. With no valid target, nothing happens. |
| **Muster** | Immediately plays, from the player's **deck**, every card in the same muster group. Cards in hand are not affected. |

### 7.3 Ongoing (active while the card is on the board)

| Ability | Effect |
|---|---|
| **Bond** | Multiplies its strength by the number of units in the same row that share its bond group (section 6, step 3). |
| **Inspire** | Gives **+1** to every other unit in its row (section 6, step 4). |
| **Legend** | Immune to weather, War Horn, Inspire, Wildfire, Scarecrow and Medic. |

Bond groups and muster groups are defined in the card data (usually, cards with
the same name share a group).

## 8. Special cards (MVP)

| Card | Effect |
|---|---|
| **Hoarfrost** | Weather. Sets every unit in **Melee** rows, on both sides, to 1. |
| **Thick Fog** | Weather. Same effect on **Ranged** rows. |
| **Downpour** | Weather. Same effect on **Siege** rows. |
| **Clear Skies** | Removes every weather card from the weather area. |
| **War Horn** | Placed in the horn slot of one of the player's own rows. Doubles the strength of the units in that row (section 6, step 5). It can't be played into a slot that is already taken. |
| **Wildfire** | Destroys the unit(s) with the highest current strength on the whole board, on **both** sides. Every unit tied for highest is destroyed. Legends are never affected. |
| **Scarecrow** | Swaps places with a unit (not a Legend) on the player's own side, including an opponent's Spy on that side. That unit goes to the player's hand. The Scarecrow stays in its place, with 0 strength, until the end of the round. It can only be played if there is a valid target. |

Further rules:

- Weather affects **both** players. A second copy of the same weather adds no
  extra effect.
- A weather card stays in the weather area until Clear Skies is played or the
  round ends. Clear Skies and Wildfire go to the discard pile as soon as they are
  resolved.
- Destroyed units, discarded weather and resolved specials go to the discard pile
  of the player who owns that side or played the card (see D4 for units on the
  opponent's side).

## 9. End of a round

The round ends when **both players have passed**.

1. **Result:** the player with the higher total wins the round and the other
   player loses 1 life. On a **tie**, both players lose 1 life.
2. **Cleanup:** every card on the board (units, War Horns, Scarecrows) and every
   weather card goes to a discard pile.
3. Hands and decks carry over. **No cards are drawn.**

> **Decision needed (D3):** who plays first in rounds 2 and 3?
>
> - **A (recommended):** the **winner** of the previous round. Playing first is a
>   disadvantage, because you reveal your plan first, so this helps the player
>   who is behind. After a tie, the player who played second in the previous
>   round plays first.
> - **B:** the **loser** of the previous round.
> - **C:** players alternate every round, regardless of the result.
>
> I can't confirm which of these the original uses.

> **Decision needed (D4):** at cleanup, a Spy on the opponent's side goes to…
>
> - **A (recommended):** the discard pile of the side it is **on**, which is the
>   opponent's. That player's Medic can then revive it and use it against its
>   original owner. I believe this matches the original.
> - **B:** the discard pile of the player who played it.

## 10. End of the match

- A player who reaches **0 lives** loses the match.
- If both players reach 0 lives at the same time, the match is a **draw**.
- A match therefore lasts at most **3 rounds**.

## 11. Information

| Visible to both players | Visible only to its owner |
|---|---|
| The board, the weather area, discard piles, lives, number of cards in each hand and deck, who has passed | The contents of the hand |

Nobody sees the order of the cards in a deck. The server only sends each player
what they are allowed to see.

## 12. Decks (MVP)

Each faction has one preconstructed deck. Deck building (choosing your own cards)
arrives in Phase 4, with limits based on the original: at least **22 units** and
at most **10 special cards**.

## 13. Later (not in the MVP)

- **Leaders:** one per deck, with an ability usable once per match (it takes a
  turn).
- **Faction passives**, for example:
  - draw a card after winning a round;
  - win rounds that end in a tie;
  - keep one random unit on the board after each round;
  - choose who plays first in round 1;
  - at the start of round 3, play two random units from the discard pile.
- **Unit versions of specials:** a unit with War Horn for its own row, and a unit
  with Wildfire limited to one enemy row when that row's score is at least 10.
- **Extra mechanics:** a weather card that hits two rows, units that transform,
  units that summon another unit when destroyed.

## 14. Decisions needed

| # | Question | Recommendation |
|---|---|---|
| D1 | Names: rows, lives, ability and special card names used in this document | Keep them, or propose your own |
| D2 | Order of the strength calculation (section 6) | Keep as written |
| D3 | Who plays first in rounds 2 and 3 (section 9) | A: the previous round's winner |
| D4 | Discard pile for a Spy at the end of a round (section 9) | A: the side it is on |
| D5 | MVP scope: the abilities in sections 7–8 now, everything in section 13 later | Accept |
