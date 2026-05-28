#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCANFORGE="${ROOT}/src/scanforge"
RESULT_DIR="${ROOT}/results/timing_exclusion"
mkdir -p "${RESULT_DIR}"

CIRCUITS=("$@")
if [ ${#CIRCUITS[@]} -eq 0 ]; then
  CIRCUITS=(s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584)
fi

find_sf() {
  local circuit="$1"
  local p
  for p in \
    "${ROOT}/FAN_ATPG/results/${circuit}.sf" \
    "${ROOT}/results/${circuit}.sf"
  do
    if [ -f "$p" ]; then
      printf '%s\n' "$p"
      return 0
    fi
  done
  return 1
}

if [ ! -x "${SCANFORGE}" ]; then
  echo "Building ScanForge binary..."
  (cd "${ROOT}/src" && make)
fi

MASTER_CSV="${RESULT_DIR}/timing_exclusion_master.csv"
printf 'circuit,case,ratio,depth,coverage,pattern_count,runtime_sec,non_scan_ff,scan_ff,coverage_proxy_co,coverage_proxy_combined,pattern_applicability,switching_activity,max_segment_stress,segment_variance,hotspot_count\n' > "${MASTER_CSV}"

done_count=0
for circuit in "${CIRCUITS[@]}"; do
  sf_path="$(find_sf "${circuit}" || true)"
  netlist="${ROOT}/FAN_ATPG/mod_netlist/${circuit}.v"
  if [ -z "${sf_path}" ]; then
    echo "Skip ${circuit}: missing .sf in FAN_ATPG/results or results/" >&2
    continue
  fi
  if [ ! -f "${netlist}" ]; then
    echo "Skip ${circuit}: missing netlist ${netlist}" >&2
    continue
  fi

  ranking_csv="${RESULT_DIR}/${circuit}_timing_proxy.csv"
  sweep_csv="${RESULT_DIR}/${circuit}_exclude_sweep.csv"

  "${SCANFORGE}" "${sf_path}" \
    --timing-netlist "${netlist}" \
    --timing-ranking-out "${ranking_csv}" \
    --exclude-sweep \
    --exclude-summary-csv "${sweep_csv}" >/dev/null

  tail -n +2 "${sweep_csv}" >> "${MASTER_CSV}"
  done_count=$((done_count + 1))
  echo "[${done_count}] ${circuit} -> $(basename "${sweep_csv}")"
done

echo ""
echo "Timing exclusion sweep done."
echo "Per-circuit outputs: ${RESULT_DIR}"
echo "Master CSV: ${MASTER_CSV}"
