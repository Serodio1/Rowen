#!/usr/bin/env bash
# Round 7: is it the Spies deck? (Easy, Normal) Then the anti-Spy rules and
# deck on top of giveup,cards,ward.
# usage: CODE=<copy of main>/backend round7.sh   (resumable)
set -u
here=$(cd "$(dirname "$0")" && pwd)
R=$here/run.sh D=$CODE/../docs/decks/spies.json A=$here/robots-antispy.json
G="giveup,cards,ward" X="scareback,spyfirst,medicspy,revivespy"
$R b-easy "" easy easy 4000 16 "$D"
$R b-normal8 "" normal8 normal8 4000 16 "$D"
ROBOTS_DECK=$A $R b-gcw-antispy "$G" hard hard 4000 16 "$D"
$R b-gcw-rules "$G,$X" hard hard 4000 16 "$D"
ROBOTS_DECK=$A $R b-gcw-rules-antispy "$G,$X" hard hard 4000 16 "$D"
$R a-gcw-rules "$G,$X" hard normal 3000 20
echo ALLDONE
