#!/usr/bin/env bash
# usage: run.sh NAME "VARIANT" FIRST SECOND BASE CHUNKS [DECK]
# Plays CHUNKS chunks of 20 matches, seeds BASE+k, 4 at a time, into out/NAME/.
# Chunks already saved are skipped, so a run can be resumed.
set -u
name=$1 variant=$2 first=$3 second=$4 base=$5 chunks=$6 deck=${7:-}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/out/$name"
for k in $(seq 0 $((chunks - 1))); do
  f="$here/out/$name/$k.json"
  [ -f "$f" ] && continue
  echo "VARIANT='$variant' uv run --project \"$CODE\" python \"$here/chunk.py\" \"$f\" $first $second $((base + k)) $deck"
done | xargs -P 4 -I{} bash -c "cd \"$here\" && {}"
