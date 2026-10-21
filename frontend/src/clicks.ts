import type { MouseEvent } from "react";

/**
 * Return a click handler that ignores the second click of a double click.
 *
 * The answer to the first click can come before the second, and change what
 * is under the mouse: the second click would land on a move of the next
 * view, or on a deck once the player chose to play again. And a card chosen
 * by the first click would be played by the second. (`detail` counts the
 * clicks in a row, and a key press gives 0. Some systems count a fourth
 * quick click as 1 again: this stops double and triple clicks.)
 */
export function onFirstClick(onClick: () => void) {
  return (event: MouseEvent) => {
    if (event.detail > 1) {
      return;
    }
    onClick();
  };
}
