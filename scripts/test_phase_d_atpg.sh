#!/usr/bin/env bash
# Phase D ATPG regression: relaxed PODEM init + atomic MUX2 + b03 FC.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAN="$ROOT/FAN_ATPG"
FAN_BIN="$FAN/pkg/fan/bin/opt/fan"
PHASE_TEST="$FAN/pkg/core/bin/opt/phase_d_test"

cd "$FAN"
make -j"$(nproc)" >/dev/null

echo "== phase_d_test (C++ unit)"
"$PHASE_TEST" "$FAN"

parse_fc() {
  local rpt="$1"
  python3 - "$rpt" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
fc_scan = re.search(r'fault coverage \(scan protocol\)\s+([\d.]+)%', text)
fc_scan_coll = re.search(r'fault coverage \(scan, collapsed\)\s+([\d.]+)%', text)
fc_raw = re.search(r'fault coverage \(raw, appendix\)\s+([\d.]+)%', text)
au = re.search(r'AU \(atpg untestable\)\s+(\d+)', text)
dt = re.search(r'DT \(detected\)\s+(\d+)', text)
print(f"{fc_scan.group(1) if fc_scan else '0'} {fc_scan_coll.group(1) if fc_scan_coll else '0'} {fc_raw.group(1) if fc_raw else '0'} {au.group(1) if au else '0'} {dt.group(1) if dt else '0'}")
PY
}

run_case() {
  local name="$1" script="$2"
  echo "== $name"
  "$FAN_BIN" -f "script/fanScripts/$script" >/dev/null
}

# Phase C regressions must not break
bash "$ROOT/scripts/test_phase_c_atpg.sh"

run_case "b03 scan-protocol baseline" "b03_fs.script"
read -r FC_SCAN FC_SCAN_COLL FC_RAW AU DT <<<"$(parse_fc rpt/b03_fs.rpt)"
echo "   b03 FC_scan=${FC_SCAN}% FC_scan_coll=${FC_SCAN_COLL}% FC_raw=${FC_RAW}% AU=${AU} DT=${DT}"
awk -v fc="$FC_SCAN" -v au="$AU" 'BEGIN {
  if (fc+0 < 90.0) { print "FAIL: b03 FC_scan < 90% on reset-tie netlist (base-gate pipeline)"; exit 1 }
  if (au+0 >= 35) { print "FAIL: b03 AU still >= 35"; exit 1 }
}'

echo "PASS: Phase D ATPG regression"
