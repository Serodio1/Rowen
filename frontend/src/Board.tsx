import { useId } from "react";
import type { View } from "./api/client.ts";
import { CardFace } from "./CardFace.tsx";
import { cardText, unitText } from "./text.ts";

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
 * player's own at the bottom, so the two melee rows meet in the middle, as on
 * a real table (and in the CLI). The player's hand is under their rows.
 *
 * On a wide screen, the players and the weather are on the left and the
 * decks on the right, as in The Witcher 3. On a narrow one, the players and
 * the weather are above the rows, and the decks below the hand.
 *
 * Everything shown comes from the view: nothing is worked out here (ADR 0002).
 */
export function Board({ view }: { view: View }) {
  const { you, ai } = sides(view);
  // Weather hits both sides, so it is shown once, for both.
  const weather = [...ai.weather, ...you.weather];

  return (
    <section
      aria-label="Board"
      className="wood grid grid-cols-1 gap-3 rounded-xl border-2 border-wood-600 p-2 shadow-2xl shadow-black/60 lg:grid-cols-[12rem_minmax(0,1fr)_6rem] lg:gap-x-4 lg:p-4"
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
          />
        ))}
      </div>
      <Hand view={view} />
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
                    className="size-3 rotate-45 rounded-sm bg-life shadow ring-1 ring-red-300/70"
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
        <ul className="flex flex-wrap justify-center gap-1">
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
 */
function BoardRow({
  label,
  row,
  weather,
  bubble,
}: {
  label: string;
  row: RowView;
  weather: SpecialCard | undefined;
  bubble: string;
}) {
  const under = row.weathered ? (weather?.name ?? "weather") : null;
  const name = `${label}: ${String(row.score)}${under === null ? "" : `, under ${under}`}`;
  return (
    <div
      role="group"
      aria-label={name}
      className="relative flex min-h-23 items-center gap-2 overflow-hidden rounded-md border border-wood-600/70 bg-black/25 p-1 lg:min-h-27"
    >
      {/* The weather first, so the cards are drawn over it. */}
      {under !== null && (
        <div
          aria-hidden
          className={`pointer-events-none absolute inset-0 ${weatherLook(weather)}`}
        >
          <span className="absolute top-1 right-2 font-display text-xs text-white italic drop-shadow">
            {under}
          </span>
        </div>
      )}
      <span
        aria-hidden
        className={`relative grid size-9 shrink-0 place-items-center rounded-full border-2 border-wood-950 font-display text-base font-bold text-ink shadow shadow-black/60 ${bubble}`}
      >
        {row.score}
      </span>
      <div className="relative grid h-20 w-14 shrink-0 place-items-center rounded border border-dashed border-gold-600/40 lg:h-24 lg:w-16">
        {row.horn !== null && (
          <CardFace card={row.horn} name={cardText(row.horn)} />
        )}
      </div>
      <ul className="relative flex min-w-0 flex-1 justify-center-safe gap-1 overflow-x-auto py-1.5 pl-1.5">
        {row.units.map((unit, index) => (
          // Copies of a unit share its id, so the place in the row is the key.
          <li key={`unit-${String(index)}`}>
            <CardFace
              card={unit.card}
              strength={unit.strength}
              name={unitText(unit)}
            />
          </li>
        ))}
        {row.scarecrows.map((card, index) => (
          <li key={`scarecrow-${String(index)}`}>
            <CardFace card={card} name={cardText(card)} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Return the classes that draw `weather` over a row. */
function weatherLook(weather: SpecialCard | undefined): string {
  // Any weather the page has no look for still shows on the row.
  return (weather && WEATHER_LOOKS[weather.kind]) ?? "bg-white/10";
}

/** The cards in the player's hand, in a gold strip under their rows. */
function Hand({ view }: { view: View }) {
  const id = useId();
  return (
    <div className="rounded-lg border-2 border-gold-600/80 bg-gold-400/10 p-2 shadow-inner shadow-black/40 lg:col-start-2 lg:row-start-3">
      <h3
        id={id}
        className="mb-1 font-display text-xs tracking-widest text-gold-300/80 uppercase"
      >
        Your hand
      </h3>
      {view.hand.length === 0 ? (
        <p className="text-sm italic opacity-70">Your hand is empty.</p>
      ) : (
        <ul
          aria-labelledby={id}
          className="flex justify-center-safe gap-1.5 overflow-x-auto pt-1.5 pl-1.5"
        >
          {view.hand.map((card, index) => (
            // Copies of a card share its id, so the place in the hand is the key.
            <li key={index}>
              <CardFace card={card} name={cardText(card)} size="large" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** One player's deck, face down, and their discard pile, its top card up. */
function Piles({ name, side }: { name: string; side: Side }) {
  const id = useId();
  const top = side.discard.at(-1);
  return (
    <div role="group" aria-labelledby={id}>
      <h3 id={id} className="sr-only">
        {name}
      </h3>
      <dl className="flex gap-2 text-center text-xs lg:flex-col lg:items-center">
        <div className="flex flex-col items-center gap-1">
          <dt className="opacity-80">Discard pile</dt>
          <dd className="flex flex-col items-center gap-1">
            {top === undefined ? (
              <span className="h-20 w-14 rounded border border-dashed border-gold-600/40 lg:h-24 lg:w-16" />
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
              className="grid h-20 w-14 place-items-center rounded-md border-2 border-gold-400 bg-linear-to-b from-[#5a2320] to-[#2b100e] font-display text-lg font-bold text-gold-200 shadow-md shadow-black/60 lg:h-24 lg:w-16"
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
