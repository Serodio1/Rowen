/**
 * The tutorial: a match the backend recorded from the engine
 * (`rowen.api.tutorial`), played back in the page with no API call.
 */
import type { Played, View } from "./api/client.ts";

/**
 * One step: the balloon's text and its target (a `data-tutorial` on the
 * board), the board before the step, with the one move asked as its only
 * legal action (none when the step only explains), and the moves the step
 * plays: the player's, if any, then the AI's.
 */
export interface TutorialStep {
  text: string;
  target: string;
  view: View;
  moves: Played["moves"];
}

export interface Tutorial {
  steps: TutorialStep[];
}

/** Load the recording, in its own chunk, only when the tutorial opens. */
export async function loadTutorial(): Promise<Tutorial> {
  const json: unknown = (await import("./tutorial.json")).default;
  // The backend writes it in the API's shapes, and a test checks it is up
  // to date; JSON's types would only say `string` where the API has unions.
  return json as Tutorial;
}
