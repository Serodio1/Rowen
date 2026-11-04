#!/usr/bin/env bash
# Round 8: the anti-Spy rules only on the Robots' side, as with a person
# playing the Spies deck against the Hard AI.
# usage: CODE=<copy of main>/backend round8.sh   (resumable)
set -u
here=$(cd "$(dirname "$0")" && pwd)
R=$here/run.sh D=$CODE/../docs/decks/spies.json A=$here/robots-antispy.json
V="giveup,cards,ward,scareback,spyfirst,medicspy,revivespy,robotsonly"
ROBOTS_DECK=$A $R b-gcw-robotsrules-antispy "$V" hard hard 4000 16 "$D"
$R b-gcw-robotsrules "$V" hard hard 4000 16 "$D"
echo ALLDONE
