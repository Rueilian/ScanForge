#!/usr/bin/env bash
# Regenerate ITC'99 netlists in FAN full-scan format (SDFFR + scan chain).
set -euo pipefail
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
done

bash "$ROOT/scripts/verify_fullscan_netlist.sh"
