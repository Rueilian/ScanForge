#!/usr/bin/env bash
# Synthesize ITC'99 circuits to base-gate NanGate45 Verilog (DFFR raw output).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RTL_DIR="$REPO_ROOT/itc99_synth_rtl"
OUT_DIR="$REPO_ROOT/FAN_ATPG/mod_netlist"
LIBERTY="$REPO_ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib"
LOG_DIR="$REPO_ROOT/logs/synth"

export PATH="${HOME}/local/bin:${PATH:-}"

mkdir -p "$LOG_DIR" "$OUT_DIR"

if [[ ! -f "$LIBERTY" ]]; then
  python3 "$REPO_ROOT/scripts/gen_base_liberty.py"
fi

if ! command -v yosys >/dev/null; then
  echo "ERROR: yosys not found in PATH" >&2
  exit 1
fi

TARGETS=(
  "b03:b03"
  "b04:b04"
  "b05:b05"
  "b07:b07"
  "b08:b08"
  "b09:b09"
  "b11:b11"
  "b12:b12"
  "b13:b13"
  "b14:b14"
  "b15:b15"
)

FAIL=0

for entry in "${TARGETS[@]}"; do
  IFS=: read -r cname module <<< "$entry"
  rtl="$RTL_DIR/${cname}.v"
  out="$OUT_DIR/${cname}_dffr.v"
  log="$LOG_DIR/${cname}.log"

  if [[ ! -f "$rtl" ]]; then
    echo "SKIP $cname: RTL not found at $rtl" >&2
    FAIL=1
    continue
  fi

  echo -n "Synthesizing $cname ($module) ... "

  yosys -p "
    read_verilog -sv $rtl;
    hierarchy -check -top $module;
    synth -top $module -flatten;
    dfflibmap -liberty $LIBERTY;
    abc -liberty $LIBERTY;
    splitnets;
    opt_clean;
    opt -fast;
    check -noinit;
    write_verilog -noattr $out;
  " >"$log" 2>&1 || {
    echo "FAILED — see $log"
    FAIL=1
    continue
  }

  if grep -qE '\b(OAI[0-9]+|AOI[0-9]+)_X[0-9]+\s+\w+\s*\(' "$out"; then
    echo "FAILED — OAI/AOI compound cells in $out"
    FAIL=1
    continue
  fi

  ff_count=$(grep -cE 'DFFR_X[12]' "$out" 2>/dev/null | tr -d '\n' || true)
  mux_count=$(grep -cE 'MUX2_X1' "$out" 2>/dev/null | tr -d '\n' || true)
  ff_count=${ff_count:-0}
  mux_count=${mux_count:-0}
  echo "OK (DFFR=$ff_count MUX2=$mux_count → $out)"
done

echo ""
if [[ "$FAIL" -ne 0 ]]; then
  echo "Synthesis finished with failures. See $LOG_DIR/" >&2
  exit 1
fi
echo "Synthesis complete. Output: $OUT_DIR/*_dffr.v"
