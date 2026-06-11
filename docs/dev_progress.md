# ScanForge — Development Progress & Log

This document tracks the current implementation status of each project stage and keeps a record of the development log.

---

## 1. Implementation Status

| Stage | Stage-wise Status | Status | Notes / Deliverables |
|---|---|---|---|
| **Stage A** | Yosys base-gate synthesis & OpenSTA slack extraction | **Completed** | Outputs synthesized Verilog to `FAN_ATPG/mod_netlist/b*.v` and non-scan masks to `masks/`. |
| **Stage B** | `PARTIAL_SEQUENTIAL` time-frame unrolling mode | **Completed** | Integrates scan-capable and non-scan FF unrolling in `FAN_ATPG` core. |
| **Stage C** | Sequential ATPG engine fixes | **Completed** | Resolves OOB event-stack crashes, MUX2 PODEM propagation, and multi-frame SAF consistency bugs. |
| **Stage D** | Progressive residual sweep pipeline | **Completed** | Automation runner `run_progressive_residual.py` and sweep script `run_progressive_residual_sweep.py` implemented. |
| **Stage E** | Sweep execution & Data collection | **In Progress** | Sweep is currently running in the background to generate `results/progressive_residual_summary.csv`. |
| **Stage F** | Two-Phase State Justification Optimization | **Completed** | C++ implementation completed and compilation verified. Exposes new `set_two_phase_justification` CLI command. |
| **Stage G** | Evaluation, plotting, and reporting | **In Progress** | Figures and final report draft under `docs/final_report.md` are being consolidated. |

---

## 2. Development Log

### May 2026 — Topic Realignment & Pilot
* Realigned course project topic to timing-driven partial scan sequential ATPG.
* Formulated the progressive time-frame recovery strategy (T=1 → T=2 → T=4).
* Verified the pilot unrolling mode on ISCAS'89 `s27` benchmark.

### June 5, 2026 — ATPG Engine Bug Fixes
* Fixed dominator tree event-stack OOB crash in `atpg.cpp` and `simulator.h` by adjusting array bounds to `maxGateLevel + 1`.
* Restored compilation and execution sanity for `b03`, `b04`, `b08`, and `b09`.

### June 9, 2026 — Base-Gate Synthesis & Scan Protocol
* Consolidated synthesis pipeline using only Nangate45 base gates to avoid OAI/AOI synthesis anomalies.
* Implemented `applyScanProtocol()` to exclude async reset pins from the fault coverage denominator, achieving >91% full-scan baselines across the ITC'99 benchmarks.
* Fixed multi-frame SAF target mapping and pattern-replay interface to ensure test coverage reproducibility.

### June 11, 2026 — Repo Cleanup, Doc Organization & Optimization Implementation
* Cleaned up the `results/` folder by moving TDD debug CSVs into `results/tdd_stage1/` and removing duplicate root scripts.
* Organized the `docs/` folder by archiving historical discussions, duplicate prototypes, and flow guides into `docs/archive/`.
* Implemented the **Two-Phase State Justification** algorithm in the `FAN_ATPG` submodule (adding custom backtracking boundaries and state objective justification), exposing it via the `set_two_phase_justification <on/off>` CLI command. Verified that the modified codebase compiles 100% cleanly.
* Launched the full progressive residual sweep across all Tier A benchmarks.
