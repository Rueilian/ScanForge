#!/usr/bin/env bash
# Structural checks for scan-inserted ITC'99 netlists.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NL="$ROOT/FAN_ATPG/mod_netlist"
FAIL=0

check_one() {
  local c="$1"
  local f="$NL/${c}.v"
  if [[ ! -f "$f" ]]; then
    echo "SKIP $c: missing $f"
    return
  fi
  local dffr sdffr test_si_top const_port
  dffr=$(grep -cE '\bDFFR_X1\b|\bDFFS_X1\b|\bDFFRS_X1\b' "$f" || true)
  sdffr=$(grep -cE '\bSDFFR_X1\b|\bSDFFS_X1\b|\bSDFFRS_X1\b' "$f" || true)
  test_si_top=$(head -40 "$f" | grep -c 'input test_si;' || true)
  const_port=$(grep -E 'module .*\(.*_const[0-9]+_' "$f" | wc -l || true)

  echo "== $c =="
  echo "  DFFR/DFFS: $dffr   SDFFR/SDFFS: $sdffr"
  echo "  input test_si in first 40 lines: $test_si_top"
  echo "  _constN_ in module header: $const_port"

  if [[ "$dffr" -ne 0 ]]; then
    echo "  FAIL: non-scan FF remains"
    FAIL=1
  fi
  if [[ "$sdffr" -eq 0 ]]; then
    echo "  FAIL: no scan FF found"
    FAIL=1
  fi
  if [[ "$test_si_top" -ne 1 ]]; then
    echo "  FAIL: test_si not declared near module top"
    FAIL=1
  fi
  if [[ "$const_port" -ne 0 ]]; then
    echo "  FAIL: _constN_ still a module port"
    FAIL=1
  fi
}

for c in b03 b04 b07 b08 b09 b11 b12 b13 b14 b15; do
  check_one "$c"
done

if [[ "$FAIL" -ne 0 ]]; then
  echo "verify_scan_netlist: FAILED"
  exit 1
fi
echo "verify_scan_netlist: PASS"
