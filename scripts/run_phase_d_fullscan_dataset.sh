#!/usr/bin/env bash
# Full-scan dataset sweep with scan-protocol FC as primary metric.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=atpg_timeouts.sh
source "$ROOT/scripts/atpg_timeouts.sh"
# shellcheck source=itc99_benchmark_scope.sh
source "$ROOT/scripts/itc99_benchmark_scope.sh"
FAN="$ROOT/FAN_ATPG"
FAN_BIN="$FAN/pkg/fan/bin/opt/fan"
OUT="$ROOT/results/phase_d_fullscan_dataset.csv"
APPENDIX="$ROOT/results/appendix_phase_d_fullscan_raw.csv"
# Legacy aliases (prefer ATPG_WALL_TIMEOUT / ATPG_PER_TARGET_TIMEOUT).
TIMEOUT="${TIMEOUT:-$ATPG_WALL_TIMEOUT}"
PER_TARGET_TIMEOUT="${PER_TARGET_TIMEOUT:-$ATPG_PER_TARGET_TIMEOUT}"
# shellcheck source=atpg_timeouts.sh already loaded ATPG_THREADS (default 0 = all cores)
if [[ "${ATPG_THREADS}" -eq 0 ]]; then
  ATPG_THREADS="$(nproc)"
fi

echo "ATPG timeouts: wall=${TIMEOUT}s per_target=${PER_TARGET_TIMEOUT}s threads=${ATPG_THREADS}"

cd "$FAN"
make -j"$(nproc)" >/dev/null

write_script() {
  local nl="$1"
  local rpt="$2"
  local pto="${3:-}"
  cat >"/tmp/fan_fs_$$.script" <<EOF
read_lib techlib/mod_nangate45.mdt
read_netlist ${nl}
build_circuit --frame 1
set_fault_type saf
add_fault --all
${pto}
${threads_cmd}
set_static_compression on
set_dynamic_compression on
set_X-Fill on
run_atpg
report_statistics > ${rpt}
exit
EOF
}

ITC=("${ITC_ATPG[@]}")
echo "ITC scope: ${ITC[*]} (deferred: ${ITC_DEFERRED[*]})"
ISCAS=(s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584)
TINY=(tiny_sdffr tiny_sdff)

echo "circuit,group,fc_scan,fc_scan_coll,test_cov_scan,fu_collapsed,dt,au,ti_scan,ud,patterns,runtime_s,wall_s" >"$OUT"
echo "circuit,group,fc_raw,test_cov_raw,fu_full,dt,au,ti,ab,wall_s" >"$APPENDIX"

run_one() {
  local circuit="$1" group="$2"
  local nl="mod_netlist/${circuit}.v"
  local rpt="rpt/${circuit}_scan_proto_fs.rpt"

  if [[ ! -f "$nl" ]]; then
    echo "SKIP $circuit: missing $nl"
    return
  fi

  local pto=""
  if awk -v t="$PER_TARGET_TIMEOUT" 'BEGIN { exit (t+0 > 0) ? 0 : 1 }'; then
    pto="set_per_target_timeout ${PER_TARGET_TIMEOUT}"
  fi
  local threads_cmd="set_atpg_threads ${ATPG_THREADS}"
  local wall_timeout="$TIMEOUT"
  write_script "$nl" "$rpt" "$pto"
  local t0
  t0=$(date +%s.%N)
  if timeout "$wall_timeout" "$FAN_BIN" -f "/tmp/fan_fs_$$.script" >/dev/null 2>&1; then
    local wall
    wall=$(python3 - <<PY
import time
print(f"{time.time() - float('$t0'):.2f}")
PY
)
    local stats
    stats=$(python3 "$ROOT/scripts/parse_fan_scan_stats.py" "$rpt" --csv)
    IFS=, read -r fc_scan fc_scan_coll tc_scan fc_raw tc_raw fu_c fu_full dt au ti_scan ti ud pat rt <<<"$stats"
    echo "${circuit},${group},${fc_scan},${fc_scan_coll},${tc_scan},${fu_c},${dt},${au},${ti_scan},${ud},${pat},${rt},${wall}" >>"$OUT"
    echo "${circuit},${group},${fc_raw},${tc_raw},,,${au},${ti},,${wall}" >>"$APPENDIX"
    echo "OK $circuit fc_scan=${fc_scan}%"
  else
    echo "TIMEOUT/ERR $circuit"
  fi
}

for c in "${ITC[@]}"; do run_one "$c" itc99; done
for c in "${ISCAS[@]}"; do run_one "$c" iscas; done
for c in "${TINY[@]}"; do run_one "$c" tiny; done

rm -f "/tmp/fan_fs_$$.script"
echo "Wrote $OUT"
echo "Wrote $APPENDIX"
