#!/usr/bin/env bash
# Synthesize ITC'99 circuits to NanGate45 gate-level Verilog using Yosys.
# Run from anywhere; paths are absolute.
set -e

REPO_ROOT="/home/swear01/ScanForge"
RTL_DIR="$REPO_ROOT/itc99_rtl"
OUT_DIR="$REPO_ROOT/FAN_ATPG/mod_netlist"
LIBERTY="$REPO_ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib"
LOG_DIR="$REPO_ROOT/logs/synth"

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

  yosys -q -p "
    read_verilog $rtl;
    synth -top $module -flatten;
    dfflibmap -liberty $LIBERTY;
    abc -liberty $LIBERTY;
    splitnets;
    opt_clean -purge;
    write_verilog -noattr $out;
  " > "$log" 2>&1

  if [ $? -ne 0 ]; then
    echo "FAILED — see $log"
    continue
  fi

  # FAN full-scan format: SDFFR + scan chain + CK port (like s510/s27).
  python3 "$REPO_ROOT/scripts/fixup_verilog.py" "$out" "${out}.tmp" --full-scan && mv "${out}.tmp" "$out"

  ff_count=$(grep -cE "\bS?DFFR?S?_X[12]\b" "$out" 2>/dev/null || echo 0)
  echo "OK ($ff_count FFs → $out)"

  if [ "$ff_count" -lt 20 ]; then
    echo "  WARNING: $cname has <20 FFs — will be excluded from x=5% experiments"
  fi
done

echo ""
echo "Synthesis complete. Check $LOG_DIR/ for per-circuit logs."
