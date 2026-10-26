import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import type { Api, Choice, PlayerDeck } from "./api/client.ts";
import {
  choicesQuery,
  decksQuery,
  deleteDeck,
  forgetDecks,
  playerDecksQuery,
  saveDeck,
} from "./api/requests.ts";
import { CardFace } from "./CardFace.tsx";
import { ALERT, BUTTON, PANEL } from "./styles.ts";
import { cardText } from "./text.ts";

/**
 * The decks the player who is logged in built: a list of them, to change or
 * delete each one, and a button per faction to build a new one. Building or
 * changing a deck opens the editor in the list's place.
 *
 * It takes the focus when it opens, and again when the editor closes: the
 * button that opened it is gone.
 *
 * @param onBack - Called when the player is done with their decks.
 */
export function MyDecks({ api, onBack }: { api: Api; onBack: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  // The deck being built (`deck` null) or changed, from a faction's cards,
  // or null while the list shows.
  const [editing, setEditing] = useState<{
    faction: string;
    deck: PlayerDeck | null;
  } | null>(null);
  useEffect(() => {
    if (editing === null) {
      heading.current?.focus();
    }
  }, [editing]);
  const factions = useQuery(decksQuery(api));
  const names = new Map(factions.data?.map((deck) => [deck.id, deck.name]));
  const decks = useQuery(playerDecksQuery(api));

  if (editing !== null) {
    return (
      <DeckEditor
        api={api}
        faction={editing.faction}
        factionName={names.get(editing.faction) ?? editing.faction}
        deck={editing.deck}
        onDone={() => {
          setEditing(null);
        }}
      />
    );
  }
  const full = decks.isSuccess && decks.data.decks.length >= decks.data.most;
  return (
    <section className={PANEL}>
      <h2
        ref={heading}
        tabIndex={-1}
        className="font-display text-2xl text-gold-300 outline-none"
      >
        My decks
      </h2>
      {decks.isPending && <p className="italic">Loading your decks…</p>}
      {decks.isError && (
        <>
          <p role="alert" className={ALERT}>
            {decks.error.message}
          </p>
          <button
            type="button"
            className={BUTTON}
            onClick={() => {
              void decks.refetch();
            }}
          >
            Try again
          </button>
        </>
      )}
      {decks.isSuccess &&
        (decks.data.decks.length === 0 ? (
          <p className="italic">No deck built yet.</p>
        ) : (
          <ul aria-label="Your decks" className="flex w-full flex-col gap-2">
            {decks.data.decks.map((deck) => (
              <DeckRow
                key={deck.id}
                api={api}
                deck={deck}
                factionName={names.get(deck.deck) ?? deck.deck}
                onEdit={() => {
                  setEditing({ faction: deck.deck, deck });
                }}
              />
            ))}
          </ul>
        ))}
      {decks.isSuccess && (
        <div className="flex flex-col items-center gap-2">
          {full ? (
            <p className="italic">
              You have {decks.data.most} decks, the most you may keep: delete
              one to build another.
            </p>
          ) : (
            <div className="flex flex-wrap justify-center gap-2">
              {factions.data?.map((faction) => (
                <button
                  key={faction.id}
                  type="button"
                  className={BUTTON}
                  onClick={() => {
                    setEditing({ faction: faction.id, deck: null });
                  }}
                >
                  New {faction.name} deck
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <button type="button" className={BUTTON} onClick={onBack}>
        Back
      </button>
    </section>
  );
}

/**
 * One deck of the player's in the list: its name, its faction and how many
 * cards it has, with buttons to change it or delete it. Deleting asks first,
 * in the same place: "Delete" or "Keep".
 */
function DeckRow({
  api,
  deck,
  factionName,
  onEdit,
}: {
  api: Api;
  deck: PlayerDeck;
  factionName: string;
  onEdit: () => void;
}) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const remove = useMutation({
    mutationFn: () => deleteDeck(api, deck.id),
    onSuccess: () => {
      forgetDecks(queryClient);
    },
  });
  const cards = Object.values(deck.copies).reduce((sum, n) => sum + n, 0);
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-gold-600/60 px-3 py-2">
      <span>
        <strong className="text-gold-200">{deck.name}</strong>{" "}
        <span className="text-sm opacity-80">
          {factionName}, {cards} cards
        </span>
      </span>
      {remove.isError && (
        <p role="alert" className={ALERT}>
          {remove.error.message}
        </p>
      )}
      <span className="flex gap-2">
        {asking ? (
          <>
            <span className="self-center text-sm">Delete {deck.name}?</span>
            <button
              type="button"
              className={BUTTON}
              disabled={remove.isPending}
              onClick={() => {
                remove.mutate();
              }}
            >
              Delete
            </button>
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                setAsking(false);
              }}
            >
              Keep
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className={BUTTON}
              aria-label={`Change ${deck.name}`}
              onClick={onEdit}
            >
              Change
            </button>
            <button
              type="button"
              className={BUTTON}
              aria-label={`Delete ${deck.name}`}
              onClick={() => {
                setAsking(true);
              }}
            >
              Delete
            </button>
          </>
        )}
      </span>
    </li>
  );
}

/**
 * Where a deck is built or changed, in two columns as in the original game:
 * the cards the deck may hold, and the deck. Choosing a card in the first
 * adds a copy to the deck, up to the most it may have; choosing one in the
 * deck takes a copy out. Above them, the deck's name, and how many units and
 * special cards it has against what a deck needs.
 *
 * The API says what a deck may hold and how many units and special cards it
 * needs (ADR 0002), and checks the deck again when it is saved. Save is
 * turned off until the deck keeps to those numbers.
 *
 * @param faction - The id of the faction's own deck, whose cards it holds.
 * @param deck - The deck to change, or null for a new one.
 * @param onDone - Called once the deck is saved, or the player cancels.
 */
function DeckEditor({
  api,
  faction,
  factionName,
  deck,
  onDone,
}: {
  api: Api;
  faction: string;
  factionName: string;
  deck: PlayerDeck | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const nameId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  const [name, setName] = useState(deck?.name ?? `My ${factionName}`);
  const [copies, setCopies] = useState<Record<string, number>>(
    deck?.copies ?? {},
  );
  const choices = useQuery(choicesQuery(api, faction));
  const save = useMutation({
    mutationFn: () =>
      saveDeck(api, deck?.id ?? null, {
        name: name.trim(),
        deck: faction,
        copies,
      }),
    onSuccess: () => {
      forgetDecks(queryClient);
      onDone();
    },
  });

  const count = (choice: Choice) => copies[choice.card.id] ?? 0;
  const change = (choice: Choice, by: number) => {
    setCopies((now) => {
      const n = (now[choice.card.id] ?? 0) + by;
      // A card that isn't chosen is left out, never chosen 0 times (the API
      // turns that down).
      const others = Object.entries(now).filter(
        ([id]) => id !== choice.card.id,
      );
      return Object.fromEntries(
        n > 0 ? [...others, [choice.card.id, n]] : others,
      );
    });
  };

  return (
    <section className="wood mx-auto flex max-w-5xl flex-col gap-4 rounded-xl border-2 border-wood-600 p-4 shadow-2xl shadow-black/60 sm:p-6">
      <h2
        ref={heading}
        tabIndex={-1}
        className="text-center font-display text-2xl text-gold-300 outline-none"
      >
        {deck === null ? `New ${factionName} deck` : `Change ${deck.name}`}
      </h2>
      {choices.isPending && <p className="italic">Loading the cards…</p>}
      {choices.isError && (
        <>
          <p role="alert" className={ALERT}>
            {choices.error.message}
          </p>
          <button
            type="button"
            className={BUTTON}
            onClick={() => {
              void choices.refetch();
            }}
          >
            Try again
          </button>
        </>
      )}
      {choices.isSuccess && (
        <Columns
          cards={choices.data.cards}
          count={count}
          minUnits={choices.data.min_units}
          maxSpecials={choices.data.max_specials}
          onAdd={(choice) => {
            change(choice, 1);
          }}
          onRemove={(choice) => {
            change(choice, -1);
          }}
        >
          {(valid) => (
            <form
              className="flex flex-wrap items-end justify-center gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                save.mutate();
              }}
            >
              <label htmlFor={nameId} className="flex flex-col text-sm">
                Name
                <input
                  id={nameId}
                  required
                  maxLength={30}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                  }}
                  className="rounded-md border border-gold-600 bg-wood-900 px-2 py-1 text-parchment focus-visible:outline-2 focus-visible:outline-gold-300"
                />
              </label>
              <button
                type="submit"
                className={BUTTON}
                disabled={!valid || name.trim() === "" || save.isPending}
              >
                Save
              </button>
              <button type="button" className={BUTTON} onClick={onDone}>
                Cancel
              </button>
            </form>
          )}
        </Columns>
      )}
      {save.isError && (
        <p role="alert" className={ALERT}>
          {save.error.message}
        </p>
      )}
    </section>
  );
}

/**
 * The editor's counts and its two columns: the cards the deck may hold, each
 * with how many copies it has of the most, and the cards in the deck. On a
 * narrow screen the deck comes under the cards.
 *
 * @param children - What goes between the counts and the columns, given
 *   whether the deck keeps to the numbers: the name and the buttons.
 */
function Columns({
  cards,
  count,
  minUnits,
  maxSpecials,
  onAdd,
  onRemove,
  children,
}: {
  cards: Choice[];
  count: (choice: Choice) => number;
  minUnits: number;
  maxSpecials: number;
  onAdd: (choice: Choice) => void;
  onRemove: (choice: Choice) => void;
  children: (valid: boolean) => ReactNode;
}) {
  const sum = (type: "unit" | "special") =>
    cards
      .filter((choice) => choice.card.type === type)
      .reduce((total, choice) => total + count(choice), 0);
  const units = sum("unit");
  const specials = sum("special");
  const inDeck = cards.filter((choice) => count(choice) > 0);
  return (
    <>
      <p className="text-center" aria-live="polite">
        <span className={units < minUnits ? "text-red-300" : ""}>
          Units: {units} (at least {minUnits})
        </span>
        {" · "}
        <span className={specials > maxSpecials ? "text-red-300" : ""}>
          Special cards: {specials} (at most {maxSpecials})
        </span>
      </p>
      {children(units >= minUnits && specials <= maxSpecials)}
      <div className="grid gap-4 sm:grid-cols-2">
        <CardColumn title="Cards">
          {cards.map((choice) => (
            <ChoiceButton
              key={choice.card.id}
              choice={choice}
              label={`Add ${cardText(choice.card)}, ${String(count(choice))} of ${String(choice.most)}`}
              shown={`${String(count(choice))} / ${String(choice.most)}`}
              disabled={count(choice) >= choice.most}
              onClick={() => {
                onAdd(choice);
              }}
            />
          ))}
        </CardColumn>
        <CardColumn title="Your deck">
          {inDeck.length === 0 ? (
            <li className="italic">Choose cards on the left to add them.</li>
          ) : (
            inDeck.map((choice) => (
              <ChoiceButton
                key={choice.card.id}
                choice={choice}
                label={`Take out ${cardText(choice.card)}, ${String(count(choice))} in the deck`}
                shown={`×${String(count(choice))}`}
                disabled={false}
                onClick={() => {
                  onRemove(choice);
                }}
              />
            ))
          )}
        </CardColumn>
      </div>
    </>
  );
}

/** One of the editor's columns: a heading and a list of cards. */
function CardColumn({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gold-600/60 bg-wood-950/40 p-2">
      <h3
        id={id}
        className="font-display text-sm tracking-widest text-gold-300 uppercase"
      >
        {title}
      </h3>
      <ul aria-labelledby={id} className="flex flex-wrap gap-2">
        {children}
      </ul>
    </div>
  );
}

/** A card in one of the editor's columns, as a button, with its count under it. */
function ChoiceButton({
  choice,
  label,
  shown,
  disabled,
  onClick,
}: {
  choice: Choice;
  label: string;
  shown: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
        className="flex flex-col items-center gap-0.5 rounded-md p-0.5 hover:bg-wood-700 focus-visible:outline-2 focus-visible:outline-gold-300 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <CardFace card={choice.card} name={cardText(choice.card)} />
        <span aria-hidden="true" className="text-xs">
          {shown}
        </span>
      </button>
    </li>
  );
}
