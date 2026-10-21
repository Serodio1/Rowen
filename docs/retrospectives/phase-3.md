# Phase 3 retrospective: a real interface

Phase 3 ends with the release `v0.3.0`. It ran on 21 October 2026, in 14 pull
requests (#90 to #106). At the end of it, the game looks like a card game: each
card is drawn upright with its own art, a move is made by clicking a card and
then where it goes, each move plays out card by card, and the whole match fits
on one laptop screen. This document looks back at what was built, which
decisions shaped it and why, and what to change next.

## What was built

| Part | What it does |
|---|---|
| Cards | Each card is drawn upright: its art, and over it the frame, the strength, icons for its rows and ability, and its name, all drawn by the page from the card's data. 25 pictures, made for Rowen ([the cards' art](../art.md)). |
| Playing | Choosing a card lights up where it can go; clicking there plays it. A card with nowhere to choose plays on a second click. The keyboard works too: Tab, the arrow keys, 1 to 3 for the rows, and Escape. |
| Board | The board, the hand, the moves and what happened fit on one screen at 1440×900; on a phone, they are one under the other. Clicking a discard pile lists its cards. |
| Animations | Each card played comes up large on the right, then flies to its place. A Muster brings its units one after the other, and a unit destroyed burns where it was. Passing, the end of a round and the next round are big messages, and the match ends with a table of its rounds. |
| What a card does | Pointing at a card, or reaching it with the keyboard, shows it large with what it does, in words from the engine. |
| Tests in a browser | Playwright plays a whole match in Chromium against the real Docker images, and checks the layout on a laptop and a phone. |

## Decisions and why

No new ADR: the decisions of Phase 3 follow from those already taken, mostly
ADR 0002 (the server is the only source of the rules).

- **The page draws the card; the picture is only the illustration.** The
  frame, the strength and the icons come from the card's data, so a new card
  needs a picture and a line in its deck, nothing else. A card with no picture
  yet shows a placeholder.
- **Our own art, and its origin written down.** The pictures were made with AI
  tools from prompts written for Rowen, which name no game, and
  [`docs/art.md`](../art.md) records the tools, the prompts and the license.
  The icons are our own SVG. Nothing comes from The Witcher 3.
- **Animations from the events, with no rules in the page.** The engine
  already says what each move did (a unit played, a unit destroyed, a round
  ended). The page turns each event into a step, and where a card goes is where
  the server's view has it. The page never works out a score.
- **One view after each move** (#104). The API sends the view after each
  action, the player's and each of the AI's, not only the last one. While a
  card comes up, the board is as it was before its move; once it flies, as the
  server left it after that move. Every number on the screen is the server's.
- **What a card does is written by the engine** (#99). The texts live next to
  the rules, so a new ability and its text change in the same place, and the
  API sends them with every card.
- **Where a Spy goes comes with the card** (#96). Each unit says whether it
  goes on the opponent's side. Putting it on the actions instead would have
  changed matches already saved, which are kept as their actions (ADR 0013).
- **Animations never wait for the player, and the player never waits for
  them.** A move can be made while the last one plays out. With the system's
  "reduce motion" setting, everything shows at once.
- **The keyboard and screen readers are first-class.** Every card and place is
  a button named as its move, such as "Play Soldier in the melee row". The
  animations and big messages are only pictures; the log says the same in
  words, and a card's text is read from the card itself.

## Testing

- **660 backend tests,** covering 100% of statements and branches, as in the
  phases before. The tests of the PostgreSQL store run in CI.
- **220 frontend tests,** with Vitest and Testing Library, written against
  what a player sees and does. The animations are tested with a fake clock.
- **Two Playwright tests in CI,** against the same Docker images as the server.
  One plays a whole match with no animations, so it is fast and reliable. The
  other checks the layout with the animations on, on a laptop and a phone.
- **Mutation testing by hand,** on every pull request. When a change to a line
  did not make a test fail, a test was written for it.
- **Tester agents, before the release** (#89). Two AI agents played 11
  matches in Chromium, with every kind of card and both decks, the keyboard,
  reduced motion and a phone's screen. They compared what the page said with
  what the API sent. They found no wrong rule, but about fifteen places where
  the page showed something at the wrong moment or in the wrong place. Almost
  all of them were fixed (#104, #106); a Scarecrow's place is left for
  Phase 5 (#105).

## What went well

- **The engine's events were enough.** Every animation, message and line of
  the log was built from events the engine already sent in Phase 1. Only one
  was added, for a Medic with nothing to revive.
- **The rules never moved to the page.** Even the fixes that looked like
  they needed a rule in the browser, such as the scores during an animation,
  were made by sending more from the server.
- **Playing found what reading didn't.** The tester agents found, in one
  afternoon, problems that the code reviews of the same pull requests had
  missed.
- **Generated types again.** When the API sent a view after each move instead
  of only one, the type checker showed every place in the page to change.
- **Small pull requests.** Fourteen pull requests in a day, each one
  understood and explained before it was merged.

## What could be better

- **Two bugs were found by playing, after review.** A weather card's help
  sentence was wrong, and a Spy's row didn't light up (#95). Both passed code
  review: nobody had played the change. This is why the tester agents now play
  the game before each release.
- **The first animations showed the end of a move at once.** The board showed
  the scores after all the moves while the cards were still coming, and the
  next round while the last one was still being told. It took a change to the
  API to fix it (#104).
- **A layout change made the rows grow by 10 pixels** (#94). It was caught
  before the merge, but only by looking.
- **Answers are bigger.** With a view after each move, an answer is about
  12 KB, from 5 KB (1.2 KB gzipped, as nginx sends it).
- **A Scarecrow is drawn at the end of its row,** not in the place of the unit
  it took back, because the API sends Scarecrows apart from the units (#105).
- **Twelve cards or more in the hand overlap,** and cover part of each
  other's icons.
- **Not yet tried with a real screen reader.** The names and descriptions were
  checked in the page's accessibility tree, not with a screen reader.
- **The animations' timings were chosen by one player.** A move of the AI with
  many cards can take several seconds to play out.

## Next

- **Phase 4:** accounts, a player's matches kept, and a guest mode.
- **Before then:** try the page with a screen reader (Windows Narrator), and
  tune the animations' timings after more people play.
- **Phase 5:** a Scarecrow in the place of the unit it took back (#105), with
  the rest of the rules.
- **v1.0.0:** a GIF in the README, once the interface is final; for now, a
  screenshot.
- **Still to decide, from Phase 2:** answering a match that can no longer be
  played with "not found" instead of a 500; deleting matches left alone for
  long; whether to add pre-commit hooks.
