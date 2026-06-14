#!/usr/bin/env bash
# Build ISCAS'89 netlists for FAN_ATPG using TTU gate-level Verilog.
#
# Pipeline:
#   TTU format (pld.ttu.ee) → convert_ttu_to_nangate.py → DFFR_X1 cells
#   → fixup_verilog.py --full-scan → SDFFR_X1 + scan chain
#   → wrap long module header (FAN parser limit)
#
# No Yosys needed: TTU circuits are already gate-level NanGate45-equivalent.
# DFFs without reset are mapped to DFFR_X1 with RN=vdd (always inactive).
set -euo pipefail

SCRIPT_DIR="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TTU_DIR="$REPO_ROOT/iscas89_rtl/ttu"
OUT_DIR="$REPO_ROOT/FAN_ATPG/mod_netlist"
FIXUP="$REPO_ROOT/scripts/fixup_verilog.py"
CONV="$REPO_ROOT/scripts/convert_ttu_to_nangate.py"
LOG_DIR="$REPO_ROOT/logs/synth"
TTU_BASE="https://pld.ttu.ee/~maksim/benchmarks/iscas89/verilog"

require_tool() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not in PATH" >&2; exit 127; }
}
require_tool python3
require_tool curl

mkdir -p "$TTU_DIR" "$LOG_DIR" "$OUT_DIR"

# circuit_name (module name will be circuit_name after conversion)
TARGETS=(s953 s1196 s1238 s5378)

FAIL=0

for cname in "${TARGETS[@]}"; do
  ttu_v="$TTU_DIR/${cname}.v"
  dffr_v="$OUT_DIR/${cname}_dffr.v"
  final_v="$OUT_DIR/${cname}.v"
  log="$LOG_DIR/${cname}_iscas89.log"

  echo -n "[$cname] "

  # Download TTU file if not cached
  if [[ ! -f "$ttu_v" ]]; then
    echo -n "download ... "
    if ! curl -fsSL "$TTU_BASE/${cname}.v" -o "$ttu_v" 2>"$log"; then
      echo "FAILED (download) — see $log"
      FAIL=1; continue
    fi
  fi

  # Convert to NanGate45 DFFR format
  echo -n "convert ... "
  if ! python3 "$CONV" "$ttu_v" "$dffr_v" "$cname" >> "$log" 2>&1; then
    echo "FAILED (convert) — see $log"
    FAIL=1; continue
  fi
  ff_count=$(grep -c "DFFR_X1" "$dffr_v" 2>/dev/null || echo 0)

  # Insert scan chain
  echo -n "fixup (DFFR=$ff_count) ... "
  if ! python3 "$FIXUP" "$dffr_v" "$final_v" --full-scan --strict >> "$log" 2>&1; then
    echo "FAILED (fixup) — see $log"
    FAIL=1; continue
  fi

  sdff_count=$(grep -c "SDFFR_X1" "$final_v" 2>/dev/null || echo 0)
  mod_line=$(grep "^module" "$final_v" | awk '{print length}')
  echo "OK (SDFFR=$sdff_count module_line=${mod_line})"
done

echo ""
if [[ "$FAIL" -ne 0 ]]; then
  echo "Build finished with failures. See $LOG_DIR/" >&2
  exit 1
fi
echo "ISCAS'89 netlists ready in $OUT_DIR/s{953,1196,1238,5378}.v"
