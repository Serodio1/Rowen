#!/usr/bin/env bash
# Round 9: Robots decks with 3 Wards against the Spies deck, then the
# anti-Spy decks against the Humans' own deck (is the deck too strong?).
# usage: CODE=<copy of main>/backend round9.sh   (resumable)
set -u
here=$(cd "$(dirname "$0")" && pwd)
R=$here/run.sh D=$CODE/../docs/decks/spies.json
V="giveup,cards,ward,scareback,spyfirst,medicspy,revivespy,robotsonly"
ROBOTS_DECK=$here/robots-ward3.json $R b-ward3 "$V" hard hard 4000 16 "$D"
ROBOTS_DECK=$here/robots-antispy-ward3.json $R b-antispy-ward3 "$V" hard hard 4000 16 "$D"
ROBOTS_DECK=$here/robots-antispy.json $R c-antispy "$V" hard hard 4000 16 -
ROBOTS_DECK=$here/robots-antispy-ward3.json $R c-antispy-ward3 "$V" hard hard 4000 16 -
echo ALLDONE
