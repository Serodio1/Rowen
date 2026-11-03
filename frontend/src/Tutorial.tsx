import { useEffect, useId, useState, type ReactNode } from "react";
import type { Event } from "./api/client.ts";
import { Balloon } from "./Balloon.tsx";
import { Board } from "./Board.tsx";
import { onFirstClick } from "./clicks.ts";
import { Controls } from "./Controls.tsx";
import type { Chosen, Playing } from "./plays.ts";
import { Rounds } from "./Rounds.tsx";
import { Banner, Showcase } from "./Showcase.tsx";
import {
  mayMove,
  NO_STEPS,
  stageOf,
  stepsOfMoves,
  usePlayOut,
  viewAt,
  type Step,
} from "./stage.ts";
import { BUTTON, PANEL } from "./styles.ts";
import { loadTutorial, type Tutorial as Recording } from "./tutorial.ts";

/**
 * The tutorial: a recorded match played back on the board, one step at a
 * time. Each step's balloon says what to do; only the move it asks for is
 * lit (or Next, when it only explains). Nothing goes to the server, and
 * nothing is saved.
 *
 * @param onLeave - Called to go back to the main menu.
 * @param onPlay - Called to start a real match, once the tutorial is over.
 */
export function Tutorial({
  onLeave,
  onPlay,
}: {
  onLeave: () => void;
  onPlay: () => void;
}) {
  const [recording, setRecording] = useState<Recording | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    loadTutorial().then(
      (loaded) => {
        if (live) {
          setRecording(loaded);
        }
      },
      () => {
        if (live) {
          setFailed(true);
        }
      },
    );
    return () => {
      live = false;
    };
  }, []);

  const leave = (
    <button type="button" className={BUTTON} onClick={onLeave}>
      Leave tutorial
    </button>
  );
  if (recording === null) {
    return (
      <section className={PANEL}>
        <p role={failed ? "alert" : undefined}>
          {failed
            ? "The tutorial couldn't load. Check the connection."
            : "Loading the tutorial…"}
        </p>
        {leave}
      </section>
    );
  }
  return (
    <Steps
      recording={recording}
      leave={leave}
      onLeave={onLeave}
      onPlay={onPlay}
    />
  );
}

function Steps({
  recording: { steps },
  leave,
  onLeave,
  onPlay,
}: {
  recording: Recording;
  leave: ReactNode;
  onLeave: () => void;
  onPlay: () => void;
}) {
  // The step shown: `steps.length` once all are played.
  const [at, setAt] = useState(0);
  const [chosen, setChosen] = useState<Chosen | null>(null);
  // The animation of the last step's moves: none with reduced motion.
  const [animation, setAnimation] = useState<readonly Step[]>(NO_STEPS);
  const progress = usePlayOut(animation);
  const busy = progress.step < animation.length;
  const showing = animation[progress.step];
  const resultId = useId();

  const step = steps[at];
  const last = steps.at(-1)?.moves.at(-1)?.view;
  const view = step?.view ?? last;
  if (view === undefined) {
    // An empty recording: the backend's tests rule it out.
    return leave;
  }
  /** Play the step's moves, then show the next step. */
  function advance() {
    if (step === undefined) {
      return;
    }
    setChosen(null);
    setAnimation(mayMove() ? stepsOfMoves(step.moves, step.view) : NO_STEPS);
    setAt(at + 1);
  }
  // While moves play out, the board shows the match as it was then.
  const then = viewAt(animation, progress);
  const board =
    then === undefined
      ? view
      : { ...view, round: then.round, players: then.players };
  const playing: Playing = {
    // The recording cut them to the one move asked.
    actions: view.legal_actions,
    chosen,
    disabled: busy,
    onChoose: setChosen,
    onPlay: advance,
  };
  const over = view.match_over && !busy;
  const rounds = steps
    .flatMap((step) => step.moves.flatMap((move) => move.events))
    .filter(
      (event): event is Extract<Event, { type: "round_ended" }> =>
        event.type === "round_ended",
    );

  return (
    <section className="flex flex-col gap-3">
      <div
        className="flex flex-wrap items-center justify-between gap-2"
        inert={over}
      >
        <h2 className="font-display text-xl text-gold-300 lg:text-2xl">
          Tutorial · Round {board.round}
        </h2>
        {leave}
      </div>
      <div inert={over}>
        <Board
          view={board}
          playing={view.match_over ? undefined : playing}
          stage={stageOf(animation, progress)}
        />
        {showing?.kind === "announce" && <Banner text={showing.text} />}
        {showing?.kind === "play" && (
          // A new element for each card, which comes up from nothing.
          <Showcase
            key={progress.step}
            step={showing}
            flying={progress.flying}
          />
        )}
      </div>
      {!view.match_over && (
        <Controls view={view} playing={playing} thinking={false} />
      )}
      {/* Mounted all along, so its status region reads each new step. */}
      <Balloon
        target={step?.target ?? ""}
        text={step?.text ?? ""}
        shown={step !== undefined && !busy}
        onNext={step?.view.legal_actions.length === 0 ? advance : undefined}
      />
      {over && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={resultId}
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
        >
          <div className="wood flex w-full max-w-md flex-col items-center gap-4 rounded-xl border-2 border-gold-400 p-6 shadow-2xl shadow-black">
            <h2
              id={resultId}
              className="text-center font-display text-3xl text-gold-200"
            >
              Tutorial complete
            </h2>
            <Rounds rounds={rounds} viewer={view.player} />
            <div className="flex flex-wrap justify-center gap-2">
              <button
                type="button"
                className={BUTTON}
                autoFocus
                // The second click of a double click on the last move could
                // land here.
                onClick={onFirstClick(onPlay)}
              >
                Play a match
              </button>
              <button
                type="button"
                className={BUTTON}
                onClick={onFirstClick(onLeave)}
              >
                Return to main menu
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
