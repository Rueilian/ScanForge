#!/usr/bin/env bash
# DEPRECATED: use scripts/build_itc99_netlists.sh (or --fixup-only via build script).
# Thin wrapper for fixup-only regeneration from existing _dffr.v sources.
set -euo pipefail
echo "NOTE: regenerate_fan_fullscan_netlists.sh is deprecated; use build_itc99_netlists.sh" >&2
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NL="$ROOT/FAN_ATPG/mod_netlist"
FIXUP="$ROOT/scripts/fixup_verilog.py"

CIRCUITS=(b03 b04 b07 b08 b09 b11 b12 b13 b14 b15)

for c in "${CIRCUITS[@]}"; do
  out="$NL/${c}.v"
  # Prefer DFFR-only base: dedicated copy, else current file stripped of scan.
  if [[ -f "$NL/${c}_dffr.v" ]]; then
    base="$NL/${c}_dffr.v"
  elif [[ -f "$NL/${c}_dffr_only.v" ]]; then
    base="$NL/${c}_dffr_only.v"
  elif [[ -f "$NL/${c}_ck.v" ]]; then
    base="$NL/${c}_ck.v"
  elif [[ -f "$out" ]]; then
    base="/tmp/${c}_strip.v"
    python3 "$ROOT/scripts/strip_scan_from_netlist.py" "$out" "$base" 2>/dev/null || cp "$out" "$base"
  else
    echo "SKIP $c: no source netlist"
    continue
  fi
  echo "== $c: $base -> FAN full-scan"
  python3 "$FIXUP" "$base" "$out" --full-scan
  if grep -qE '^\s*input\s+(reset|rst|nrst|arst|areset|reset_n)\s*;' "$out" 2>/dev/null; then
    python3 "$FIXUP" "$out" "$NL/${c}_reset_tie.v" --reset-tie-high
    echo "   + ${c}_reset_tie.v (scan-protocol netlist)"
  fi
done

bash "$ROOT/scripts/verify_fullscan_netlist.sh"
