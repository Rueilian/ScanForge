# Shared ATPG timeout defaults (source from bash runners).
# Override: ATPG_WALL_TIMEOUT=7200 ATPG_PER_TARGET_TIMEOUT=30 bash scripts/run_phase_d_fullscan_dataset.sh
#
# Tier policy (see docs/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md):
#   Tier A (b03–b11,b13): PER_TARGET=0  — completes in ms–s; timeout only hides regressions
#   Tier B (b12/b14/b15): PER_TARGET=30 — cap stubborn faults without 120s × N blow-up

# Wall-clock limit per FAN invocation (seconds).
export ATPG_WALL_TIMEOUT="${ATPG_WALL_TIMEOUT:-3600}"

# Per-target-fault limit inside FAN (set_per_target_timeout); 0 = disabled.
# Default 0: safe for Tier A sweeps. Set 30 when ITC_INCLUDE_DEFERRED=1.
export ATPG_PER_TARGET_TIMEOUT="${ATPG_PER_TARGET_TIMEOUT:-0}"

# Parallel fault-partition workers; 0 = all CPU cores (nproc).
export ATPG_THREADS="${ATPG_THREADS:-0}"
