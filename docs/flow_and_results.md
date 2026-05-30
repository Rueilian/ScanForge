# ScanForge — Pipeline Flow and Architecture

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
| Pass 4 | Module header missing const port names | Append `_const0_` etc. to port list |
| Pass 5 | Escaped identifiers (`\name[n]`) | Rename |
| Pass 6 | Constant literals in body | Replace with named `input` ports |

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

### 5.1 ITC'99 ATPG crashes (BLOCKING)

**Symptom:** b03, b05, b08, b09, b12, b14 crash with segfault during `run_atpg` on NanGate45-synthesized netlists.

**Root cause:** Likely the unconstrained `_const0_` input port. FAN_ATPG treats `_const0_` as a free PI. When the constant-zero input is unconstrained, the ATPG engine may encounter undefined behavior (null-pointer, divide-by-zero) depending on circuit structure.

**Workaround:** Constrain `_const0_` to 0 in the FAN script before `run_atpg`. The exact FAN_ATPG constraint command needs investigation.

**Status:** b07 and b13 survive ATPG but produce low fault coverage (~44-55%) due to unconstrained `_const0_`. s27 works correctly (no `_const0_`).

### 5.2 ITC'99 `_const0_` constraint needed

All Yosys-synthesized ITC'99 netlists use `_const0_` as a module input port. FAN_ATPG must be told to tie this port to constant 0 before ATPG, otherwise coverage is severely degraded. See `AGENTS.md` gotcha.

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

### Completed (with evidence)

- [x] Yosys synthesis flow → NanGate45 gate-level Verilog (11/11 circuits)
- [x] OpenSTA timing analysis → per-FF slack ranking
- [x] Non-scan mask generation at 5/10/15/20% (55 files)
- [x] `PARTIAL_SEQUENTIAL` multi-frame unrolling mode
- [x] `set_nonscan_ff` command and script integration
- [x] Multi-frame pattern storage (`PIFrames_`) and simulation replay
- [x] SAF final-frame fault mapping (ATPG + simulator consistency)
- [x] T=1 `partial_scan_no_recovery` verified on s27: 39.36% ≠ 94.55%
- [x] T=4 `partial_scan_with_recovery` verified on s27: 88.68% (recovery from 39.36%)
- [x] FAN_ATPG stability fixes (convergence, TIEX guards, build ordering)

### Blocked

- [ ] ITC'99 ATPG: 6/11 circuits crash (b03, b05, b08, b09, b12, b14) — likely `_const0_` constraint needed
- [ ] ITC'99 `_const0_` unconstrained → surviving circuits show ~44-55% fault coverage
- [ ] `run_atpg_sweep.py` CSV columns empty for b03 — crash before report generation

### Not Yet Started

- [ ] T=8 sequential ATPG recovery (T=4 verified on s27, T=8 not yet)
- [ ] ITC'99 full 55-run sweep
- [ ] Cone-guided multi-frame simplification

### Immediate Next Task

Add `_const0_` constraint in FAN scripts. Once all ITC'99 circuits survive ATPG, run the full sweep and collect meaningful fault coverage data.

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
