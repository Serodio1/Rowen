# ADR 0019: Give each faction a passive, kept with its deck and carried out by the engine

- **Status:** Accepted
- **Date:** 2026-10-29

## Context

Phase 5 asks for the rest of the rules, among them the factions' passives
(`docs/plan.md`, `docs/rules.md` section 13). A passive is a rule of a
faction's own that works by itself, with no action. Until now the two
factions only differed in their cards.

The rules must stay in the engine (ADR 0002, ADR 0003): the CLI, the API and
the browser only show what the engine says, and the AI plays through the
engine. A match must still replay from its seed and actions (ADR 0013). And
more factions are to come, so a new passive should be easy to add.

## Decision

1. **Humans draw a card after winning a round**; a tie is not a win. **Robots
   keep one random unit on the board after each round**, not a Legend and not
   a Spy, which the opponent played there (rules, section 12, D9).
2. **The passive belongs to the deck.** A faction's JSON file names it by key
   (`"passive": "draw_on_round_win"`), as cards name their abilities, and
   `Deck.passive` holds it. A deck a player builds has its faction's passive.
   Each player's state keeps the passive of the deck they play.
3. **The engine carries the passives out at the end of a round** that doesn't
   end the match, while it sets up the next one, in `rowen.engine.passives`.
   The unit Robots keep is chosen with the match's own randomness, so the same
   seed keeps the same unit. Drawing is told with the event a Spy already
   uses (`CardsDrawn`, hidden from the opponent); keeping a unit with a new
   public event, `UnitKept`.
4. **Everyone sees each side's passive**, as the faction is in plain sight:
   `SideView.passive`, and the API sends its text, from `PASSIVE_TEXTS` beside
   the rule, in each side and in the list of decks.

## Alternatives considered

- **Passives in a table of faction ids in the engine.** One place less in the
  data, but a deck a player builds would need its faction's id stored with
  it, and a new faction would need code as well as a file.
- **A passive as a function in the data, called by the engine.** More open,
  but the data would hold code, and the import contract of the engine
  (ADR 0003) could no longer check what a passive does.
- **Leaders first.** More visible, but a leader is a new action through the
  whole stack; passives need no action and teach the engine about factions
  first. Leaders are the next pull request.

## Consequences

- A new passive is a value in `decks.Passive`, a text in `PASSIVE_TEXTS`, its
  rule in `passives.py`, and its key in a faction's file. A test checks that
  every passive has a text.
- The AI plays with the passives with no change of its own: it imagines each
  side's passive from its view, and its play-outs go through the engine.
- **Matches stored before this change replay under the new rules.** A Human
  who won a round now draws, and a Robot unit now stays, so a stored action
  can turn illegal. Of 300 matches played by the baseline AI under the old
  rules and stopped before round 3, 15 could no longer be replayed. The API
  answers such a match with a 500 error. The results of finished matches are
  stored (ADR 0015), so the list of matches and the stats are not affected.
