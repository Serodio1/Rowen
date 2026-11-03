import type { Event } from "./api/client.ts";

/** The end of a round, as the API sends it. */
export type RoundEnded = Extract<Event, { type: "round_ended" }>;

/**
 * How each round went, in a table: the player's score, the AI's and who
 * won it.
 *
 * @param viewer - The player of the view: 0 or 1.
 */
export function Rounds({
  rounds,
  viewer,
}: {
  rounds: readonly RoundEnded[];
  viewer: number;
}) {
  return (
    <table className="w-full text-center">
      <caption className="sr-only">The rounds</caption>
      <thead className="font-display text-sm text-gold-300">
        <tr>
          <th scope="col">Round</th>
          <th scope="col">You</th>
          <th scope="col">The AI</th>
          <th scope="col">Won by</th>
        </tr>
      </thead>
      <tbody>
        {rounds.map((round, index) => (
          <tr key={index} className="border-t border-gold-600/60">
            <th scope="row" className="py-1 font-normal">
              {index + 1}
            </th>
            <td>{round.scores[viewer]}</td>
            <td>{round.scores[1 - viewer]}</td>
            <td>
              {round.winner === null
                ? "Tie"
                : round.winner === viewer
                  ? "You"
                  : "The AI"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
