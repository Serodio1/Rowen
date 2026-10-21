import type { ReactNode } from "react";

/**
 * The game's icons, drawn for Rowen: lines on a 24 × 24 grid, in the colour
 * of the text around them. None comes from The Witcher 3 or from an icon
 * library.
 *
 * To add one, add its name and its lines here: TypeScript then asks for it
 * wherever every icon must be listed.
 */
const ICONS = {
  // The rows.
  melee: (
    // A sword: the blade, the guard and the grip.
    <>
      <path d="M20 4 9.5 14.5" />
      <path d="M20 4v3.5L11 16.5" />
      <path d="M6 12l6 6" />
      <path d="M8.5 15.5 4 20" />
    </>
  ),
  ranged: (
    // A bow, drawn, with its arrow.
    <>
      <path d="M8 3c6 3.5 6 14.5 0 18" />
      <path d="M8 3v18" />
      <path d="M3 12h17M17 9l3 3-3 3" />
    </>
  ),
  siege: (
    // A tower with battlements.
    <path d="M6 21V6h2.5v2.5h2V6h3v2.5h2V6H18v15zM10 21v-4a2 2 0 0 1 4 0v4" />
  ),

  // The abilities of units.
  agile: (
    // Two arrows, each the other way: it goes in either row.
    <>
      <path d="M4 8h14M14 4l4 4-4 4" />
      <path d="M20 16H6M10 12l-4 4 4 4" />
    </>
  ),
  spy: (
    // An eye.
    <>
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  medic: (
    // A cross.
    <path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z" />
  ),
  muster: (
    // Three figures together.
    <>
      <circle cx="12" cy="7" r="2.5" />
      <circle cx="5.5" cy="9.5" r="2" />
      <circle cx="18.5" cy="9.5" r="2" />
      <path d="M7.5 20a4.5 4.5 0 0 1 9 0" />
      <path d="M2 19a3.5 3.5 0 0 1 4-3.4M22 19a3.5 3.5 0 0 0-4-3.4" />
    </>
  ),
  bond: (
    // Two links of a chain.
    <>
      <path d="M10 14a4 4 0 0 1 0-5.7l2.3-2.3a4 4 0 0 1 5.7 5.7l-1.2 1.2" />
      <path d="M14 10a4 4 0 0 1 0 5.7l-2.3 2.3a4 4 0 0 1-5.7-5.7l1.2-1.2" />
    </>
  ),
  inspire: (
    // A banner on its pole.
    <>
      <path d="M6 21V3" />
      <path d="M6 4h12l-3 4.5 3 4.5H6" />
    </>
  ),

  // The special cards.
  hoarfrost: (
    // A snowflake.
    <>
      <path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7" />
      <path d="M9.5 3.5 12 6l2.5-2.5M9.5 20.5 12 18l2.5 2.5" />
    </>
  ),
  "thick-fog": (
    // Banks of fog.
    <path d="M3 8h11M17 8h4M5 12h14M3 16h4M10 16h11M6 20h10" />
  ),
  downpour: (
    // A cloud, and rain.
    <>
      <path d="M7 14a4 4 0 0 1-.6-8A5.5 5.5 0 0 1 17 6.5a3.8 3.8 0 0 1 0 7.5z" />
      <path d="M8 17.5 7 20.5M12 17.5l-1 3M16 17.5l-1 3" />
    </>
  ),
  "clear-skies": (
    // The sun.
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
    </>
  ),
  "war-horn": (
    // A horn, wide at its mouth.
    <path d="M3 10h4l12-6v16L7 14H3zM7 14l1.5 6" />
  ),
  wildfire: (
    // A flame.
    <path d="M12 2.5c.7 3.8 6 5.8 6 11.5a6 6 0 0 1-12 0c0-2.8 1.6-4.6 2.8-6.3.2 1.9 1 3 2.2 3.3.1-3.2-.9-5.2 1-8.5z" />
  ),
  scarecrow: (
    // A scarecrow on its post.
    <>
      <circle cx="12" cy="5" r="2.5" />
      <path d="M12 7.5V22M4 11h16M8 11l-1 6M16 11l1 6" />
    </>
  ),
} satisfies Record<string, ReactNode>;

/** The name of one of the game's icons, such as `"melee"` or `"spy"`. */
export type IconName = keyof typeof ICONS;

/**
 * One of the game's icons.
 *
 * It is only a picture: screen readers skip it, so what it means must be in
 * words nearby, such as the card's name for screen readers in `CardFace`.
 *
 * @param className - Its size and colour, such as `"size-4 text-gold-200"`.
 */
export function Icon({
  name,
  className,
}: {
  name: IconName;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      data-icon={name}
      className={className}
    >
      {ICONS[name]}
    </svg>
  );
}
