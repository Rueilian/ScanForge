#!/usr/bin/env bash
# One-shot ITC'99 netlist pipeline: prep → synth → fixup → validate → FAN smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NL="$ROOT/FAN_ATPG/mod_netlist"
FIXUP="$ROOT/scripts/fixup_verilog.py"
export PATH="${HOME}/local/bin:${PATH:-}"

ITC=(b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15)
LIB_BASE="$ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib"

has_reset_port() {
  grep -qE '^\s*input\s+(reset|rst|nrst|arst|areset|reset_n)\s*;' "$1" 2>/dev/null
}

MODE="${1:-all}"
case "$MODE" in
  all|prep|synth|fixup|validate) ;;
  --fixup-only) MODE=fixup ;;
  *)
    echo "Usage: $0 [all|prep|synth|fixup|validate|--fixup-only]" >&2
    exit 1
    ;;
esac

run_prep() {
  command -v yosys >/dev/null || { echo "ERROR: yosys required" >&2; exit 1; }
  test -f "$LIB_BASE" || python3 "$ROOT/scripts/gen_base_liberty.py"
  python3 "$ROOT/scripts/prep_itc99_rtl.py" --all --check
}

run_synth() {
  bash "$ROOT/scripts/synth_itc99.sh"
}

run_fixup() {
  for c in "${ITC[@]}"; do
    dffr="$NL/${c}_dffr.v"
    out="$NL/${c}.v"
    if [[ ! -f "$dffr" ]]; then
      echo "ERROR: missing $dffr (run synth first)" >&2
      exit 1
    fi
    echo "== fixup $c"
    python3 "$FIXUP" "$dffr" "$out" --full-scan --strict
    if has_reset_port "$out"; then
      python3 "$FIXUP" "$out" "$NL/${c}_reset_tie.v" --reset-tie-high --strict
      echo "   + ${c}_reset_tie.v"
    fi
  done
}

run_validate() {
  python3 "$ROOT/scripts/validate_netlist.py" --all --json "$ROOT/logs/netlist/summary.json"
  python3 "$ROOT/scripts/fan_smoke_load.py" --circuits "${ITC[@]}"
  python3 "$ROOT/scripts/print_netlist_summary.py"
}

mkdir -p "$ROOT/logs/netlist"

case "$MODE" in
  all)
    run_prep
    run_synth
    run_fixup
    run_validate
    ;;
  prep) run_prep ;;
  synth) run_synth ;;
  fixup) run_fixup ;;
  validate) run_validate ;;
esac

echo "build_itc99_netlists.sh: DONE ($MODE)"
