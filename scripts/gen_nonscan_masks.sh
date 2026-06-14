#!/usr/bin/env bash
# Run OpenSTA on all synthesized ITC'99 circuits and generate non-scan mask files.
# Requires synthesized netlists in FAN_ATPG/mod_netlist/b*.v
# Run from anywhere; paths are resolved relative to this repository.
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
NETLIST_DIR="$REPO_ROOT/FAN_ATPG/mod_netlist"
LIBERTY="$REPO_ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib"
MASK_DIR="$REPO_ROOT/masks"
LOG_DIR="$REPO_ROOT/logs/sta"
TCL_TEMPLATE="$REPO_ROOT/scripts/sta_extract_slack.tcl"
EXTRACT_PY="$REPO_ROOT/scripts/gen_mask_from_slack.py"

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: required tool '$tool' not found in PATH" >&2
    echo "Install the missing tool or export PATH to include it before running this script." >&2
    exit 127
  fi
}

require_tool sta
require_tool python3

mkdir -p "$MASK_DIR" "$LOG_DIR"

# circuit:top_module:clock_port
CIRCUITS=(
  "b03:b03:clock"
  "b04:b04:CLOCK"
  "b05:b05:CLOCK"
  "b07:b07:clock"
  "b08:b08:CLOCK"
  "b09:b09:clock"
  "b11:b11:clock"
  "b12:b12:clock"
  "b13:b13:clock"
  "b14:b14:clock"
  "b15:b15:CLOCK"
  "s953:s953:CK"
  "s1196:s1196:CK"
  "s1238:s1238:CK"
  "s5378:s5378:CK"
)

# Active evaluation uses 10% only; other ratios live in masks/archive/.
NONSCAN_RATIOS="0.10"

for entry in "${CIRCUITS[@]}"; do
  IFS=: read -r cname module clk_port <<< "$entry"
  netlist="$NETLIST_DIR/${cname}.v"

  if [ ! -f "$netlist" ]; then
    echo "SKIP $cname: synthesized netlist not found at $netlist"
    echo "  → Run synth_itc99.sh first"
    continue
  fi

  slack_csv="$MASK_DIR/${cname}_slack.csv"
  log="$LOG_DIR/${cname}_sta.log"

  # Write per-run TCL wrapper (sets variables then sources template)
  wrapper_tcl="/tmp/sta_wrap_${cname}.tcl"
  cat > "$wrapper_tcl" <<ENDTCL
set liberty_file "$LIBERTY"
set netlist_file "$netlist"
set top_module   "$module"
set clock_port   "$clk_port"
set output_file  "$slack_csv"
source "$TCL_TEMPLATE"
ENDTCL

  echo -n "Running STA for $cname ... "
  if ! sta "$wrapper_tcl" > "$log" 2>&1 || [ ! -f "$slack_csv" ]; then
    echo "FAILED — see $log"
    continue
  fi

  echo "OK"
  python3 "$EXTRACT_PY" "$slack_csv" "$MASK_DIR" "$cname" $NONSCAN_RATIOS
done

echo ""
echo "Mask generation complete. Files in $MASK_DIR/"
echo "Verify: wc -l $MASK_DIR/b03_x5.mask"
