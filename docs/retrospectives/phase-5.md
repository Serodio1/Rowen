# Phase 5 retrospective: a smarter AI and the full rules

Phase 5 ends with the release `v0.5.0`. It ran from 28 to 30 October 2026, in
34 pull requests (#135 to #174). At the end of it, the player chooses how well
the AI plays (Easy, Normal or Hard), each faction has a leader who brings a
passive, the decks win about as often as each other, and two AIs can play each
other thousands of times to measure all that. This document looks back at what
was built, which decisions shaped it and why, and what to change next.

## What was built

| Part | What it does |
|---|---|
| Monte Carlo AI | Normal and Hard guess the cards they can't see, many times, play each guess out to the end of the match, and choose the move that did best (#137, #154, #160). Easy is the AI from before. |
| AI levels | The player chooses the level before the deck; each match keeps it, and so does the list of matches (#138). |
| `rowen-arena` | Plays two levels against each other, with both decks in both seats, and says how often each won, with a margin of error, and how long a move took (#153). |
| Passives and leaders | Robots keep a random unit on the board at the end of a round; Humans draw 2 cards after winning one. Each faction's leader is the face of its passive, on the board and when choosing a deck (#161, #162, #170). |
| Balance report | How often each deck wins, measured with the arena, and the change that made it fair: Robots won 64.0% ± 1.5% against the Easy AI, and 51.4% ± 1.6% after it (#169, #170). |
| A Scarecrow in its place | A Scarecrow now shows where the unit it took back was, not at the end of the row (#149). |
| A page that grows | On a large screen everything is up to 1.6 times as big, so a 2K screen is not mostly empty (#164). |
| Dependencies kept up to date | Dependabot proposes the pinned actions and base images once a month, at least 14 days after their release (#143, #165). |

## Decisions and why

Two new ADRs:

- **A Monte Carlo AI that guesses the hidden cards** ([ADR 0018](../adr/0018-monte-carlo-ai-guesses-the-hidden-cards.md)).
  It only sees what a player sees, so it guesses the rest from the decks
  anyone can look up: its own, and the player's faction's. A fixed number of
  guesses (8 for Normal, 16 for Hard), not a time budget, so a test gives the
  same answer every time. Its randomness has a seed of its own, apart from the
  match's: the match's seed would tell it the player's hand. Playing each guess
  out to the end of the match won 67.6% ± 3.3% against Easy, against 59.8%
  ± 3.5% to the end of the round (#154).
- **Each faction has a passive, brought by its leader and carried out by the
  engine** ([ADR 0019](../adr/0019-faction-passives-belong-to-the-deck.md)).
  The passive is a key in the deck's data, and the engine has the rule for
  each key, as for the cards' abilities. The leader is only the face of the
  passive: no ability to use once a match.

And some smaller ones, in the pull requests:

- **Measure before saying "better".** Every change to the AI or the balance
  was played out in the arena, and only kept when the difference was larger
  than the margin of error (#153, #160, #169, #170).
- **The AI may skip the legality check, the API never.** In its imagined
  matches the AI only plays moves the engine listed, so checking them again
  only costs time; the API checks every move a player sends (#140).
- **A move a second, per address.** nginx lets each address make one move a
  second (with a burst of 20), so nobody can make the Hard AI think without
  end. With Cloud Run's limit of one instance and a budget cap, the game can't
  cost money (#139).
- **Actions and images pinned by their hash,** which can't move as a tag can,
  and updated by Dependabot, not by hand (#143, #165).

## Testing

- **999 backend tests,** covering 100% of statements and branches, as in the
  phases before. Some guard things that matter only by chance, such as the
  order of the steps at the end of a round, where swapping two lines changed
  no result until the passives came (#172).
- **314 frontend tests,** with Vitest and Testing Library.
- **Five Playwright tests in CI,** against the Docker images, through nginx.
- **Thousands of matches in the arena,** for the AI's strength and the
  balance, with the same seeds, so two versions face the same deals.
- **Mutation testing by hand,** on every pull request. When a refactor gave
  the same results for the same seeds, it proved the refactor changed nothing
  (#167).
- **Two reviews with AI agents.** A review of the whole repository at the
  start of the phase (28 October) found two real problems (the limit on moves,
  and the AI checking every move twice) and code to remove; it was fixed in
  #139 to #151. The one before the release (30 October) had three reviewers,
  a sceptic checking each one, and two tester agents playing in Chromium. It
  found nothing blocking. The findings were fixed in #171 to #174, among them
  the AI counting a Spy for the wrong player.

## What went well

- **The arena made the AI's decisions easy to check.** A guess about what
  makes the AI stronger became a number with a margin of error, and two of
  the ideas tried were left out because the number said they didn't help.
- **The passives were a few lines of data and rules.** Cards' abilities
  already worked by keys, so the passives did too, and the frontend only shows
  the text the API sends.
- **Fixing the balance took one number:** how many cards Humans draw
  (`ROUND_WIN_DRAWS`), after four variants were measured.
- **Reviews found bugs that no test had,** such as the Spy counted for the
  wrong player, and each came with a way to reproduce it.

## What could be better

- **The Hard AI made the player's own move slow.** The answer to a move only
  comes once the AI has played, and playing each guess out to the end of the
  match (#154) about doubled the time: about 2 seconds as the player saw it
  on the site. It
  was measured as the AI's time per move, not as the player's wait, and was
  only noticed by playing after the release. The page now shows the player's
  card at once while the AI thinks (#176).
- **A bug came back after the release:** a Spy revived by a Medic lit up the
  player's rows. The test of it had only the Spy in the discard pile, where
  the wrong card and the right one are the same; with another card before it,
  it fails (#175).
- **Some numbers were written before they were measured again,** such as a
  count of tests, and a pull request was pushed before its coverage was
  checked (99.96%, #174).
- **The pull requests in the middle of the phase were not reviewed by
  agents,** as decided, to save time; the review before the release then had
  more to look at.
- **About 5% of the matches kept before the passives can't be played again**
  with the new rules, and answer 500 when resumed. It was decided to leave
  them.
- **Not measured:** the Hard AI's strength with the passives, and any timing
  on Cloud Run and Neon.

## Next

- **`v1.0.0`:** the animations and the Hoarfrost's look (#158), a tutorial for
  a player who has never played (#159), the final README (a GIF, an
  architecture diagram, the testing strategy), and a final pass on the code
  and the documentation.
- **To measure:** Hard with 12 guesses instead of 16, which would answer
  faster, if it plays as well.
- **Still to decide, from Phase 2:** answering a match that can no longer be
  played with "not found" instead of a 500; deleting matches left alone for
  long.
- **Before the release:** the page with a real screen reader (Windows
  Narrator).
