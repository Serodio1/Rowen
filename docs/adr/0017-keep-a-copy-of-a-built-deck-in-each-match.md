# ADR 0017: Keep a copy of a player's built deck in each match they play with it

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

A player who is logged in may build decks from a faction's cards and keep up
to 10 (`player_decks`, #110). They may change a deck, all of it at once, or
delete it, whenever they like, also while a match with it goes on.

A match is kept as its decks, its seed and its actions, and the API plays the
actions again to know where it is, on every request
([ADR 0013](0013-keep-matches-in-postgresql.md)). The same decks, seed and
actions must always make the same match: with other cards in a deck, the same
seed deals other cards, and an action kept may not even be legal any more.

So the match must know which cards the player's deck held when it started,
whatever happened to the deck since.

## Decision

- **Each match played with a built deck keeps a copy of it**: its name and how
  many copies of each card, in two columns of `matches`, `player_deck_name`
  and `player_copies` (JSONB). `player_deck` still holds the faction, so the
  stats count a built deck with its faction's own. Both columns are empty for
  a match with a faction's own deck, and a CHECK keeps them both empty or both
  filled.
- **The match doesn't point at the deck** (no foreign key). Changing or
  deleting the deck never touches its matches.
- **The API makes the deck again from the copy** each time it plays a match
  again (`build_deck`), in the order of the faction's choices, never in the
  order of the copy's keys: JSONB keeps its keys in an order of its own, and
  the seed shuffles the deck in the order its cards come.
- **The AI plays the other faction's own deck.**
- A deck kept before a change of the rules that it now breaks starts no match
  (422 `invalid_deck`); the player changes it first.

## Alternatives considered

- **A foreign key to the deck**, and no copy. Less to keep, but changing the
  deck would change every match played with it, and deleting it would leave
  them unplayable.
- **The copy and a foreign key** (`ON DELETE SET NULL`), to link a match to its
  deck in "My matches". The link would show the deck as it is now, which may
  not be the one played: it could mislead.
- **Versions of each deck**, never changed, and a foreign key to the version
  played. Exact, but every change of a deck would add a row, kept for as long
  as a match points at it.
- **The whole list of cards**, one id per copy, instead of the counts. The same
  deck in more space, and the order of the list would have to be kept as it
  was.

## Consequences

- A match plays again the same way, whatever the player does to the deck. A
  test changes the deck after the match starts and gets the same view.
- Each match with a built deck takes a few hundred bytes more.
- "My matches" shows the deck's name as it was when the match started.
- If the rules change, a match with a deck that breaks them can't be played
  again: the same is true of the factions' own decks, and of every match,
  since the actions themselves may be illegal under new rules (#55).
