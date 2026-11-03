#!/usr/bin/env bash
# Round 5: the controls again, then redraw and scare on top of giveup,cards.
# usage: CODE=<copy of main>/backend round5.sh   (~75 min on 4 cores; resumable)
set -u
here=$(cd "$(dirname "$0")" && pwd)
R=$here/run.sh D=$CODE/../docs/decks/spies.json
$R a-control "" hard normal 3000 20
$R b-control "" normal normal 4000 16 "$D"
$R a-giveup-cards "giveup,cards" hard normal 3000 20
$R b-giveup-cards "giveup,cards" hard hard 4000 16 "$D"
$R a-gc-redraw "giveup,cards,redraw" hard normal 3000 20
$R b-gc-redraw "giveup,cards,redraw" hard hard 4000 16 "$D"
$R a-gc-scare "giveup,cards,scare" hard normal 3000 20
$R b-gc-scare "giveup,cards,scare" hard hard 4000 16 "$D"
echo ALLDONE
