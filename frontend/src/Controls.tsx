import type { View } from "./api/client.ts";
import { onFirstClick } from "./clicks.ts";
import { otherActions, playsOf, selfPlay, type Playing } from "./plays.ts";
import { BUTTON } from "./styles.ts";
import { actionText, cardNames } from "./text.ts";

/**
 * What the player is to do now, in words, and the moves that are no card:
 * passing, or keeping the hand before round 1. While a card is chosen, a
 * button lets it go (as Escape does on the board). On the AI's turn, that
 * it is, and while it plays (`thinking`), that the AI is thinking.
 */
export function Controls({
  view,
  playing,
  thinking,
}: {
  view: View;
  playing: Playing;
  thinking: boolean;
}) {
  const names = cardNames(view);
  const chosen = playing.chosen;
  const name = chosen === null ? "" : (names.get(chosen.card) ?? chosen.card);
  let hint = "Choose a card to play, or pass.";
  if (thinking) {
    // The answer comes once the AI has made its moves.
    hint = "The AI is thinking…";
  } else if (view.current !== view.player) {
    // Until the player's move has played out: the AI thinks after it.
    hint = "The AI's turn.";
  } else if (view.reviving) {
    hint =
      chosen === null
        ? "Choose a unit to revive."
        : `Choose the row to revive ${name} in.`;
  } else if (
    view.legal_actions.some((action) => action.type === "end_redraw")
  ) {
    hint =
      chosen === null
        ? "Choose a card to swap, or keep this hand."
        : `Choose ${name} again to swap it.`;
  } else if (
    chosen !== null &&
    selfPlay(playsOf(view.legal_actions, chosen.card)) !== undefined
  ) {
    // Weather, Clear Skies and Wildfire have nowhere to choose: choosing
    // the card again, with a click or the keyboard, plays it.
    hint = `Choose ${name} again to play it.`;
  } else if (chosen !== null) {
    // A Scarecrow goes in the place of a unit, which it takes back.
    const scarecrow = view.hand.some(
      (card) =>
        card.id === chosen.card &&
        card.type === "special" &&
        card.kind === "scarecrow",
    );
    hint = scarecrow
      ? `Choose a unit to take back with ${name}, or choose ${name} again to put it back.`
      : `Choose where to play ${name}, or choose it again to put it back.`;
  }
  return (
    <div className="flex flex-col items-center gap-2">
      <p className="text-center text-sm text-gold-200">{hint}</p>
      <div
        role="group"
        aria-label="Moves"
        className="flex flex-wrap justify-center gap-2"
      >
        {chosen !== null && (
          <button
            type="button"
            className={BUTTON}
            aria-keyshortcuts="Escape"
            disabled={playing.disabled}
            onClick={() => {
              playing.onChoose(null);
            }}
          >
            Cancel
          </button>
        )}
        {otherActions(view.legal_actions).map((action) => (
          <button
            key={action.type}
            type="button"
            className={BUTTON}
            disabled={playing.disabled}
            onClick={onFirstClick(() => {
              playing.onPlay(action);
            })}
          >
            {actionText(action, names)}
          </button>
        ))}
      </div>
    </div>
  );
}
