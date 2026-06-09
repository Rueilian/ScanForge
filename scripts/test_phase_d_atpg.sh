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
fc = re.search(r'fault coverage\s+([\d.]+)%', text)
au = re.search(r'AU \(atpg untestable\)\s+(\d+)', text)
dt = re.search(r'DT \(detected\)\s+(\d+)', text)
print(f"{fc.group(1) if fc else '0'} {au.group(1) if au else '0'} {dt.group(1) if dt else '0'}")
PY
}

run_case() {
  local name="$1" script="$2"
  echo "== $name"
  "$FAN_BIN" -f "script/fanScripts/$script" >/dev/null
}

# Phase C regressions must not break
bash "$ROOT/scripts/test_phase_c_atpg.sh"

run_case "b03 Phase D baseline" "b03_fs.script"
read -r FC AU DT <<<"$(parse_fc rpt/b03_fs.rpt)"
echo "   b03 FC=${FC}% AU=${AU} DT=${DT}"
awk -v fc="$FC" -v au="$AU" 'BEGIN {
  if (fc+0 < 70) { print "FAIL: b03 FC < 70% after Phase D"; exit 1 }
  if (au+0 >= 300) { print "FAIL: b03 AU still >= 300"; exit 1 }
}'

echo "PASS: Phase D ATPG regression"
