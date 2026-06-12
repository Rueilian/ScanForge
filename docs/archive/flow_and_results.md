# ScanForge — Pipeline Flow and Architecture

> **Archived.** Describes legacy T=8 `run_atpg_sweep.py` flow. Current pipeline: `scripts/run_progressive_residual.py` — see [`../spec.md`](../spec.md).

## 1. Project Overview

ScanForge studies fault coverage loss and recovery when timing-critical flip-flops are excluded from scan. The pipeline:

1. Synthesizes ITC'99 benchmark circuits to NanGate45 gate-level Verilog (Yosys)
2. Ranks FFs by timing criticality via OpenSTA minimum-path-slack analysis
3. Marks the top `x%` most timing-critical FFs as non-scan
4. Runs FAN_ATPG with a `PARTIAL_SEQUENTIAL` T=8-frame unrolled model
5. Collects stuck-at fault coverage across 11 circuits × 5 ratios = 55 runs

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Stage A: Synthesis + Timing Analysis                               │
│                                                                     │
│  itc99_rtl/b*.v                                                     │
│       │ Yosys (synth_itc99.sh)                                      │
│       ▼                                                             │
│  FAN_ATPG/mod_netlist/b*.v    (NanGate45 gate-level, post-fixup)   │
│       │ OpenSTA (sta_extract_slack.tcl)                             │
│       ▼                                                             │
│  masks/<circuit>_slack.csv    (per-FF min path slack)              │
│       │ gen_mask_from_slack.py                                      │
│       ▼                                                             │
│  masks/<circuit>_x*.mask      (FF cell names, top x% by slack)     │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│  Stage B/C: FAN_ATPG with PARTIAL_SEQUENTIAL Mode                  │
│                                                                     │
│  Script per (circuit, ratio):                                       │
│    read_lib techlib/mod_nangate45.mdt                               │
│    read_netlist mod_netlist/<circuit>.v                             │
│    set_nonscan_ff <names from mask>          ← Task C              │
│    build_circuit --frame 8                   ← triggers Task B     │
│    set_fault_type saf                                               │
│    add_fault --all                                                  │
│    run_atpg                                                         │
│    report_statistics > rpt/<circuit>_x<x>.rpt                      │
│                                                                     │
│  PARTIAL_SEQUENTIAL unrolling (T=8 frames):                        │
│    non-scan FF: PPO[t] → BUF → PPI[t+1]  (state propagates)       │
│    scan FF:     PPI[t] free               (independently driven)   │
│    frame 0:     all PPIs free             (X initial state)        │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│  Stage D: Experiment Runner + Results                               │
│                                                                     │
│  run_atpg_sweep.py                                                  │
│    for each (circuit, ratio) in 11 × 5:                            │
│      generate FAN script                                            │
│      invoke ./bin/opt/fan -f <script>  (cwd = FAN_ATPG/)           │
│      parse rpt: fault_coverage, DT, AU, AB, UD, patterns, time     │
│      append row to results/itc99_partial_scan.csv                  │
│                                                                     │
│  Output: results/itc99_partial_scan.csv  (55 rows)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. FAN_ATPG Extensions

### 3.1 PARTIAL_SEQUENTIAL Mode (Task B)

`connectMultipleTimeFrame()` in `circuit.cpp` handles three modes:

| `TIME_FRAME_CONNECT_TYPE` | Behavior |
|---|---|
| `COMBINATIONAL` | No inter-frame connections |
| `SEQUENTIAL` | All PPOs connect to next-frame PPIs via BUF |
| `PARTIAL_SEQUENTIAL` | Non-scan FF PPOs → BUF → next-frame PPI; scan FF PPIs remain free |

Frame 0 is treated uniformly: all PPIs are free (X initial state). This follows standard sequential ATPG convention.

The implementation uses a frame-0 snapshot (`const std::vector<Gate> f0`) to avoid template mutation bugs when expanding gates across frames.

### 3.2 `set_nonscan_ff` Command (Task C)

FAN script syntax:
```
set_nonscan_ff <cell_name_1> <cell_name_2> ...
set_nonscan_ff --clear
```

Flow:
1. `SetNonscanFfCmd::exec()` stores cell names in `fanMgr_->nonscanFfNames`
2. `BuildCircuitCmd::exec()` copies to `cir->nonscanCellNames_` before calling `connectMultipleTimeFrame()`
3. FAN prints `# Non-scan FFs declared: N total` to confirm name matching

### 3.3 Verilog Post-Processing (`fixup_verilog.py`)

Yosys-generated Verilog requires post-processing for FAN compatibility:

| Pass | Problem | Fix |
|------|---------|-----|
| Pre-pass | Constant literals (`1'b0`, `1'h0`) in port connections | Discover all `_constN_` names needed |
| Pass 1–2 | Bus port/wire declarations (`[N:0] name`) | Expand to individual scalars |
| Pass 3 | Indexed references (`name[n]`) | Rename to `name_n_` |
| Pass 4 | Module header bus expansion | Expand bus ports in module header |
| Pass 5 | Escaped identifiers (`\name[n]`) | Rename |
| Pass 6 | Constant literals in body | Replace with named wire (_const0_, _const1_) |
| Pass 7 | `_constN_` as module input breaks FAN (free PI) | Instantiate `LOGIC0_X1`/`LOGIC1_X1` tie cells instead |

The Pass 7 fix (2026-05-30) replaces the previous approach of adding `_const0_`/`_const1_` as module input ports. NanGate45 `LOGIC0_X1` and `LOGIC1_X1` cells are instantiated to drive these constant wires, which FAN_ATPG recognizes as proper tie cells (TIEL/TIEH) rather than free PIs.

---

## 4. Evaluation Cases

The project spec (`spec.md`) defines three evaluation cases for the final comparison:

| Case | Description | Status |
|------|-------------|--------|
| `full_scan` | All FFs scan, x=0%, standard 1-frame ATPG | Works (ISCAS'89) |
| `partial_scan_no_recovery` | Non-scan FFs present, T=1, X initial state | Under verification |
| `partial_scan_with_recovery` | Non-scan FFs present, T=8 sequential ATPG | Not yet implemented |

### 4.1 `partial_scan_no_recovery` correctness (critical)

The T=1 no-recovery case must treat non-scan FFs as **unknown and uncontrollable** at the single modeled frame. Any behavior that lets ATPG freely justify non-scan FF values back to 0/1 is an invalid implementation.

An implementation audit (documented in `checklist.md`) has identified the key modification points. After the most recent observability fix on s27 (ISCAS'89) at 67% non-scan ratio:

- `full_scan`: coverage=94.55%
- `partial_scan_no_recovery`: coverage=85.45% (AU=10, UD=6)

This separation from full-scan is the correct direction. However, full verification on the ITC'99 benchmark set is still pending.

### 4.2 `partial_scan_with_recovery` (T=8/T=4) status

T=4 sequential ATPG has been verified on s27 with meaningful coverage recovery:

| Circuit | Mode | x% | T | Fault coverage | DT | AU |
|---------|------|----|---|----------------|----|----|
| s27 | Full scan | 0% | 1 | 94.55% | 104 | 0 |
| s27 | Partial scan no recovery | 67% | 1 | 39.36% | 37 | 55 |
| s27 | Partial scan with recovery | 67% | 4 | 88.68% | — | — |

The T=4 result recovers coverage from 39.36% to 88.68%, confirming that multi-frame sequential justification works. T=8 recovery is not yet separately validated — the current `run_atpg_sweep.py` uses T=8 for all non-zero ratios.

---

## 5. Known Issues

### 5.1 FAN_ATPG level-indexed array sizing (FIXED: e26e038+local patch)

**Root cause:** `circuitLevel_to_EventStack_` and `events_` arrays sized `totalLvl_` but gates can have `numLevel_ == totalLvl_`. Caused OOB crash in `identifyGateDominator()` and `Simulator::eventFaultSim()`.

**Fix:** Size arrays to `maxGateLevel + 1` where `maxGateLevel = max(gate.numLevel_)` across all circuit gates. Committed locally in FAN_ATPG submodule (atpg.h, simulator.h).

**Circuits resolved:** b03, b04, b08, b09 (4 additional circuits now pass ATPG).

### 5.2 ITC'99 remaining blockers

| Circuit | Status | Root cause |
|---------|--------|------------|
| b05 | CRASH | `assign` syntax at line 5169 — Verilog compat |
| b11 | TIMEOUT | 58 FFs, ATPG exceeds 120s |
| b12 | TIMEOUT | 192 FFs, ATPG exceeds 120s |
| b14 | TIMEOUT | 219 FFs, ATPG exceeds 120s |
| b15 | UNTESTED | 839 FFs, runtime concern |

### 5.3 `set_nonscan_ff` has no visible effect at low exclusion

At x=5%, all ITC'99 circuits show identical `full_scan` vs `no_recovery` coverage. The AU-dominated fault distribution (50-65% AU) masks partial-scan effects. Higher exclusion ratios (10-20%) may show separation but were not yet tested.

### 5.4 Progressive residual multi-frame ATPG evaluation

Two regimes tested:

**Low-exclusion (x=20%): b07, b13**
- T=2 adds minimal benefit: 7-8 new faults detected
- T=4 residual recovers 21-27 faults but naive T=4 loses 83-108 T=1-detected faults
- Union gain: +1.2 to +1.4pp over T=1
- AU recovery rate: 0.6-2.2%
- **Recommendation: T=1 only.** Multi-frame adds marginal value at low exclusion.

**High-exclusion (x=67%): s27**
- T=1→39.36%, T=2→72.22%, T=4→86.67%
- T=2 recovers 20 of 39 residual faults (51.3% AU recovery)
- T=4 recovers 29 of 39 residual faults (74.4% AU recovery), 9 beyond T=2
- Naive loss is minimal: only 2 faults lost from T=1
- Union: FC_T1=37.88%, FC_T1∪T2=68.18% (+20), FC_T1∪T2∪T4=81.82% (+9)
- **Recommendation: T=1 → T=2 → T=4 progressive residual is effective.**

**Priority scoring (both regimes):**
Simple structural priority (obs/ctrl distance, cone size, fanout) does NOT outperform random ordering. Top-K recovery curves nearly identical regardless of prioritization. More sophisticated features or learned ranking may be needed.

**Budget:**
BACKTRACK_LIMIT=500 is compile-time constant. AB explosion was not observed (AB=0 for both s27 and b07). The strong s27 recovery was achieved within default budget.

### 5.5 b03 crashes at T=4 multi-frame ATPG

---

## 6. Benchmark Details

| Circuit | FFs | Clock port | Notes |
|---------|-----|------------|-------|
| b03 | 31 | `clock` | |
| b04 | 67 | `CLOCK` | |
| b05 | 88 | `CLOCK` | |
| b07 | 45 | `clock` | |
| b08 | 28 | `clock` | |
| b09 | 30 | `clock` | |
| b11 | 58 | `clock` | |
| b12 | 192 | `clock` | |
| b13 | 65 | `clock` | |
| b14 | 219 | `clock` | |
| b15 | 839 | `CLOCK` | Largest circuit; ATPG may take > 1 hr |

FF cells in synthesized netlists: `DFFR_X1`, `DFFS_X1`, `DFFRS_X1` (NanGate45 standard cells; not `SDFF_X1`).

---

## 7. Experiment Plan

### Parameter sweep

| Parameter | Values |
|---|---|
| Non-scan ratio `x` | 0% (full-scan baseline), 5%, 10%, 15%, 20% |
| Sequential ATPG depth | T=8 (fixed; T=1 for x=0% baseline) |

Total: **11 circuits × 5 ratios = 55 runs**

### Evaluation metrics

| Metric | Purpose |
|---|---|
| Fault coverage | Primary success metric |
| Test coverage | Secondary coverage view |
| Undetected / aborted faults | Remaining ATPG gap |
| Pattern count | Test-cost proxy |
| ATPG runtime | Practicality |

---

## 8. Current Status

### True Progressive Residual Multi-Frame ATPG Results

| Case | Excl | T1 FC% | T1∪T2% | T1∪T2∪T4% | Gain pp | T2 new | T4 new | Conclusion |
|------|------|--------|---------|------------|---------|--------|--------|------------|
| s27 x=67% | 2/3 | 37.88 | 68.18 | 81.82 | **+43.94** | 20 | 9 | **STRONG** — run T=2+T=4 |
| b07 x=20% | 9/45 | 28.91 | 29.26 | 30.27 | +1.36 | 7 | 20 | MARGINAL — T=1 only |
| b07 x=50% | 22/45 | 19.47 | 19.89 | 20.37 | +0.90 | 8 | 9 | NONE — stop at T=1 |
| b13 x=20% | 13/65 | 42.20 | 42.74 | 43.64 | +1.44 | 10 | 17 | MARGINAL — T=1 only |
| b13 x=50% | 32/65 | 30.00 | 30.23 | 30.93 | +0.93 | 4 | 12 | NONE — stop at T=1 |

**Key finding: higher exclusion DECREASES recovery gain on ITC'99.**
b07/b13 have high AU from structural untestability, not from sequential constraints.
Only s27 (ISCAS'89, small, controllability-driven) shows genuine sequential recovery.

### Final Method: True Progressive Residual Multi-Frame ATPG

1. Run T=1 on all faults → D1
2. Build residual list R1 = All - D1
3. Run T=2 only on R1 → D2
4. Build residual list R2 = R1 - D2
5. Run T=4 only on R2 → D4
6. Report: D_final = D1 ∪ D2 ∪ D4 over original denominator

`add_fault -f <file>` enables custom residual fault-list targeting.

### Completed
- [x] LOGIC0/LOGIC1 tie-cell fix
- [x] maxGateLevel event-stack sizing
- [x] `add_fault -f` custom residual fault-list
- [x] True progressive residual pipeline
- [x] Full sweep: s27, b07(20/50%), b13(20/50%)
- [x] Per-fault gateID reporting
- [x] Fixed-denominator union coverage

### Blocked / Not Started
- [ ] T=8 recovery (future work)
- [ ] b11/b12/b14 (timeout), b05 (assign syntax), b15 (untested)
- [ ] BACKTRACK_LIMIT budget tuning (compile-time constant)
- [ ] Priority scoring (negative result — abandoned)

### Immediate Next Task

Test higher exclusion ratios (10-20%) to see if no_recovery separates from full_scan. The current 5% may exclude too few FFs to show a measurable coverage delta.

---

## 9. Legacy Content (deprecated topics)

The sections below describe older project work that has been superseded. They are retained for reference but no longer reflect the current project direction.

### 9.1 ScanForge C++ Engine (ISCAS'89)

The `src/` directory contains a standalone C++ engine that was originally built for:
- SCOAP-based partial scan FF selection
- Scan-shift switching activity simulation
- Stress-aware and wear-leveling partial scan modes
- Timing-exclusion sweep analysis on ISCAS'89 benchmarks

This engine is **not required** for the current ITC'99 sequential ATPG pipeline. It is kept for the legacy timing-exclusion sweep workflow. See the [README](./README.md) for its CLI reference.

### 9.2 Stress-Aware Partial Scan (progress_report.md)

The initial project topic was "Stress-Aware Partial Scan Selection" targeting ISCAS'89 benchmarks with a SCOAP coverage proxy. This work produced a full experimental study (7 modes, 12 circuits, 7,920 data rows) and is documented in `progress_report.md`.

As of May 2026, the project has been redirected to the current topic: **"Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits"** targeting ITC'99 benchmarks with true stuck-at fault coverage via FAN_ATPG.

The `progress_report.md` file has been updated to reflect the new topic. The old stress-aware content is preserved in git history.

---

## 10. Dependencies

| Component | Purpose |
|---|---|
| FAN_ATPG | ATPG backend with PARTIAL_SEQUENTIAL mode |
| Yosys | RTL → NanGate45 gate-level synthesis |
| OpenSTA | Static timing analysis for FF slack ranking |
| Python 3 | Experiment runner, mask generation, verilog fixup |
| g++ (C++14) | ScanForge engine (legacy) |
| bison, flex | FAN_ATPG build dependencies |

---

## 11. How to Run

```bash
# 1. Build FAN_ATPG
cd FAN_ATPG && make -j$(nproc) && cd ..

# 2. Synthesize ITC'99 benchmarks
bash scripts/synth_itc99.sh

# 3. Generate non-scan masks
bash scripts/gen_nonscan_masks.sh

# 4. Run pilot ATPG sweep
python3 scripts/run_atpg_sweep.py --circuits b03

# 5. Run full sweep (after bug fix confirmed)
python3 scripts/run_atpg_sweep.py
```
