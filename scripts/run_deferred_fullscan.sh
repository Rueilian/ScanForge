#!/usr/bin/env bash
# Run remaining deferred full-scan ATPG (b15, s38417) and merge into results CSV.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/atpg_timeouts.sh"
FAN="$ROOT/FAN_ATPG"
FAN_BIN="$FAN/pkg/fan/bin/opt/fan"
OUT="$ROOT/results/phase_d_fullscan_dataset.csv"
APPENDIX="$ROOT/results/appendix_phase_d_fullscan_raw.csv"
THREADS="${ATPG_THREADS:-0}"
[[ "$THREADS" -eq 0 ]] && THREADS="$(nproc)"

cd "$FAN"
make -j"$THREADS" >/dev/null

run_one() {
  local circuit="$1" group="$2" wall="$3" per_target="$4"
  local nl="mod_netlist/${circuit}.v"
  local rpt="rpt/${circuit}_scan_proto_fs.rpt"
  local script="/tmp/fan_deferred_${circuit}.script"
  local pto=""
  [[ "$per_target" -gt 0 ]] && pto="set_per_target_timeout ${per_target}"

  cat >"$script" <<EOF
read_lib techlib/mod_nangate45.mdt
read_netlist ${nl}
build_circuit --frame 1
set_fault_type saf
add_fault --all
${pto}
set_atpg_threads ${THREADS}
set_static_compression on
set_dynamic_compression on
set_X-Fill on
run_atpg
report_statistics > ${rpt}
exit
EOF

  echo "START $circuit wall=${wall}s per_target=${per_target}s threads=${THREADS}"
  local t0 wall_s status=OK
  t0=$(date +%s.%N)
  if ! timeout "$wall" "$FAN_BIN" -f "$script" >/dev/null 2>&1; then
    status=FAIL
  fi
  wall_s=$(python3 -c "import time; print(f'{time.time()-float(\"$t0\"):.2f}')")

  if [[ "$status" == OK && -s "$rpt" ]]; then
    local stats
    stats=$(python3 "$ROOT/scripts/parse_fan_scan_stats.py" "$rpt" --csv)
    IFS=, read -r fc_scan fc_scan_coll tc_scan fc_raw tc_raw fu_c fu_full dt au ti_scan ti ud pat rt <<<"$stats"
    python3 - "$OUT" "$APPENDIX" "$circuit" "$group" "$fc_scan" "$fc_scan_coll" "$tc_scan" "$fu_c" "$dt" "$au" "$ti_scan" "$ud" "$pat" "$rt" "$wall_s" "$fc_raw" "$tc_raw" "$ti" <<'PY'
import csv, sys
out, appendix, circuit, group = sys.argv[1:5]
fields = sys.argv[5:]
fc_scan, fc_scan_coll, tc_scan, fu_c, dt, au, ti_scan, ud, pat, rt, wall_s, fc_raw, tc_raw, ti = fields
row = [circuit, group, fc_scan, fc_scan_coll, tc_scan, fu_c, dt, au, ti_scan, ud, pat, rt, wall_s]
app = [circuit, group, fc_raw, tc_raw, '', '', au, ti, '', wall_s]
for path, new_row in [(out, row), (appendix, app)]:
    rows, header = [], None
    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        replaced = False
        for r in reader:
            if r and r[0] == circuit:
                rows.append(new_row)
                replaced = True
            else:
                rows.append(r)
        if not replaced:
            rows.append(new_row)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
PY
    echo "OK $circuit fc_scan=${fc_scan}% wall=${wall_s}s"
  else
    echo "TIMEOUT/ERR $circuit wall=${wall_s}s (rpt size=$(stat -c%s "$rpt" 2>/dev/null || echo 0))"
    return 1
  fi
}

# b15 + s38417: 2h wall, shorter per-target (skip stubborn faults faster)
WALL_SLOW="${ATPG_WALL_TIMEOUT_SLOW:-7200}"
PTO_DEFERRED="${ATPG_PER_TARGET_TIMEOUT_DEFERRED:-15}"
PTO_ISCAS_SLOW="${ATPG_PER_TARGET_TIMEOUT_ISCAS_SLOW:-30}"
run_one b15 itc99 "$WALL_SLOW" "$PTO_DEFERRED"
run_one s38417 iscas "$WALL_SLOW" "$PTO_ISCAS_SLOW"

echo "Done. Updated $OUT"
