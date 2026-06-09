#!/usr/bin/env bash
# Structural checks for FAN full-scan netlists (SDFFR + scan chain, like s510).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NL="$ROOT/FAN_ATPG/mod_netlist"
FAIL=0

for c in b03 b04 b07 b08 b09 b11 b12 b13 b14 b15; do
  f="$NL/${c}.v"
  [[ -f "$f" ]] || continue
  dffr=$(grep -cE '\bDFFR_X1\b|\bDFFS_X1\b|\bDFFRS_X1\b' "$f" || true)
  sdffr=$(grep -cE '\bSDFFR_X1\b|\bSDFFS_X1\b|\bSDFFRS_X1\b' "$f" || true)
  has_ck=$(grep -cE '\binput CK\b|\.CK\(CK\)' "$f" || true)
  has_clock=$(grep -cE '\binput clock\b|\.CK\(clock\)' "$f" || true)
  test_ports=$(grep -c 'test_si' "$f" || true)
  test_so=$(grep -c 'assign test_so' "$f" || true)
  const_port=$(grep -E 'module .*\(.*_const[0-9]+_' "$f" | wc -l || true)
  const_input=$(grep -cE '^\s*input\s+_const[0-9]+_\s*;' "$f" || true)
  echo "== $c == SDFFR=$sdffr DFFR=$dffr CK=$has_ck clock=$has_clock scan=$test_ports test_so=$test_so"
  [[ "$sdffr" -gt 0 ]] || { echo "  FAIL: no SDFFR scan FF"; FAIL=1; }
  [[ "$dffr" -eq 0 ]] || { echo "  FAIL: bare DFFR still present"; FAIL=1; }
  [[ "$has_ck" -gt 0 ]] || { echo "  FAIL: missing CK port"; FAIL=1; }
  [[ "$has_clock" -eq 0 ]] || { echo "  FAIL: clock port still present"; FAIL=1; }
  [[ "$test_ports" -gt 0 ]] || { echo "  FAIL: missing test_si/test_se"; FAIL=1; }
  [[ "$test_so" -gt 0 ]] || { echo "  FAIL: missing assign test_so"; FAIL=1; }
  [[ "$const_port" -eq 0 ]] || { echo "  FAIL: _constN_ module port"; FAIL=1; }
  [[ "$const_input" -eq 0 ]] || { echo "  FAIL: _constN_ input declaration"; FAIL=1; }
done
[[ "$FAIL" -eq 0 ]] && echo "verify_fullscan_netlist: PASS" || { echo "verify_fullscan_netlist: FAILED"; exit 1; }
