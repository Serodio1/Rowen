#!/usr/bin/env bash
# Round 6: ward on top of each base variant given (comma lists), (a) then (b).
# usage: CODE=<copy of main>/backend round6.sh "giveup,cards" ["giveup,cards,redraw" ...]
set -u
here=$(cd "$(dirname "$0")" && pwd)
R=$here/run.sh D=$CODE/../docs/decks/spies.json
for base in "$@"; do
  v="$base,ward" n=$(echo "$base,ward" | tr ',' '-')
  $R "a-$n" "$v" hard normal 3000 20
  $R "b-$n" "$v" hard hard 4000 16 "$D"
done
echo ALLDONE
