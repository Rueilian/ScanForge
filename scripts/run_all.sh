#!/usr/bin/env bash
# run_all.sh — Run FAN_ATPG on all 12 ISCAS'89 circuits then sweep partial scan
# Usage:  bash scripts/run_all.sh [--sweep | --mode <co|combined|combined_wear|random>]

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
FAN="$ROOT/FAN_ATPG"
SF="$ROOT/src/scanforge"
CIRCUITS="s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584"

MODE="co"
SWEEP_FLAG=""
for arg in "$@"; do
  case $arg in
    --sweep) SWEEP_FLAG="--sweep" ;;
    --mode) shift; MODE="$1" ;;
    --mode=*) MODE="${arg#*=}" ;;
  esac
done

echo "====  ScanForge — run_all.sh  ===="
echo "  Circuits  : $CIRCUITS"
echo "  Mode      : $MODE"
echo "  Sweep     : ${SWEEP_FLAG:-off}"
echo ""

# Step 1: build FAN_ATPG if binary missing
if [ ! -x "$FAN/bin/opt/fan" ]; then
  echo "[1/3] Building FAN_ATPG..."
  (cd "$FAN" && make -j4)
else
  echo "[1/3] FAN_ATPG binary found, skipping build."
fi

# Step 2: build ScanForge if binary missing
if [ ! -x "$ROOT/src/scanforge" ]; then
  echo "[2/3] Building ScanForge..."
  (cd "$ROOT/src" && make)
else
  echo "[2/3] ScanForge binary found, skipping build."
fi

# Step 3: run each circuit
echo "[3/3] Running circuits..."
mkdir -p "$FAN/results"
for s in $CIRCUITS; do
  printf "  %-10s " "$s"
  (cd "$FAN" && ./bin/opt/fan -f "script/fanScripts/atpg_$s.script" 2>&1 | grep -q "Goodbye" && echo "ATPG OK") || echo "ATPG FAILED"
done

echo ""
echo "====  ScanForge Analysis  ===="
for s in $CIRCUITS; do
  echo ""
  echo "--- $s ---"
  $SF "$FAN/results/$s.sf" ${SWEEP_FLAG:---sweep} --mode "$MODE"
done
