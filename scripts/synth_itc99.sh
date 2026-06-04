#!/usr/bin/env bash
# Synthesize ITC'99 circuits to NanGate45 gate-level Verilog using Yosys.
# Run from anywhere; paths are resolved relative to this repository.
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
RTL_DIR="$REPO_ROOT/itc99_rtl"
OUT_DIR="$REPO_ROOT/FAN_ATPG/mod_netlist"
LIBERTY="$REPO_ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib"
LOG_DIR="$REPO_ROOT/logs/synth"

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: required tool '$tool' not found in PATH" >&2
    echo "Install the missing tool or export PATH to include it before running this script." >&2
    exit 127
  fi
}

require_tool yosys
require_tool python3

mkdir -p "$LOG_DIR"

# circuit_name:top_module_name (verified from grep "^module")
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

for entry in "${TARGETS[@]}"; do
  IFS=: read -r cname module <<< "$entry"
  rtl="$RTL_DIR/${cname}.v"
  out="$OUT_DIR/${cname}.v"
  log="$LOG_DIR/${cname}_synth.log"

  if [ ! -f "$rtl" ]; then
    echo "SKIP $cname: RTL not found at $rtl"
    continue
  fi

  echo -n "Synthesizing $cname ($module) ... "

  if ! yosys -q -p "
    read_verilog $rtl;
    synth -top $module -flatten;
    dfflibmap -liberty $LIBERTY;
    abc -liberty $LIBERTY;
    splitnets;
    opt_clean -purge;
    write_verilog -noattr $out;
  " > "$log" 2>&1; then
    echo "FAILED — see $log"
    continue
  fi

  # Rename escaped Verilog identifiers (\name[n] → name_n_) for FAN compatibility
  python3 "$REPO_ROOT/scripts/fixup_verilog.py" "$out" "${out}.tmp" && mv "${out}.tmp" "$out"

  ff_count=$(grep -cE "\bS?DFFR?S?_X[12]\b" "$out" 2>/dev/null || echo 0)
  echo "OK ($ff_count FFs → $out)"

  if [ "$ff_count" -lt 20 ]; then
    echo "  WARNING: $cname has <20 FFs — will be excluded from x=5% experiments"
  fi
done

echo ""
echo "Synthesis complete. Check $LOG_DIR/ for per-circuit logs."
