# The cards' art

Each card shows a picture over its face; the frame, the strength, the icons
and the name are drawn by the page, from the card's data
(`frontend/src/CardFace.tsx`).

## Where it comes from

Rui Vasconcelos generated the 25 pictures of the cards with AI tools on
21 October 2026, and the 2 of the leaders on 29 October 2026, from prompts
written for Rowen:

| Tool | Cards |
| --- | --- |
| [Grok](https://grok.com/), by xAI | Human, Soldier, Sniper, Informant, Medic, Smart Guy, Plane |
| [Gemini](https://gemini.google.com/), by Google | all the others: the rest of the Humans, the Robots and the special cards, and both leaders (The Commander, The Overseer) |

Every prompt asked for an original design, with no text, frame or logo, and
named no game. No picture, icon or font comes from The Witcher 3 or from
GWENT.

Each prompt was the same description of the style, then one sentence on the
card, such as *"a human field medic kneeling, bandaging a wounded comrade, a
medical bag beside her. Warm golden tones."* The style:

> Vertical portrait illustration, 2:3 aspect ratio, high resolution. Painted
> semi-realistic digital art, rich textures, dramatic side lighting, dark muted
> background, cohesive style for a collectible card game. The main subject is
> centered in the middle of the image; keep the top-left corner, the top-right
> corner and the bottom fifth of the image free of important details. No text,
> no letters, no numbers, no logos, no watermark, no border, no frame, no card
> layout. Original design, not based on any existing game.

## Terms

- **Grok:** xAI's [consumer terms](https://x.ai/legal/terms-of-service) leave
  the ownership of what a user generates with the user, as far as the law
  allows, and its [FAQ](https://x.ai/legal/faq) asks for the work to be
  attributed to Grok: these pictures were created with Grok.
- **Gemini:** [Google's terms](https://policies.google.com/terms) say that
  Google doesn't claim ownership of the original content its services
  generate for a user.

The same or similar pictures may be generated for someone else, and whether a
picture made by AI can be copyrighted depends on the country. The [MIT
License](../LICENSE) covers the code; the art is here to be shown with the
game.

## Adding or changing art

1. Make a picture for the card or leader, upright (2:3, or close: it is cut around its
   middle), with nothing important in the top corners or the bottom fifth.
2. Name it by the card's or leader's id, as in the deck files in
   `backend/src/rowen/data` (`computer-spy.png`, `humans-leader.png`), and put
   it in a folder with the others.
3. From the repository's folder, run:

   ```sh
   uv run scripts/convert_art.py <that folder>
   ```

   It makes `frontend/src/art/<id>.webp` (400 by 600 pixels), refuses a name
   that is no card's id, and lists the cards with no picture yet.
4. Add the tool and the date to the table above.

A backend test (`backend/tests/test_art.py`) fails if a card has no art, or
if a file in `frontend/src/art` is no card's art. A card with no art shows a
placeholder: its row's colour and icon.
