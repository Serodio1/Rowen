import { ALERT, BUTTON } from "./styles.ts";

/** Say why something didn't come, with a button to ask for it again. */
export function Failed({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}) {
  return (
    <>
      <p role="alert" className={ALERT}>
        {error.message}
      </p>
      <button type="button" className={BUTTON} onClick={onRetry}>
        Try again
      </button>
    </>
  );
}
