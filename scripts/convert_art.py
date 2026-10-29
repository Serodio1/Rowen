# /// script
# requires-python = ">=3.14"
# dependencies = ["pillow==12.3.0"]
# ///
"""Turn the pictures of the cards and leaders into the art the game shows.

Each picture in the folder given is named by a card's or a leader's id, such
as ``human.png`` or ``humans-leader.jpg`` (the ids are in the deck files in
``backend/src/rowen/data``). Each one is cut to the card's shape (2:3, around
its middle), made 400 by 600 pixels and saved as WebP in ``frontend/src/art``,
where the page finds it (``frontend/src/cards.ts``).

Run it from the repository's folder, with uv, which installs Pillow for this
script only::

    uv run scripts/convert_art.py <folder with the pictures>

A picture whose name is not a card's or a leader's id is an error (a typo
would leave its card without art); one with no picture is only listed.
"""

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "src" / "rowen" / "data"
ART = ROOT / "frontend" / "src" / "art"

# The size of the art: twice the largest card on the page, for screens with
# two pixels to each point.
WIDTH, HEIGHT = 400, 600
# WebP's quality, from 0 to 100: 80 looks the same as the picture on a card,
# at about 28 KB each.
QUALITY = 80
PICTURES = {".png", ".jpg", ".jpeg", ".webp"}


def card_ids() -> set[str]:
    """Return the id of every card and leader in the deck files and of the
    special cards.
    """
    ids = {card["id"] for card in json.loads((DATA / "specials.json").read_text())}
    for file in (DATA / "decks").glob("*.json"):
        deck = json.loads(file.read_text())
        ids |= {card["id"] for card in deck["units"]}
        if "leader" in deck:
            ids.add(deck["leader"]["id"])
    return ids


def convert(picture: Path, art: Path) -> None:
    """Cut `picture` to 2:3 around its middle, shrink it and save it as `art`."""
    with Image.open(picture) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        if width * 3 > height * 2:
            # Too wide: keep the middle columns.
            kept = height * 2 // 3
            box = ((width - kept) // 2, 0, (width + kept) // 2, height)
        else:
            # Too tall (or just right): keep the middle rows.
            kept = width * 3 // 2
            box = (0, (height - kept) // 2, width, (height + kept) // 2)
        small = image.crop(box).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        small.save(art, "WEBP", quality=QUALITY, method=6)


def main(folder: Path) -> int:
    """Convert every picture in `folder`; return the exit code."""
    ids = card_ids()
    pictures = sorted(p for p in folder.iterdir() if p.suffix.lower() in PICTURES)
    unknown = [p.name for p in pictures if p.stem not in ids]
    if unknown:
        print(f"Not a card's id: {', '.join(unknown)}", file=sys.stderr)
        return 1
    ART.mkdir(exist_ok=True)
    for picture in pictures:
        convert(picture, ART / f"{picture.stem}.webp")
        print(f"{picture.name} -> frontend/src/art/{picture.stem}.webp")
    missing = sorted(ids - {p.stem for p in pictures})
    if missing:
        print(f"No picture yet for: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: uv run {sys.argv[0]} <folder with the pictures>")
    sys.exit(main(Path(sys.argv[1])))
