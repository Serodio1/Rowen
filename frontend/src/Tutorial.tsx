import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Balloon } from "./Balloon.tsx";
import { Board } from "./Board.tsx";
import { onFirstClick } from "./clicks.ts";
import { Controls } from "./Controls.tsx";
import type { Chosen, Playing } from "./plays.ts";
import { Rounds, type RoundEnded } from "./Rounds.tsx";
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
 * @param onEnded - Called with whether the end of the tutorial is shown
 *   over the whole page, as PlayMatch does.
 */
export function Tutorial({
  onLeave,
  onPlay,
  onEnded,
}: {
  onLeave: () => void;
  onPlay: () => void;
  onEnded: (ended: boolean) => void;
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
        <p role={failed ? "alert" : "status"}>
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
      onEnded={onEnded}
    />
  );
}

function Steps({
  recording: { steps },
  leave,
  onLeave,
  onPlay,
  onEnded,
}: {
  recording: Recording;
  leave: ReactNode;
  onLeave: () => void;
  onPlay: () => void;
  onEnded: (ended: boolean) => void;
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
  // Where the cards and the moves are: the board, and the buttons under it.
  const boardArea = useRef<HTMLDivElement>(null);
  const movesArea = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // As in PlayMatch: once the move asked can be made, the focus goes to
    // the lit card, or else to Pass, unless it is elsewhere (on Next, which
    // the balloon focused on a step that only explains).
    const focused = document.activeElement;
    const areas = [boardArea.current, movesArea.current];
    if (
      !busy &&
      (focused === document.body ||
        areas.some((area) => area?.contains(focused)))
    ) {
      const card = boardArea.current?.querySelector<HTMLElement>(
        "[data-choosable]:not(:disabled)",
      );
      // From nowhere, the page stays where it is (see PlayMatch), except for
      // Pass on a laptop's layout (lg): just under the board, it may be out of
      // sight. On a phone it is far below the balloon, which says why to pass.
      const wide =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(min-width: 64rem)").matches;
      (
        card ??
        movesArea.current?.querySelector<HTMLElement>("button:not(:disabled)")
      )?.focus({
        preventScroll: focused === document.body && (card !== null || !wide),
      });
    }
  }, [at, busy]);

  const step = steps[at];
  const last = steps.at(-1)?.moves.at(-1)?.view;
  const view = step?.view ?? last;
  const over = view?.match_over === true && !busy;
  useEffect(() => {
    onEnded(over);
    // Left by any button, it is no longer shown.
    return () => {
      onEnded(false);
    };
  }, [over, onEnded]);
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
  const rounds = steps
    .flatMap((step) => step.moves.flatMap((move) => move.events))
    .filter((event): event is RoundEnded => event.type === "round_ended");

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
      <div ref={boardArea} inert={over}>
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
      <div ref={movesArea}>
        {!view.match_over && (
          <Controls view={view} playing={playing} thinking={false} />
        )}
      </div>
      {/* Mounted all along, so its status region reads each new step. */}
      <Balloon
        // Once a card is chosen, it points at where the card goes, so it
        // doesn't cover it (above the hand, it covered the row next to it).
        target={
          chosen === null
            ? `[data-tutorial="${step?.target ?? ""}"]`
            : "[data-target]"
        }
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
