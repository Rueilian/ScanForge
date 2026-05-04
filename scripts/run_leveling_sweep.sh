#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCANFORGE="${ROOT}/src/scanforge"

CIRCUITS=("s953" "s5378" "s9234")
MODES=("combined" "combined_wear" "combined_wear_leveling")
LAMBDAS=("0.0" "0.25" "0.5" "0.75" "1.0")
WINDOWS=("8" "16")

mkdir -p "${ROOT}/results/leveling"

for c in "${CIRCUITS[@]}"; do
  sf="${ROOT}/FAN_ATPG/results/${c}.sf"
  if [[ ! -f "$sf" ]]; then
    echo "Skip ${c}: missing $sf (build FAN_ATPG and generate .sf first)" >&2
    continue
  fi
  for mode in "${MODES[@]}"; do
    for lam in "${LAMBDAS[@]}"; do
      for w in "${WINDOWS[@]}"; do
        out="${ROOT}/results/leveling/${c}_${mode}_lam${lam}_w${w}.csv"
        "${SCANFORGE}" "$sf" \
          --sweep \
          --mode "${mode}" \
          --lambda "${lam}" \
          --segment-window "${w}" \
          --summary-csv "$out"
      done
    done
  done
done
