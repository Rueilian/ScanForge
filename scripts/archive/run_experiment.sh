#!/bin/bash
# Run full experiment matrix: 12 circuits × 7 modes × λ sweep × segment window
# Output: results/experiments/<circuit>_<mode>_l<lambda>_w<window>.csv

set -e
SCANFORGE="$(dirname "$0")/../src/scanforge"
SF_DIR="$(dirname "$0")/../FAN_ATPG/results"
OUT_DIR="$(dirname "$0")/../results/experiments"
mkdir -p "$OUT_DIR"

CIRCUITS="s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584"
MODES="random co combined co_wear combined_wear co_wear_leveling combined_wear_leveling"
LAMBDAS="0.0 0.25 0.5 0.75 1.0"
WINDOW=16

total=0; done_count=0
for c in $CIRCUITS; do for m in $MODES; do for l in $LAMBDAS; do total=$((total+1)); done; done; done

for circuit in $CIRCUITS; do
    sf="$SF_DIR/${circuit}.sf"
    if [ ! -f "$sf" ]; then echo "SKIP $circuit (no .sf)"; continue; fi

    for mode in $MODES; do
        for lambda in $LAMBDAS; do
            # wear-unrelated modes: only run λ=0.5 to avoid redundant rows
            if [[ "$mode" == "random" || "$mode" == "co" || "$mode" == "combined" ]]; then
                if [ "$lambda" != "0.5" ]; then done_count=$((done_count+1)); continue; fi
            fi

            out="$OUT_DIR/${circuit}_${mode}_l${lambda}_w${WINDOW}.csv"
            "$SCANFORGE" "$sf" \
                --sweep --fine \
                --mode "$mode" \
                --lambda "$lambda" \
                --segment-window $WINDOW \
                --summary-csv "$out" 2>/dev/null

            done_count=$((done_count+1))
            echo "[$done_count/$total] $circuit $mode λ=$lambda → $(basename $out)"
        done
    done
done

echo ""
echo "Done. Results in $OUT_DIR"
echo "CSV count: $(ls $OUT_DIR/*.csv 2>/dev/null | wc -l)"
