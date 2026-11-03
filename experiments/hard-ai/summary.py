"""Sum the chunks of each run in out/: the first AI's share of decisive wins, ±95%."""

import json
import math
import pathlib

for run in sorted(pathlib.Path(__file__).parent.glob("out/*")):
    t = [json.loads(f.read_text()) for f in run.glob("*.json")]
    w, l, d = (sum(x[k] for x in t) for k in ("wins", "losses", "draws"))
    decks = {}
    for x in t:
        for deck, n in x["deck_wins"].items():
            decks[deck] = decks.get(deck, 0) + n
    n = w + l
    p = w / n if n else 0
    m = 1.96 * math.sqrt(p * (1 - p) / n) if n else 0
    shares = ", ".join(f"{k} {v / n:.1%}" for k, v in sorted(decks.items())) if n else ""
    print(f"{run.name}: {w + l + d} matches, first {p:.1%} ± {m:.1%} ({d} drawn); {shares}")
