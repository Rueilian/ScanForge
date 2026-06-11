#!/usr/bin/env bash
# ITC'99 benchmark tiers for ScanForge ATPG experiments.
#
# Tier A (active):   full-scan SAF completes in seconds on current FAN engine.
# Tier B (deferred): netlist built/validated; excluded from sweeps until engine
#                    speed + correctness fixes land (b12/b14/b15).
# Tier C (out):      b17+ and other mega-benchmarks — not in project scope.
#
# Override for ad-hoc runs:
#   ITC_INCLUDE_DEFERRED=1 bash scripts/run_phase_d_fullscan_dataset.sh

ITC_ACTIVE=(b03 b04 b05 b07 b08 b09 b11 b13)
ITC_DEFERRED=(b12 b14 b15)
ITC_OUT_OF_SCOPE=(b17 b18 b20 b21 b22)

# All netlists produced by build_itc99_netlists.sh
ITC_ALL=(b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15)

# Default circuits for ATPG sweeps / FC reporting
if [[ "${ITC_INCLUDE_DEFERRED:-0}" == "1" ]]; then
  ITC_ATPG=("${ITC_ALL[@]}")
else
  ITC_ATPG=("${ITC_ACTIVE[@]}")
fi

export ITC_ACTIVE ITC_DEFERRED ITC_OUT_OF_SCOPE ITC_ALL ITC_ATPG
