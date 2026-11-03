export type Side = "top" | "right" | "bottom" | "left";

const OPPOSITE: Record<Side, Side> = {
  top: "bottom",
  bottom: "top",
  left: "right",
  right: "left",
};

/** The balloon's edge the arrow sits on: the one facing the target. */
export function arrowSide(placement: string): Side {
  return OPPOSITE[placement.split("-")[0] as Side];
}
