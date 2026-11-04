"""Play one chunk of 20 matches and save the tally as JSON.

usage: chunk.py OUT FIRST SECOND SEED [DECK]
(a): hard normal  -> the variant against main's Hard.
(b): hard hard --deck spies.json -> the variant on both sides; control: normal normal.
"""

import dataclasses
import json
import os
import sys

from rowen.cli import arena

import variants

arena.choose = variants.choose
out, first, second, seed = sys.argv[1:5]
deck = arena.read_deck(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else None
# ROBOTS_DECK: a built Robots deck played instead of the faction's own.
if os.environ.get("ROBOTS_DECK"):
    robots, real = arena.read_deck(os.environ["ROBOTS_DECK"]), arena.load_deck
    arena.load_deck = lambda deck_id: robots if deck_id == "robots" else real(deck_id)
tally = arena.run(first, second, 20, int(seed), lambda line: None, deck)
with open(out, "w") as file:
    json.dump(dataclasses.asdict(tally), file)
