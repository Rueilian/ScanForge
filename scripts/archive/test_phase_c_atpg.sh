#!/usr/bin/env bash
# Phase C ATPG regression: PO/PPO observation fix + tiny_sdffr + b03 + s510.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAN="$ROOT/FAN_ATPG"
FAN_BIN="$FAN/pkg/fan/bin/opt/fan"
PHASE_TEST="$FAN/pkg/core/bin/opt/phase_c_test"

cd "$FAN"
make -j"$(nproc)" >/dev/null

echo "== phase_c_test (C++ unit)"
"$PHASE_TEST" "$FAN"

parse_fc() {
  local rpt="$1"
  python3 - "$rpt" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
fc = (re.search(r'fault coverage \(scan protocol\)\s+([\d.]+)%', text)
      or re.search(r'fault coverage \(raw, appendix\)\s+([\d.]+)%', text)
      or re.search(r'fault coverage\s+([\d.]+)%', text))
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

run_case "tiny_sdffr" "tiny_sdffr_check.script"
read -r FC AU DT <<<"$(parse_fc rpt/tiny_sdffr_atpg.rpt)"
echo "   FC=${FC}% AU=${AU} DT=${DT}"
awk -v fc="$FC" -v au="$AU" 'BEGIN {
  if (fc+0 < 85) { print "FAIL: tiny_sdffr FC < 85%"; exit 1 }
  if (au+0 != 0) { print "FAIL: tiny_sdffr AU != 0"; exit 1 }
}'

run_case "tiny_sdff" "tiny_sdff_check.script"
read -r FC AU DT <<<"$(parse_fc rpt/tiny_sdff_atpg.rpt)"
echo "   FC=${FC}% AU=${AU} DT=${DT}"
awk -v fc="$FC" -v au="$AU" 'BEGIN {
  if (fc+0 < 85) { print "FAIL: tiny_sdff FC < 85%"; exit 1 }
  if (au+0 != 0) { print "FAIL: tiny_sdff AU != 0"; exit 1 }
}'

run_case "s27" "s27_debug_fullscan.script"
# s27 stats go to stdout; re-run with report redirect
cat > /tmp/s27_phase_c.script <<'EOF'
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/s27.v
build_circuit --frame 1
set_fault_type saf
add_fault --all
run_atpg
report_statistics > rpt/s27_phase_c.rpt
exit
EOF
"$FAN_BIN" -f /tmp/s27_phase_c.script >/dev/null
read -r FC AU DT <<<"$(parse_fc rpt/s27_phase_c.rpt)"
echo "   s27 FC=${FC}% AU=${AU}"
awk -v fc="$FC" 'BEGIN { if (fc+0 < 90) { print "FAIL: s27 FC < 90%"; exit 1 } }'

run_case "s510" "s510_fs_quick.script"
read -r FC AU DT <<<"$(parse_fc rpt/s510_fs_quick.rpt)"
echo "   s510 FC=${FC}% AU=${AU}"
awk -v fc="$FC" 'BEGIN { if (fc+0 < 94) { print "FAIL: s510 FC < 94%"; exit 1 } }'

run_case "b03 baseline" "b03_fs.script"
read -r FC AU DT <<<"$(parse_fc rpt/b03_fs.rpt)"
echo "   b03 FC=${FC}% AU=${AU} DT=${DT}"

# Per-FF RN retarget breaks FAN netlist check (dangling reset INV nets); use reset tie instead.
cat > script/fanScripts/b03_reset_tie.script <<'EOF'
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b03_reset_tie.v
build_circuit --frame 1
set_fault_type saf
add_fault --all
run_atpg
report_statistics > rpt/b03_reset_tie.rpt
exit
EOF
run_case "b03 reset tie-high" "b03_reset_tie.script"
read -r FC_RST AU_RST DT_RST <<<"$(parse_fc rpt/b03_reset_tie.rpt)"
echo "   b03_reset_tie FC=${FC_RST}% AU=${AU_RST} DT=${DT_RST}"

echo "PASS: Phase C ATPG regression"
