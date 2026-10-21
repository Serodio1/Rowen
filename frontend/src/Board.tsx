import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import type { Action, Card, View } from "./api/client.ts";
import { CardFace } from "./CardFace.tsx";
import { onFirstClick } from "./clicks.ts";
import {
  choosable,
  playsOf,
  ROWS,
  rowPlay,
  selfPlay,
  unitPlay,
  type CardAction,
  type Chosen,
  type Playing,
} from "./plays.ts";
import { actionText, cardNames, cardText, unitText } from "./text.ts";

type Side = View["players"][number];
type Row = keyof Side["rows"];
type RowView = Side["rows"][Row];
type SpecialCard = Side["weather"][number];

// What a row looks like under each kind of weather (the classes are in
// index.css).
const WEATHER_LOOKS: Partial<Record<SpecialCard["kind"], string>> = {
  hoarfrost: "weather-frost",
  "thick-fog": "weather-fog",
  downpour: "weather-rain",
};

/**
 * The board, as the player of the view sees it: the AI's side on top and the
 * player's own at the bottom, so the two melee rows meet in the middle, as
 * when two people play face to face (and in the CLI). The player's hand is
 * under their rows.
 *
 * On a wide screen, the players and the weather are on the left and the
 * decks on the right, as in The Witcher 3. On a narrow one, the players and
 * the weather are above the rows, and the decks below the hand.
 *
 * Every number and card shown comes from the view: the page only lays them
 * out, and sees which total is higher (ADR 0002).
 *
 * With `playing`, the player plays on it: they choose a card (in the hand,
 * or in the discard pile while reviving), and the places it may go light up
 * as buttons; choosing one makes the move. Only the legal actions of the
 * view can be made. From the keyboard: Tab and the arrows go from card to
 * card, Enter chooses one and moves to its first place, 1, 2 and 3 play it
 * in the melee, ranged or siege row, and Escape lets it go.
 *
 * The lists have role="list": Tailwind takes their bullets off, and with
 * them Safari drops the lists from what VoiceOver reads.
 */
export function Board({ view, playing }: { view: View; playing?: Playing }) {
  const { you, ai } = sides(view);
  // Weather hits both sides, so it is shown once, for both.
  const weather = [...ai.weather, ...you.weather];
  const names = cardNames(view);
  const chosen = playing?.chosen ?? null;
  const plays =
    playing === undefined || chosen === null
      ? []
      : playsOf(playing.actions, chosen.card);
  const board = useRef<HTMLElement>(null);

  useEffect(() => {
    // Once a card is chosen, the focus goes to the first place it may go,
    // so the keyboard goes on from there.
    if (chosen !== null) {
      board.current?.querySelector<HTMLElement>("[data-target]")?.focus();
    }
  }, [chosen]);

  function onKeyDown(event: KeyboardEvent) {
    if (playing === undefined || chosen === null || playing.disabled) {
      return;
    }
    if (event.key === "Escape") {
      // Back to the card chosen, which is a button still.
      board.current
        ?.querySelector<HTMLElement>('[aria-pressed="true"]')
        ?.focus();
      playing.onChoose(null);
      return;
    }
    const row = ROWS[Number(event.key) - 1];
    const play = row === undefined ? undefined : rowPlay(plays, row);
    if (
      play !== undefined &&
      !event.altKey &&
      !event.ctrlKey &&
      !event.metaKey
    ) {
      playing.onPlay(play);
    }
  }

  // What the player's side needs to play on it.
  const act =
    playing === undefined
      ? undefined
      : { names, disabled: playing.disabled, onPlay: playing.onPlay };

  return (
    <section
      ref={board}
      aria-label="Board"
      onKeyDown={onKeyDown}
      className="wood grid grid-cols-1 gap-3 rounded-xl border-2 border-wood-600 p-2 shadow-2xl shadow-black/60 lg:grid-cols-[12rem_minmax(0,1fr)_6rem] lg:gap-x-4 lg:p-3"
    >
      <div className="grid grid-cols-3 gap-2 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:grid-cols-1 lg:content-center lg:gap-6">
        <PlayerPanel name="The AI" side={ai} ahead={ai.total > you.total} />
        <Weather cards={weather} />
        <PlayerPanel name="You" side={you} ahead={you.total > ai.total} />
      </div>
      <div className="flex flex-col gap-2 lg:col-start-2 lg:row-start-1">
        {(["siege", "ranged", "melee"] as const).map((row) => (
          <BoardRow
            key={row}
            label={`The AI's ${row} row`}
            row={ai.rows[row]}
            weather={weather.find((card) => card.weather_row === row)}
            bubble="bg-enemy"
          />
        ))}
      </div>
      <div className="flex flex-col gap-2 border-t-2 border-gold-600/70 pt-3 lg:col-start-2 lg:row-start-2">
        {(["melee", "ranged", "siege"] as const).map((row) => (
          <BoardRow
            key={row}
            label={`Your ${row} row`}
            row={you.rows[row]}
            weather={weather.find((card) => card.weather_row === row)}
            bubble="bg-ally"
            targets={
              act && {
                ...act,
                row: rowPlay(plays, row),
                unit: (id) => unitPlay(plays, row, id),
                shortcut: String(ROWS.indexOf(row) + 1),
              }
            }
          />
        ))}
      </div>
      <Hand
        view={view}
        discard={you.discard}
        playing={playing}
        plays={plays}
        names={names}
      />
      <div className="flex justify-between gap-2 lg:col-start-3 lg:row-span-3 lg:row-start-1 lg:flex-col">
        <Piles name="The AI's deck and discard pile" side={ai} />
        <Piles name="Your deck and discard pile" side={you} />
      </div>
    </section>
  );
}

/** Return the two sides of the board: the player's own and the AI's. */
function sides(view: View): { you: Side; ai: Side } {
  const [first, second] = view.players;
  // The API always sends both (its OpenAPI document says so), but the types
  // of the page see a list.
  if (first === undefined || second === undefined) {
    throw new Error("The view must have two players.");
  }
  return view.player === 0
    ? { you: first, ai: second }
    : { you: second, ai: first };
}

/**
 * What both players may know of one player: their total, their lives, how
 * many cards they hold, and whether they passed.
 *
 * @param ahead - Whether their total is the higher one, which a gold ring
 *   shows.
 */
function PlayerPanel({
  name,
  side,
  ahead,
}: {
  name: string;
  side: Side;
  ahead: boolean;
}) {
  const id = useId();
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="rounded-lg border border-wood-600 bg-wood-900/85 p-2 shadow-inner shadow-black/50"
    >
      <h3
        id={id}
        className="font-display text-sm font-bold text-gold-300 lg:text-base"
      >
        {name}
      </h3>
      <dl className="mt-1 grid grid-cols-[auto_1fr] items-center lg:grid-cols-[5.5rem_1fr] gap-x-2 gap-y-1 text-xs lg:text-sm">
        <dt className="opacity-80">Total</dt>
        <dd>
          <span
            className={`inline-grid min-w-9 place-items-center rounded-full border-2 px-1 py-0.5 font-display text-lg font-bold ${
              ahead
                ? "border-gold-300 text-gold-200 ring-2 ring-gold-400/60"
                : "border-wood-600"
            }`}
          >
            {side.total}
          </span>
          {ahead && <span className="sr-only"> (ahead)</span>}
        </dd>
        <dt className="opacity-80">Lives</dt>
        <dd>
          <span aria-hidden className="flex gap-1.5">
            {side.lives === 0
              ? "–"
              : Array.from({ length: side.lives }, (_, index) => (
                  <span
                    key={index}
                    className="size-3 rotate-45 rounded-sm bg-life shadow ring-1 ring-red-300/70 forced-colors:bg-[CanvasText]"
                  />
                ))}
          </span>
          <span className="sr-only">{side.lives}</span>
        </dd>
        <dt className="opacity-80">Hand</dt>
        <dd>{side.hand_size}</dd>
        {side.redraws_left > 0 && (
          <>
            <dt className="opacity-80">Swaps left</dt>
            <dd>{side.redraws_left}</dd>
          </>
        )}
      </dl>
      {side.passed && (
        <p className="mt-1 font-display text-sm text-gold-300 italic">Passed</p>
      )}
    </div>
  );
}

/** The weather cards in play, which hit the rows of both sides. */
function Weather({ cards }: { cards: SpecialCard[] }) {
  const id = useId();
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="flex flex-col items-center justify-center gap-1 rounded-lg border border-wood-600 bg-black/30 p-2 shadow-inner shadow-black/50"
    >
      <h3
        id={id}
        className="font-display text-xs tracking-widest text-gold-300/80 uppercase"
      >
        Weather
      </h3>
      {cards.length === 0 ? (
        <p className="text-xs italic opacity-70">None</p>
      ) : (
        <ul role="list" className="flex flex-wrap justify-center gap-1">
          {cards.map((card, index) => (
            // Two players may play the same weather card, with the same id.
            <li key={index}>
              <CardFace card={card} name={cardText(card)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * One row on one side: its score, its War Horn, its units and Scarecrows,
 * and the weather over it, if any.
 *
 * Screen readers read the row's name with its score and its weather, such as
 * "Your melee row: 3, under Hoarfrost".
 *
 * @param weather - The weather card that hits this row, if one is in play.
 * @param bubble - The colour of the score's bubble: the player's or the AI's.
 * @param targets - On the player's side, where the card chosen may go in
 *   this row: the whole row lights up as a button, or each unit it may go
 *   over.
 */
function BoardRow({
  label,
  row,
  weather,
  bubble,
  targets,
}: {
  label: string;
  row: RowView;
  weather: SpecialCard | undefined;
  bubble: string;
  targets?: RowTargets | undefined;
}) {
  const under = row.weathered ? (weather?.name ?? "weather") : null;
  const name = `${label}: ${String(row.score)}${under === null ? "" : `, under ${under}`}`;
  return (
    <div
      role="group"
      aria-label={name}
      className="relative flex min-h-23 items-center gap-2 overflow-hidden rounded-md border border-wood-600/70 bg-black/25 p-1"
    >
      {/* The weather first, so the cards are drawn over it. (The high
          contrast mode of Windows takes its look away: a dashed line shows
          it then.) */}
      {under !== null && (
        <div
          aria-hidden
          className={`pointer-events-none absolute inset-0 forced-colors:border-2 forced-colors:border-dashed ${weatherLook(weather)}`}
        />
      )}
      <span
        aria-hidden
        className={`relative grid size-9 shrink-0 place-items-center rounded-full border-2 border-wood-950 font-display text-base font-bold text-ink shadow shadow-black/60 ${bubble}`}
      >
        {row.score}
      </span>
      <div className="relative grid h-20 w-14 shrink-0 place-items-center rounded border border-dashed border-gold-600/40">
        {row.horn !== null && (
          <CardFace card={row.horn} name={cardText(row.horn)} />
        )}
      </div>
      {/* As high as the War Horn's place: a row is as high with cards as
          without, so the board never grows. */}
      <ul
        role="list"
        className="relative flex min-w-0 flex-1 justify-center-safe gap-1 overflow-x-auto"
      >
        {row.units.map((unit, index) => {
          const face = (
            <CardFace
              card={unit.card}
              strength={unit.strength}
              name={unitText(unit)}
            />
          );
          const play = targets?.unit(unit.card.id);
          return (
            // Copies of a unit share its id, so the place in the row is the key.
            <li key={`unit-${String(index)}`}>
              {targets === undefined || play === undefined ? (
                face
              ) : (
                <TargetButton targets={targets} play={play}>
                  {face}
                </TargetButton>
              )}
            </li>
          );
        })}
        {row.scarecrows.map((card, index) => (
          <li key={`scarecrow-${String(index)}`}>
            <CardFace card={card} name={cardText(card)} />
          </li>
        ))}
      </ul>
      {targets?.row !== undefined && (
        // Over the whole row, under the weather's name.
        <TargetButton
          targets={targets}
          play={targets.row}
          shortcut={targets.shortcut}
          className="absolute inset-0 z-10 flex items-end justify-end rounded-md bg-gold-300/15 p-1 ring-2 ring-gold-300 ring-inset hover:bg-gold-300/30"
        >
          <span
            aria-hidden
            className="rounded-sm bg-black/75 px-1.5 font-display text-xs text-gold-200"
          >
            Play here · {targets.shortcut}
          </span>
        </TargetButton>
      )}
      {/* The weather's name last, so it is drawn over the cards. */}
      {under !== null && (
        <span
          aria-hidden
          className="pointer-events-none absolute top-1 right-1 rounded bg-black/65 px-1.5 font-display text-xs text-white italic"
        >
          {under}
        </span>
      )}
    </div>
  );
}

/**
 * Where the card chosen may go in one of the player's rows, and what the
 * buttons need to make the move.
 *
 * @property row - The play that puts the card in the row, if it may go there.
 * @property unit - Return the play that puts the card over the unit with
 *   this id, if it may (a Scarecrow).
 * @property shortcut - The key that plays it in this row: 1, 2 or 3.
 * @property names - Each card's name by id, for the buttons' names.
 * @property disabled - Whether nothing can be played now.
 * @property onPlay - Called with the play of the button clicked.
 */
interface RowTargets {
  row: CardAction | undefined;
  unit: (id: string) => CardAction | undefined;
  shortcut: string;
  names: ReadonlyMap<string, string>;
  disabled: boolean;
  onPlay: (action: Action) => void;
}

/**
 * A place where the card chosen may go: a button that makes the move, named
 * as the move, such as "Play Soldier in the melee row".
 *
 * `data-target` marks it, so the focus can go to the first one.
 */
function TargetButton({
  targets,
  play,
  shortcut,
  className = "relative block rounded-md after:absolute after:inset-0 after:rounded-md after:ring-2 after:ring-gold-300 after:ring-inset hover:brightness-125",
  children,
}: {
  targets: RowTargets;
  play: CardAction;
  shortcut?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      data-target
      // Named as the move: the card under it or "Play here" only show where.
      aria-label={actionText(play, targets.names)}
      aria-keyshortcuts={shortcut}
      disabled={targets.disabled}
      className={`${className} transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold-200 disabled:cursor-not-allowed`}
      onClick={onFirstClick(() => {
        targets.onPlay(play);
      })}
    >
      {children}
    </button>
  );
}

/** Return the classes that draw `weather` over a row. */
function weatherLook(weather: SpecialCard | undefined): string {
  // Any weather the page has no look for still shows on the row.
  return (weather && WEATHER_LOOKS[weather.kind]) ?? "bg-white/10";
}

/**
 * The cards in the player's hand, in a gold strip under their rows. While
 * the player revives a unit after a Medic, the units they may revive are
 * over it.
 *
 * With `playing`, each card the player may choose is a button.
 *
 * @param discard - The player's discard pile, where revived units come from.
 * @param plays - The plays of the card chosen, if any.
 * @param names - Each card's name by id, for the buttons' names.
 */
function Hand({
  view,
  discard,
  playing,
  plays,
  names,
}: {
  view: View;
  discard: Card[];
  playing: Playing | undefined;
  plays: readonly CardAction[];
  names: ReadonlyMap<string, string>;
}) {
  const id = useId();
  const reviveId = useId();
  const ids =
    playing === undefined ? new Set<string>() : choosable(playing.actions);
  // One copy of each unit that may be revived: copies give the same moves.
  const revivable = view.reviving
    ? [
        ...new Map(
          discard
            .filter((card) => ids.has(card.id))
            .map((card) => [card.id, card]),
        ).values(),
      ]
    : [];
  const list = { playing, plays, names };
  return (
    <div className="flex flex-col gap-2 rounded-lg border-2 border-gold-600/80 bg-gold-400/10 p-2 shadow-inner shadow-black/40 lg:col-start-2 lg:row-start-3">
      {revivable.length > 0 && (
        <div>
          <h3
            id={reviveId}
            className="mb-1 font-display text-xs tracking-widest text-gold-300 uppercase"
          >
            Revive a unit from your discard pile
          </h3>
          <CardList
            {...list}
            labelledBy={reviveId}
            cards={revivable}
            from="discard"
            choosable={ids}
          />
        </div>
      )}
      <div>
        <h3
          id={id}
          className="mb-1 font-display text-xs tracking-widest text-gold-300/80 uppercase"
        >
          Your hand
        </h3>
        {view.hand.length === 0 ? (
          <p className="text-sm italic opacity-70">Your hand is empty.</p>
        ) : (
          <CardList
            {...list}
            labelledBy={id}
            cards={view.hand}
            from="hand"
            // While reviving, only the discard pile's units can be chosen.
            choosable={view.reviving ? new Set() : ids}
          />
        )}
      </div>
    </div>
  );
}

/**
 * A list of large cards, the hand or the units to revive: those that may be
 * chosen are buttons, and the arrow keys go from one to the next.
 *
 * @param from - Where the cards are, for the card chosen.
 * @param choosable - The ids of the cards that may be chosen.
 */
function CardList({
  labelledBy,
  cards,
  from,
  choosable,
  playing,
  plays,
  names,
}: {
  labelledBy: string;
  cards: Card[];
  from: Chosen["from"];
  choosable: ReadonlySet<string>;
  playing: Playing | undefined;
  plays: readonly CardAction[];
  names: ReadonlyMap<string, string>;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (step === undefined) {
      return;
    }
    // Also keeps the list from scrolling.
    event.preventDefault();
    const buttons = [
      ...event.currentTarget.querySelectorAll<HTMLElement>(
        "[data-choosable]:not(:disabled)",
      ),
    ];
    const at = buttons.findIndex((button) => button === document.activeElement);
    // From the last card to the first, and back.
    buttons.at((at + step) % buttons.length)?.focus();
  }

  return (
    <ul
      role="list"
      aria-labelledby={labelledBy}
      onKeyDown={onKeyDown}
      className="flex justify-center-safe gap-1.5 overflow-x-auto pt-2.5 pl-1.5"
    >
      {cards.map((card, index) => (
        // Copies of a card share its id, so the place in the list is the key.
        <li key={index}>
          {playing !== undefined && choosable.has(card.id) ? (
            <CardButton
              card={card}
              chosen={
                playing.chosen?.from === from && playing.chosen.index === index
              }
              self={selfPlay(plays)}
              playing={playing}
              names={names}
              onChoose={() => {
                playing.onChoose({ card: card.id, from, index });
              }}
            />
          ) : (
            <CardFace card={card} name={cardText(card)} size="large" />
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * A card the player may choose. Once chosen, it rises; clicking it again
 * plays it if it has nowhere to choose (weather, or a swap), or else lets it
 * go.
 *
 * @param chosen - Whether it is the card chosen.
 * @param self - The play of the card chosen with nowhere to choose, if any.
 */
function CardButton({
  card,
  chosen,
  self,
  playing,
  names,
  onChoose,
}: {
  card: Card;
  chosen: boolean;
  self: CardAction | undefined;
  playing: Playing;
  names: ReadonlyMap<string, string>;
  onChoose: () => void;
}) {
  const play = chosen ? self : undefined;
  return (
    <button
      type="button"
      data-choosable
      // Once chosen, it is where it goes too: the focus goes to it.
      data-target={play === undefined ? undefined : ""}
      aria-pressed={chosen}
      // Named as the move once it plays it, such as "Play Hoarfrost".
      aria-label={play === undefined ? cardText(card) : actionText(play, names)}
      disabled={playing.disabled}
      className="block rounded-md transition hover:-translate-y-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gold-200 disabled:cursor-not-allowed disabled:hover:translate-y-0 aria-pressed:-translate-y-2 aria-pressed:ring-2 aria-pressed:ring-gold-300"
      onClick={onFirstClick(() => {
        if (!chosen) {
          onChoose();
        } else if (play !== undefined) {
          playing.onPlay(play);
        } else {
          playing.onChoose(null);
        }
      })}
    >
      <CardFace card={card} name={cardText(card)} size="large" />
    </button>
  );
}

/** One player's deck, face down, and their discard pile, its top card up. */
function Piles({ name, side }: { name: string; side: Side }) {
  const id = useId();
  const top = side.discard.at(-1);
  return (
    <div role="group" aria-labelledby={id}>
      {/* On a narrow screen the two players' piles are side by side, so each
          says whose it is. */}
      <h3
        id={id}
        className="mb-1 text-center font-display text-xs text-gold-300 lg:sr-only"
      >
        {name}
      </h3>
      <dl className="flex gap-2 text-center text-xs lg:flex-col lg:items-center">
        <div className="flex flex-col items-center gap-1">
          <dt className="opacity-80">Discard pile</dt>
          <dd className="flex flex-col items-center gap-1">
            {top === undefined ? (
              <span className="h-20 w-14 rounded border border-dashed border-gold-600/40" />
            ) : (
              <CardFace card={top} name={cardText(top)} />
            )}
            <span>{cards(side.discard.length)}</span>
          </dd>
        </div>
        <div className="flex flex-col items-center gap-1">
          <dt className="opacity-80">Deck</dt>
          <dd className="flex flex-col items-center gap-1">
            <span
              aria-hidden
              className="grid h-20 w-14 place-items-center rounded-md border-2 border-gold-400 bg-linear-to-b from-card-back to-card-back-dark font-display text-lg font-bold text-gold-200 shadow-md shadow-black/60"
            >
              {side.deck_size}
            </span>
            <span className="sr-only">{cards(side.deck_size)}</span>
          </dd>
        </div>
      </dl>
    </div>
  );
}

/** Return a number of cards in words: `1 card`, `12 cards`. */
function cards(count: number): string {
  return `${String(count)} ${count === 1 ? "card" : "cards"}`;
}
