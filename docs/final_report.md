# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops remain non-scan due to timing constraints, creating a partial-scan circuit. At T=1, non-scan FF outputs are unknown (X), causing a **31.26pp average gap to full-scan coverage** across 10 benchmark circuits. We investigate how multi-frame sequential ATPG can recover this loss.

We first establish that T=2 sequential ATPG recovers significant coverage, but T=4 adds little further benefit. This raises the central question: **what mechanism drives T=2 recovery?** Is it the frame-based backtrack limit differential (T1=800 at T=1 vs 5000 at T>1), or the Two-Phase State Justification decoupling?

To answer this, we conduct **five controlled ablation experiments** on the same 10 circuits, each varying exactly one parameter. Results are unambiguous: **(1)** Two-Phase ON (Exp 2) raises average FC from 73.48% to **90.42%** (+16.94pp vs baseline), with individual circuits gaining up to 58.49pp. **(2)** Uniform T1=5000 (Exp 3) changes FC by only +0.02pp — the backtrack limit differential is **not** the mechanism. **(3)** Enhanced backtrace (+0.47pp) and static learning (+0.00pp) produce negligible impact. **(4)** With Two-Phase ON, T=4 adds **0 pp universally** — T=2 exhausts all recoverable faults. **(5)** The pipeline narrows the gap to full-scan from 31.26pp to **4.24pp**.

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

**Initial measurement:** At T=1 with 10% non-scan exclusion, the average gap to full-scan coverage across our 10 circuits is **31.26pp**. This loss motivates the search for recovery through sequential ATPG.

### 1.2 Problem and Discovery

In a partial-scan circuit at T=1, non-scan FF outputs are in an unknown (X) initial state. Any fault whose propagation path passes through a non-scan FF pseudo-primary output (PPO) is therefore **structurally untestable in a single frame** — classified AU (atpg untestable) by the ATPG engine.

Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state can be justified through functional clocking — is the standard approach to recover this loss. However, deeper frames increase the search space, and standard multi-frame ATPG interleaves fault propagation and state justification within a single backtrack search, causing propagation backtrack explosions to exhaust the budget before state justification begins.

We implement a frame-based backtrack limit: T1=800 at T=1 (preventing wasted search on structurally unrecoverable faults), BACKTRACK=5000 at T>1 (full budget for sequential recovery). There is no per-target timeout; the backtrack limit is the sole bounding mechanism.

**Empirical observation:** The baseline pipeline recovers 10.10pp (from 63.38% to 73.48%). T=2 and T=4 each contribute, but the recovery is inconsistent across circuits. Some circuits gain most at T=2 (s5378: +14.93pp), others at T=4 (b05: +16.69pp), and some show almost no recovery (b03: +0.00pp, s953: +0.65pp). This raises the central question: **what drives recovery?** Is it the backtrack limit differential (T1=800 vs 5000), Two-Phase State Justification, or something else entirely? This question motivates our controlled ablation experiments.

### 1.3 Approach

We implement a *progressive residual multi-frame ATPG* pipeline (T=1→T=2→T=4) with a frame-based backtrack limit (T1=800 at T=1, BACKTRACK=5000 at T>1) and fault-denominator-consistent union accounting. This pipeline serves as the experimental platform.

The pipeline alone establishes *that* recovery occurs. To discover *why*, we design **five controlled ablation experiments**, each changing exactly one parameter:

| Exp | Name | Parameter Changed | What it isolates |
|-----|------|-------------------|-----------------|
| 1 | Baseline | — | How much does the plain pipeline recover? |
| 2 | Two-Phase ON | `useTwoPhaseJustification_` enabled at T>1 | Does decoupling propagation from justification help? |
| 3 | Uniform T1 | T1=5000 (same as T>1) | Is the T1 differential the mechanism? |
| 4 | Enhanced Backtrace | Composite-score heuristic ON | Does better backtrace selection help? |
| 5 | Static Learning | Fanout-implication ON | Does early conflict detection help? |

Each experiment runs the full T=1→T=2→T=4 pipeline on the same 10 circuits. The pipeline and experiment design are detailed in §4 and §6.3.

### 1.4 Scope and Positioning

This work does **not** propose a new partial-scan selection method or a new fault model. Timing-driven non-scan FF selection uses OpenSTA minimum-path-slack ranking at a **fixed 10%** exclusion ratio — **experimental setup only**. The **research narrative** follows a discovery path:

1. **What is the gap?** T=1 (combinational) vs full-scan: how much coverage is lost? (RQ1)
2. **Does depth help?** How much does T=2 recover? Does T=4 recover more? (RQ2)
3. **Why does T=2 work?** Which mechanism — backtrack limit differential or Two-Phase State Justification — drives the recovery? (RQ3)
4. **Can heuristics help?** Do enhanced backtrace or static learning improve coverage? (RQ4)

Multi-ratio comparison of absolute partial-scan FC is **not** part of this study; only **x = 10%** is evaluated. We report on **10 circuits** (6 ITC'99 + 4 ISCAS'89) that completed all 5 experiments; the remaining 5 circuits (b11, b13, s9234, s15850, s35932) are excluded — b11 and s35932 produce runner crashes, while b13, s9234, and s15850 timeout under the baseline pipeline.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF participates in the scan chain. ATPG can set any FF state arbitrarily in one cycle. In partial scan, some FFs (non-scan) are excluded from the chain. At T=1 with unknown (X) initial state, non-scan FFs are uncontrollable — their values cannot be set by scan loading.

### 2.2 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses partial-scan controllability by unrolling the circuit across T time frames. Each frame is a copy of the combinational portion of the circuit. Non-scan FF outputs (PPOs) at frame t connect to their inputs (PPIs) at frame t+1, while scan FF PPIs remain independently controllable at each frame. The initial state at frame 0 is typically X. T=1 is a single-frame model where non-scan FF PPOs remain X; T>1 provides initialization cycles to justify non-scan FF state.

### 2.3 FAN_ATPG and PARTIAL_SEQUENTIAL Mode

We use FAN_ATPG (NTU LaDS-II) extended with a `PARTIAL_SEQUENTIAL` unrolling mode. Non-scan FFs propagate state across frames via BUF connections; scan FF PPIs are free at each frame. The `set_nonscan_ff` command designates non-scan FFs. ATPG effort is bounded by backtrack limits rather than wall-clock timeout.

### 2.4 Fault Classes

After ATPG, each stuck-at fault is classified as:

- **DT** (detected): a test pattern was found.
- **AU** (atpg untestable): the ATPG engine determined no pattern exists within the search limit.
- **AB** (abort): the engine reached its backtrack limit before finding a pattern.
- **TO** (timeout): per-target time expired; testability not determined.
- **UD** (undetected): the fault was not targeted.

Fault coverage FC = DT / (DT + AU + AB + TO + UD).

### 2.5 Frame-Based Backtrack Limit

FAN_ATPG uses a backtrack limit to bound search effort per fault. By default, this limit is uniform (BACKTRACK=5000) across all time-frame depths. Our modification introduces a **frame-based differential**: T=1 uses T1_BACKTRACK_LIMIT=800 while T>1 uses BACKTRACK=5000.

**Why this matters:** At T=1, faults blocked by non-scan FF X-state are structurally unrecoverable — no single-frame pattern can detect them. Without the differential, the engine spends 5000 backtracks per fault trying to prove them untestable, yielding AU classification but consuming significant runtime. With T1=800, these faults quickly hit the backtrack limit, are classified AB (abort), and enter the residual set where T=2 recovery can attempt.

There is no per-target timeout — the backtrack limit is the sole bounding mechanism. The recovery mechanism is investigated via controlled ablation experiments (§6.3) comparing Two-Phase, enhanced backtrace, static learning, and uniform T1 limit configurations.

### 2.6 Fault Dropping

FAN_ATPG performs *within-run* fault dropping: after generating a pattern, fault simulation identifies other faults also detected by that pattern and marks them DT. However, each `add_fault --all` call rebuilds the entire fault list from the circuit. There is no built-in mechanism to import detections from a T=1 run into a T=2 run. This motivates our custom residual fault-list loading.

---

## 3. Problem Formulation

Given a partial-scan circuit C with scan FF set S and non-scan FF set N (selected by timing prioritization), let F be the original physical fault set extracted at T=1 (the collapsed stuck-at fault list).

For time-frame depth T, let D_T be the set of faults in F detected by running ATPG at depth T.

Define:

- R1 = F − D1  (residual after T=1)
- R2 = F − D1 − D2  (residual after T=2)
- D_final = D1 ∪ D2 ∪ D4 (final union)
- FC_final = |D_final| / |F|

A key engine-level challenge in multi-frame ATPG is the coupling between fault propagation and state justification. In a single-frame (combinational) ATPG, propagation D-drive and line justification operate on the same logic cone. In multi-frame partial-sequential ATPG, fault effects propagate within the last frame while non-scan FF state must be justified across earlier frames — two structurally different search problems. An ATPG engine that treats all frames uniformly applies the same backtrack budget to both tasks, often exhausting it on propagation alone before state justification begins. **Two-Phase State Justification** (§4.2) addresses this decoupling.

Our analysis questions are:

1. **RQ1 (pipeline gain):** How many percentage points does FC(T1∪T2∪T4) exceed FC(T1)?
2. **RQ2 (stage attribution):** How much of that gain comes from residual T=2 vs residual T=4?
3. **RQ3 (mechanism):** Is the gain driven by the T1 backtrack limit (T1=800 at T=1 vs 5000 at T>1), Two-Phase State Justification, or both?
4. **RQ4 (enhancements):** Do enhanced backtrace or static learning improve coverage or reduce cost?

**Important:** For each circuit, all comparisons use the same T=1 collapsed fault set F as denominator. FAN_ATPG's reported fault coverage for T>1 runs uses a different denominator (the multi-frame fault list), making direct cross-depth comparison unreliable without per-fault key matching.

**Full-scan baseline metric:** We report **FC_fullscan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice, asynchronous reset and control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator.

---

## 4. Proposed Method: Progressive Residual Multi-Frame ATPG

```
Algorithm: Progressive Residual Multi-Frame ATPG
Input:  Circuit C, non-scan FF set N, fault set F (T=1 collapsed)
Output: Final detection set D_final, coverage FC_final

1. D1 ← ATPG(T=1, target=F)
2. R1 ← F − D1
3. D2 ← ATPG(T=2, target=R1)   ▷ only on residual
4. R2 ← F − D1 − D2
5. D4 ← ATPG(T=4, target=R2)   ▷ only on remaining residual
6. D_final ← D1 ∪ D2 ∪ D4
7. FC_final ← |D_final| / |F|
```

### 4.1 Why Residual Targeting

Progressive residual targeting provides three benefits:

1. **Preserves T=1 detections.** Deeper frames never re-target already-detected faults.
2. **Reduces target count.** T=2 targets only R1 (≤|F|); T=4 targets only R2 (≤|R1|), reducing ATPG effort.
3. **Enables recoverability analysis.** By isolating which faults are recovered at each depth, we can characterize the residual fault profile.

### 4.2 Two-Phase State Justification

Multi-frame ATPG on partial-scan circuits has two logically distinct subproblems within each target fault:

- **Phase 1 — Propagation (last frame):** Drive a D-frontier from the fault site to an observable output in frame T−1. Non-scan FF PPIs in this frame are treated as free primary inputs — the engine can assign any value to support propagation. This is structurally identical to combinational ATPG propagation on the last frame's logic cone.
- **Phase 2 — State Justification (frames 0..T−2):** For each non-scan FF PPI whose value was assigned during Phase 1, justify that value backward through frames T−2, T−3, ..., 0. Non-scan FF values at frame 0 start as unknown (X) and must be justified through functional paths in earlier frames.

Standard multi-frame ATPG interleaves these two tasks within a single unified backtrack search. FAN_ATPG's `useTwoPhaseJustification_` mode decouples them:

1. **Phase 1:** Temporarily disconnect non-scan PPIs from their driving frame-T−2 outputs, treating them as independent PIs. Run PODEM on the last frame with the full backtrack budget to find a propagation path and a consistent set of PPI assignments.
2. **Phase 2:** Reconnect the non-scan PPIs. For each PPI value required by Phase 1, attempt backward justification across frames T−2..0 with a fresh backtrack budget. If any PPI value cannot be justified, the fault remains AU.

This decoupling prevents propagation backtrack explosions from exhausting the budget before state justification begins, and concentrates engine effort on the subproblem that is actually failing. The `useTwoPhaseJustification_` mode is **disabled in the baseline pipeline** and tested as Exp 2 (§6.3).

**Why this recovers T=1 AU faults:** At T=1, non-scan FF PPOs are X — the engine cannot propagate through them because the FF output value is unknown. At T=2, Phase 1 treats non-scan FF PPIs as free PIs, allowing PODEM to find a propagation path that was blocked at T=1. Phase 2 then justifies the required PPI values using frame 0, which is possible when the non-scan FF has a functional path from a scan-controllable source or primary input.

### 4.3 Fixed-Denominator Union Accounting

FAN_ATPG's `report_statistics` for T>1 runs reports fault coverage against the multi-frame fault list, whose denominator may differ from the T=1 collapsed fault list. To ensure fair comparison, we:

1. Extract per-fault D1, D2, D4 sets using `report_fault` with stable (gateID, faultyLine, faultType) keys.
2. Compute union coverage |D1 ∪ D2 ∪ D4| / |F| using the T=1 fault count |F|.

This approach guarantees that **pipeline stage FC values are comparable within each circuit** at the fixed 10% setup. The headline metric is **total_gain_pp**.

---

## 5. Implementation

### 5.1 FAN_ATPG Extensions

We extended FAN_ATPG with:

- **`add_fault -f <file>`:** Loads a custom fault list from a text file (format: `gateID SA0|SA1 faultyLine` per line). The circuit's full fault set is extracted first, then only matched entries are loaded into the active fault list. This enables T=2 and T=4 to target exactly the residual set.
- **Per-fault reporting:** `report_fault` outputs `g=<ID> l=<line> <type> <status> <gate_name>` for every fault, enabling stable fault-key matching across runs.

### 5.2 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_progressive_residual.py` | End-to-end T=1→T=2→T=4 residual pipeline |
| `scripts/run_progressive_residual_sweep.py` | ITC'99 sweep driver (8 circuits) |
| `scripts/run_progressive_residual_iscas89_sweep.py` | ISCAS'89 sweep driver (7 circuits) |
| `scripts/run_fullscan_baseline_iscas89.py` | ISCAS'89 full-scan ceiling (B2) |
| `scripts/analyze_residual.py` | Per-fault overlap analysis and priority evaluation |
| `scripts/generate_figures.py` | Matplotlib chart generation for report |

### 5.3 Engineering Stabilization

Several backend fixes were required for the pipeline to function:

| Issue | Resolution |
|-------|-----------|
| FAN_ATPG rejects floating nets in Yosys output | ERROR→WARN in `netlist.cpp` for unconnected nets |
| `_const0_` as free module input | LOGIC0_X1/LOGIC1_X1 tie-cell instantiation in `fixup_verilog.py` |
| OOB crash in level-indexed event stacks | `maxGateLevel+1` sizing in `atpg.h` and `simulator.h` |
| Stale mask FF names after re-synthesis | Regenerate masks via `gen_nonscan_masks.sh` after synthesis |
| `report_fault` prints nothing without `-s` flag | Fix inverted `stateSet` logic |
| DFF faults lack instance name in report | Print cell name for all gate types |
| ITC netlist undriven / OAI-heavy PODEM AU | **Base-gate pipeline** (`build_itc99_netlists.sh`): prep RTL → synth with `base.lib` (MUX2 allowed, OAI/AOI forbidden) → fixup v2 → `validate_netlist.py` |
| FAN compound-gate model complexity | Use only MUX as compound gate (ATPG-natural); revert OAI/AOI atomic gate mods after pipeline validation |
| ISCAS'89 TTU double-module stub | Track `in_target_module` flag in `convert_ttu_to_nangate.py` to skip `module dff(CK,Q,D)` primitives |

These are infrastructure fixes; they are not claimed as research contributions.

### 5.4 ATPG Optimization Flags

Two flag-gated ATPG heuristics were implemented for ablation, each toggled via FAN CLI:

**Enhanced Backtrace (composite-score heuristic):** `calCompositeScore()` computes a weighted composite score for each candidate objective input: `0.6 × SCOAP_controllability + 0.3 × gate_depth − 0.1 × fanout_count`. When `set_enhanced_backtrace on` is active, `findEasiestInput()` selects the input with the lowest composite score instead of the default SCOAP-only comparison.

This flag influences only the backtrace selection heuristic, not the core FAN engine logic.

**Static Learning (fanout-implication):** Precomputes for each gate the immediate fanout values forced when the gate takes a controlling value (e.g., AND gate input=0 forces output=0). When `set_static_learning on` is active, `evaluateAndSetGateAtpgVal()` checks learned implications after each gate assignment; a contradiction triggers early conflict detection. The implication database covers AND/OR/NAND/NOR/BUF/INV gates and is rebuilt once before ATPG begins.

---

## 6. Experimental Setup

### 6.1 Benchmarks

We evaluate on two benchmark suites.

**Testset A — ITC'99** (synthesized to NanGate45 via Yosys with base-gate library) [16]:

| Circuit | FFs | Non-scan @10% |
|---------|-----|--------------:|
| b03 | 30 | 4 |
| b04 | 66 | 7 |
| b05 | 88 | 9 |
| b07 | 44 | 5 |
| b08 | 67 | 7 |
| b09 | 29 | 3 |
| b11 | 84 | 9 |
| b13 | 86 | 9 |

**Testset B — ISCAS'89** (TTU gate-level netlists converted to NanGate45 SDFFR_X1; 7 circuits used in the pipeline — s38417 and s38584 are excluded because their T=1 FC already exceeds 92%, leaving minimal residual):

| Circuit | FFs | Non-scan @10% | Full-scan B2 |
|---------|----:|-------------:|-------------:|
| s953    |  29 |  3 | 96.91% |
| s1196   |  18 |  2 | 98.27% |
| s1238   |  18 |  2 | 95.14% |
| s5378   | 179 | 18 | 94.74% |
| s9234   | 211 | 22 | 92.91% |
| s15850  | 534 | 54 | 93.32% |
| s35932  | 1728 | 173 | 87.17% |

Circuits s27 and s510 (< 10 FFs) are excluded from the pipeline evaluation; s27 (3 FFs, 67% non-scan at x=10) is retained as a sanity check only — T=1 FC = 37.9%, pipeline FC = 81.8%, gain = +43.9pp, confirming the residual pipeline correctly recovers faults limited by non-scan FF controllability.

### 6.2 Partial-Scan Setup

OpenSTA ranks FFs by minimum-path-slack on synthesized NanGate45 gate-level netlists. The top **10%** most timing-critical FFs are designated non-scan. Only 10% is evaluated.

**ITC'99 masks:**

| Circuit | FF total | Non-scan @10% | Mask |
|---------|--------:|-------------:|------|
| b03 | 30 | 4 | `masks/b03_x10.mask` |
| b04 | 66 | 7 | `masks/b04_x10.mask` |
| b05 | 88 | 9 | `masks/b05_x10.mask` |
| b07 | 44 | 5 | `masks/b07_x10.mask` |
| b08 | 67 | 7 | `masks/b08_x10.mask` |
| b09 | 29 | 3 | `masks/b09_x10.mask` |
| b11 | 84 | 9 | `masks/b11_x10.mask` |
| b13 | 86 | 9 | `masks/b13_x10.mask` |

### 6.3 ATPG Experiments

All runs use a **unified base configuration**:

- Fault model: stuck-at (SAF)
- Pipeline depths: T=1 (all faults), T=2 (residual R1), T=4 (residual R2)
- Static/dynamic compression: **off**
- Wall timeout: **3600 s** (Python `subprocess.run`), no per-target timeout
- **Circuit scope:** 15 circuits (8 ITC'99 + 7 ISCAS'89); 10 (b03, b04, b05, b07, b08, b09, s953, s1196, s1238, s5378) completed all 5 experiments; 5 excluded — b11/s35932 runner crash, b13/s9234/s15850 timeout at 600s

**Base pipeline settings:** T1=800 at T=1, BACKTRACK=5000 at T>1 (frame-based backtrack limit). Two-Phase State Justification is **OFF**, enhanced backtrace and static learning are **OFF**. Each fault is targeted at each depth with full backtrack budget; the only bounding mechanism is the backtrack limit.

**Rationale for T1=800:** At T=1, faults blocked by non-scan FF X-state are structurally unrecoverable. A lower backtrack limit prevents wasted search, creating an AB residual that T=2 can target. There is no per-target timeout — the backtrack limit is the sole bounding mechanism.

**Five controlled ablation experiments** decompose the pipeline's mechanism:

| Exp | Name | Parameter Changed vs Baseline | Research Question |
|-----|------|------------------------------|-------------------|
| 1 | Baseline | — | How much coverage does the plain pipeline recover? |
| 2 | Two-Phase ON | `useTwoPhaseJustification_` enabled at T>1 | Does decoupling propagation from justification help? |
| 3 | Uniform T1 | `ATPG_T1_BACKTRACK_LIMIT=5000` (same as T>1) | Is the gain driven by the T1 differential? |
| 4 | Enhanced Backtrace | `set_enhanced_backtrace on` | Does composite-score improve backtrace quality? |
| 5 | Static Learning | `set_static_learning on` | Does early conflict detection improve results? |

Each experiment runs the **full pipeline** (T=1→T=2→T=4) on all **15 circuits**, changing exactly the one parameter listed above. Exp 2 (Two-Phase ON) uses data from a prior sweep under the same circuit set and backtrack limits.

### 6.4 Metrics and Baselines

**Two baselines** anchor all reporting:

| Baseline | Setup | Metric | Source |
|----------|-------|--------|--------|
| **B1 — Partial-scan T=1** | 10% non-scan, no per-target timeout | **FC_T1** | progressive residual results |
| **B2 — Full-scan** | All FFs scan, T=1, no per-target timeout | **FC_fullscan** | full-scan baseline runs |

Pipeline and comparison metrics (same T=1 fault denominator |F|):

| Metric | Definition | Compares |
|--------|------------|----------|
| **FC_T1** | \|D1\| / \|F\| | **B1** |
| **FC_T1_T2_T4** | \|D1 ∪ D2 ∪ D4\| / \|F\| | **Experiment** (T=1→T=2→T=4) |
| **gain_T2_pp** | FC_T1_T2 − FC_T1 | T=2 stage gain |
| **gain_T4_pp** | FC_T1_T2_T4 − FC_T1_T2 | T=4 stage gain |
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 | Experiment vs **B1** |
| **B2−Experiment** | FC_fullscan − FC_T1_T2_T4 | Remaining gap to full-scan |
| **ΔvsExp1 (Exp N)** | FC(Exp N) − FC(Exp 1) | Ablation vs baseline pipeline |
| **T1_mem_mb** | VmPeak (MB) at T=1 FAN run | Per-stage memory |
| **T2_mem_mb** | VmPeak (MB) at T=2 FAN run | Per-stage memory |
| **T4_mem_mb** | VmPeak (MB) at T=4 FAN run | Per-stage memory |
| **peak_mem_mb** | max(T1, T2, T4) VmPeak | Pipeline memory ceiling |

**Memory measurement:** Each pipeline stage invokes FAN in a separate process. After `run_atpg`, the runner calls FAN `report_memory_usage`, which reports VmPeak (virtual address space high-water mark, MB) from `/proc/self/status`. `peak_mem_mb` is the maximum across the three stage runs for that circuit — stages are sequential, so peaks are not summed.

---

## 7. Results

We present results following the discovery narrative: gap to full-scan → baseline multi-frame recovery → ablation experiments to identify the mechanism.

### 7.1 Step 1: How Big Is the T=1 Gap to Full-Scan?

We first quantify the coverage loss caused by non-scan FF X-state at T=1.

**Full-scan reference ceiling (B2):** Full-scan coverage for each circuit.

| Circuit | B2 (full-scan FC) |
|---------|:-----------------:|
| b03     | 91.62% |
| b04     | 93.46% |
| b05     | 95.34% |
| b07     | 93.46% |
| b08     | 94.03% |
| b09     | 93.44% |
| s953    | 96.91% |
| s1196   | 98.27% |
| s1238   | 95.14% |
| s5378   | 94.74% |

**T=1 (B1) vs B2:**

| Circuit | B1 (T=1) | B2 (full-scan) | **Gap** |
|---------|:--------:|:--------------:|:-------:|
| b03 | 44.50% | 91.62% | 47.12pp |
| b04 | 75.21% | 93.46% | 18.25pp |
| b05 | 29.10% | 95.34% | 66.24pp |
| b07 | 56.13% | 93.46% | 37.33pp |
| b08 | 72.96% | 94.03% | 21.07pp |
| b09 | 76.34% | 93.44% | 17.10pp |
| s953 | 36.75% | 96.91% | 60.16pp |
| s1196 | 86.13% | 98.27% | 12.14pp |
| s1238 | 82.42% | 95.14% | 12.72pp |
| s5378 | 74.25% | 94.74% | 20.49pp |

**Average gap: 31.26pp.** Non-scan FF X-state causes a severe coverage drop at T=1.

### 7.2 Step 2: Baseline Multi-Frame Recovery (T=1→T=2→T=4)

The baseline pipeline (T1=800 at T=1, BACKTRACK=5000 at T>1, Two-Phase OFF) runs T=1, then targets residual faults at T=2, then T=4.

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|
| b03     | 44.50% | 44.50% | +0.00pp | +0.00pp | +0.00pp |
| b04     | 75.21% | 85.42% | +4.88pp | +5.33pp | +10.21pp |
| b05     | 29.10% | 45.94% | +0.16pp | +16.69pp | +16.84pp |
| b07     | 56.13% | 57.64% | +0.00pp | +1.51pp | +1.51pp |
| b08     | 72.96% | 91.99% | +14.86pp | +4.17pp | +19.02pp |
| b09     | 76.34% | 86.56% | +10.22pp | +0.00pp | +10.22pp |
| s953    | 36.75% | 37.40% | +0.65pp | +0.00pp | +0.65pp |
| s1196   | 86.13% | 98.40% | +12.27pp | +0.00pp | +12.27pp |
| s1238   | 82.42% | 95.12% | +12.71pp | +0.00pp | +12.71pp |
| s5378   | 74.25% | 91.86% | +14.93pp | +2.68pp | +17.61pp |

**Average:** T1→T2→T4 FC = 73.48%, total gain = 10.10pp.

**Key observation — inconsistent stage attribution:**
- Some circuits gain entirely at T=2 (s1196, s1238)
- Others gain entirely at T=4 (b05: +16.69pp at T=4)
- A few show negligible recovery (b03: +0.00pp, s953: +0.65pp)

This inconsistency raises the central question: **what mechanism drives T=2 recovery?** Two candidates exist:
1. **T1 backtrack limit differential** (800→5000): T=1's lower budget creates an AB residual; T=2 retries with 5000 backtracks
2. **Two-Phase State Justification**: decoupling propagation from justification at T>1

### 7.3 Step 3: Ablation Experiments

We run **five controlled experiments** to decompose the mechanism. Each experiment runs the full T=1→T=2→T=4 pipeline on all 10 circuits, changing exactly one parameter relative to Exp 1.

#### Exp 1 (Baseline): T1=800, Two-Phase OFF
*(Data in §7.2 - used as reference)*

#### Exp 2 (Two-Phase ON): `useTwoPhaseJustification_` enabled at T>1

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain | Runtime |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|:-------:|
| b03     | 44.50% | 85.41% | +40.91pp | +0.00pp | +40.91pp | 0.32s |
| b04     | 75.21% | 84.46% | +9.25pp | +0.00pp | +9.25pp | 34.41s |
| b05     | 29.20% | 87.68% | +58.49pp | +0.00pp | +58.49pp | 15.64s |
| b07     | 56.13% | 87.93% | +31.80pp | +0.00pp | +31.80pp | 0.88s |
| b08     | 72.96% | 91.09% | +18.13pp | +0.00pp | +18.13pp | 0.59s |
| b09     | 76.34% | 87.85% | +11.51pp | +0.00pp | +11.51pp | 0.33s |
| s953    | 36.75% | 91.26% | +54.51pp | +0.00pp | +54.51pp | 0.32s |
| s1196   | 86.13% | 98.40% | +12.27pp | +0.00pp | +12.27pp | 0.27s |
| s1238   | 82.42% | 95.12% | +12.71pp | +0.00pp | +12.71pp | 0.36s |
| s5378   | 74.21% | 94.97% | +20.76pp | +0.00pp | +20.76pp | 19.90s |

**Average:** FC = 90.42%, total gain = 27.03pp. **T=4 adds 0 pp on every circuit.**

#### Exp 3 (Uniform T1=5000): Tests whether the backtrack limit differential drives recovery

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain | Runtime |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|:-------:|
| b03     | 44.50% | 44.50% | +0.00pp | +0.00pp | +0.00pp | 0.25s |
| b04     | 75.21% | 85.42% | +4.88pp | +5.33pp | +10.21pp | 17.50s |
| b05     | 29.20% | 46.10% | +0.13pp | +16.77pp | +16.90pp | 7.39s |
| b07     | 56.13% | 57.64% | +0.00pp | +1.51pp | +1.51pp | 0.33s |
| b08     | 72.96% | 91.99% | +14.86pp | +4.17pp | +19.02pp | 0.86s |
| b09     | 76.34% | 86.56% | +10.22pp | +0.00pp | +10.22pp | 0.57s |
| s953    | 36.75% | 37.40% | +0.65pp | +0.00pp | +0.65pp | 0.52s |
| s1196   | 86.13% | 98.40% | +12.27pp | +0.00pp | +12.27pp | 0.71s |
| s1238   | 82.42% | 95.12% | +12.71pp | +0.00pp | +12.71pp | 1.88s |
| s5378   | 74.25% | 91.86% | +14.93pp | +2.68pp | +17.61pp | 10.76s |

**Average:** FC = 73.50%, total gain = 10.11pp. **ΔFC vs Exp 1: +0.02pp.** Nearly identical to baseline.

#### Exp 4 (Enhanced Backtrace): Composite-score heuristic ON

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain | Runtime |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|:-------:|
| b03     | 41.66% | 41.66% | +0.00pp | +0.00pp | +0.00pp | 0.68s |
| b04     | 81.14% | 89.57% | +5.91pp | +2.52pp | +8.42pp | 6.30s |
| b05     | 29.40% | 48.86% | +0.15pp | +19.31pp | +19.47pp | 8.64s |
| b07     | 56.07% | 57.57% | +0.00pp | +1.50pp | +1.51pp | 0.34s |
| b08     | 72.52% | 91.99% | +15.30pp | +4.17pp | +19.47pp | 1.10s |
| b09     | 76.34% | 86.56% | +10.22pp | +0.00pp | +10.22pp | 0.83s |
| s953    | 37.56% | 37.94% | +0.38pp | +0.00pp | +0.38pp | 0.50s |
| s1196   | 85.30% | 98.40% | +13.10pp | +0.00pp | +13.10pp | 0.34s |
| s1238   | 82.01% | 95.12% | +13.11pp | +0.00pp | +13.11pp | 0.88s |
| s5378   | 74.33% | 91.83% | +14.93pp | +2.57pp | +17.50pp | 109.01s |

**Average:** FC = 73.95%, total gain = 10.32pp. **ΔFC vs Exp 1: +0.47pp.** Negligible.

> **Note:** Exp 4 T1 FC values differ from Exp 1 (e.g., b03 41.66% vs 44.50%) because the enhanced backtrace flag is active for all pipeline stages including T=1, not only T>1. This means more than one parameter technically changes at T=1. However, the key metric is the final pipeline FC, which differs from baseline by only 0.47pp — confirming enhanced backtrace has negligible impact regardless of T=1 variation.

#### Exp 5 (Static Learning): Fanout-implication ON

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain | Runtime |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|:-------:|
| b03     | 44.50% | 44.50% | +0.00pp | +0.00pp | +0.00pp | 0.16s |
| b04     | 75.21% | 85.42% | +4.88pp | +5.33pp | +10.21pp | 19.47s |
| b05     | 29.20% | 45.92% | +0.07pp | +16.66pp | +16.73pp | 8.96s |
| b07     | 56.13% | 57.64% | +0.00pp | +1.51pp | +1.51pp | 0.41s |
| b08     | 72.96% | 91.99% | +14.86pp | +4.17pp | +19.02pp | 0.98s |
| b09     | 76.34% | 86.56% | +10.22pp | +0.00pp | +10.22pp | 0.69s |
| s953    | 36.75% | 37.40% | +0.65pp | +0.00pp | +0.65pp | 0.47s |
| s1196   | 86.13% | 98.40% | +12.27pp | +0.00pp | +12.27pp | 0.51s |
| s1238   | 82.46% | 95.12% | +12.62pp | +0.04pp | +12.66pp | 1.01s |
| s5378   | 74.25% | 91.86% | +14.93pp | +2.68pp | +17.61pp | 13.78s |

**Average:** FC = 73.48%, total gain = 10.09pp. **ΔFC vs Exp 1: +0.00pp.** Completely identical.

### 7.4 Step 4: Ablation Summary

The ablation results conclusively identify the mechanism:

| Exp | Parameter | Avg FC | Avg Gain | ΔFC vs Exp 1 | Avg Runtime |
|-----|-----------|:------:|:--------:|:-----------:|:----------:|
| 1 | Baseline (T1=800, TP=OFF) | 73.48% | 10.10pp | — | 5.72s |
| 2 | **Two-Phase ON** | **90.42%** | **27.03pp** | **+16.94pp** | 7.30s |
| 3 | Uniform T1=5000 | 73.50% | 10.11pp | +0.02pp | 4.08s |
| 4 | Enhanced Backtrace | 73.95% | 10.32pp | +0.47pp | 12.86s |
| 5 | Static Learning | 73.48% | 10.09pp | +0.00pp | 4.64s |

**Key takeaway:** Two-Phase State Justification is the dominant recovery mechanism (+16.94pp average). Neither uniform T1, enhanced backtrace, nor static learning produces meaningful improvement over the baseline pipeline.

### 7.5 Memory Usage

We record per-stage VmPeak (MB) for all 10 report circuits across Exp 1–5. Memory is dominated by **time-frame depth**: T=4 peak exceeds T=1 on every circuit because `build_circuit --frame 4` unrolls a larger combinational model. Residual fault count at T>1 does not drive peak — only frame depth does.

**Exp 1 (baseline) per-stage memory:**

| Circuit | T1 (MB) | T2 (MB) | T4 (MB) | peak (MB) |
|---------|--------:|--------:|--------:|----------:|
| b03 | 10.49 | 10.66 | 10.97 | 10.97 |
| b04 | 12.39 | 12.61 | 13.70 | 13.70 |
| b05 | 14.95 | 15.50 | 17.48 | 17.48 |
| b07 | 11.46 | 11.62 | 12.36 | 12.36 |
| b08 | 10.74 | 10.90 | 11.30 | 11.30 |
| b09 | 10.73 | 10.90 | 11.30 | 11.30 |
| s953 | 11.96 | 12.28 | 13.28 | 13.28 |
| s1196 | 12.43 | 12.77 | 13.92 | 13.92 |
| s1238 | 12.46 | 12.76 | 13.82 | 13.82 |
| s5378 | 24.96 | 26.13 | 31.43 | **31.43** |

**Average pipeline peak:** 14.96 MB (Exp 1). Worst case: s5378 at 31.43 MB. On small circuits, T4/T1 peak ratio is 1.05×–1.17×; on s5378 it is 1.26×.

**Ablation impact on memory:**

| Exp | Parameter | Avg peak (MB) | Max peak (MB) | Δpeak vs Exp 1 |
|-----|-----------|:-------------:|:-------------:|:--------------:|
| 1 | Baseline (T1=800, TP=OFF) | 14.96 | 31.43 | — |
| 2 | Two-Phase ON | 14.91 | 31.25 | −0.05 MB |
| 3 | Uniform T1=5000 | 14.96 | 31.43 | 0.00 MB |
| 4 | Enhanced Backtrace | 14.96 | 31.43 | 0.00 MB |
| 5 | Static Learning | 15.04 | 32.00 | +0.08 MB |

None of the ablation flags materially change pipeline peak memory. Two-Phase ON increases T=2 VmPeak on s5378 (26.1→28.9 MB) because decoupled justification retains more frame state during search, but T=4 still sets the pipeline ceiling (~31 MB). Enhanced backtrace and static learning change runtime (especially Exp 4 on s5378) without increasing peak memory.

**Conclusion:** At T≤4 on these benchmarks, memory cost is modest and predictable. Frame depth — not Two-Phase, backtrace heuristics, or static learning — is the primary memory driver.

## 8. Discussion

### 8.1 Why T=2 Recovers Faults That T=1 Misses

At T=1 with a partial-scan circuit, non-scan FF outputs are in an unknown (X) state. Faults whose propagation path requires a specific non-scan FF value are structurally untestable in a single frame. With T1=800 backtracks, the engine quickly hits the limit rather than spending 5000 backtracks proving AU — these faults become **AB** (abort) in the residual.

The ablation results are unambiguous:

- **Exp 3 (Uniform T1=5000)** shows that giving T=1 the same backtrack budget as T=2 changes the final FC by only +0.02pp. The T1 differential does **not** create the residual — non-scan FF X-state blocking does. Even with 5000 backtracks at T=1, faults blocked by non-scan FF X-state remain AB/AU.

- **Exp 2 (Two-Phase ON)** shows that decoupling propagation from state justification is the recovery engine. With Two-Phase OFF, T=2 recovers 7.07pp on average. With Two-Phase ON, T=2 recovers 27.03pp — a **3.8× improvement** over the unified search. Two-Phase works because:
  1. **Phase 1 (propagation in frame 1):** Non-scan FF PPIs in frame 1 are decoupled and treated as free PIs. The engine can assign any value to enable propagation. At T=1, the non-scan FF PPO is X and blocks propagation.
  2. **Phase 2 (state justification in frame 0):** Required PPI values are justified backward through frame 0. Success depends on functional paths from controllable sources.

**Why Exp 1/3/4/5 show T=4 gain while Exp 2 shows none:** Without Two-Phase, the unified search at T=2 often exhausts its backtrack budget on propagation before state justification begins, leaving a residual for T=4. With Two-Phase ON, the decoupled approach succeeds at T=2, and no further recovery is possible at T=4.

### 8.2 The Role of the Backtrack Limit

The T1=800 limit prevents wasting 5000 backtracks on structurally unrecoverable T=1 faults. This is purely a **bounding mechanism** — it creates the AB residual efficiently. **It does not cause the recovery.** Exp 3 confirms this: even with T1=5000, the residual and pipeline gain are nearly identical to T1=800.

### 8.3 T=4 Adds Nothing with Two-Phase ON

With Two-Phase ON (Exp 2), T=4 adds **0 pp** across all 10 circuits. The residual after T=2 consists entirely of faults that are structurally AU at any depth — two frames are sufficient for these circuits' non-scan-FF sequential depth. Without Two-Phase (Exp 1, 3, 4, 5), T=4 adds modest gain (up to 16.69pp for b05), but this reflects the inefficiency of the unified search at T=2 rather than a genuine depth requirement.

### 8.4 Remaining Gap to Full-Scan

With Two-Phase ON (Exp 2), the average gap to full-scan is 4.24pp. s1196 (−0.13pp) and s5378 (−0.23pp) exceed full-scan coverage because more time frames provide additional propagation paths. s1238 (0.02pp gap) is effectively at parity. The remaining gap is concentrated in b04 (9.00pp), b05 (7.66pp), and s953 (5.65pp), where non-scan FF topology creates faults with no observable path at any sequential depth.

Two sources of the gap:

1. **AU faults under partial scan:** Faults whose only observable path passes through a non-scan FF output are untestable even at T=2 if the FF value cannot be justified within the backtrack budget. These are structural limitations of the 10% non-scan configuration.
2. **UD faults (QN-pin, faultyLine = -4):** Stuck-at faults on the complementary output (QN) of flip-flops are excluded from FAN_ATPG's pattern generation at any frame depth. These contribute ≈0.1 pp to the gap.

### 8.5 Circuit-Size Scaling

The T=2 gain depends on the structural relationship between the 10% non-scan FFs and the fan-out cones of the residual faults, not simply on circuit size. Small circuits with severe non-scan FF blocking (s953: T=1 ≈ 37%) show huge T=2 gains with Two-Phase ON (+54.51pp). Circuits where non-scan FFs do not block the fault propagation path (b08: T=1 ≈ 73%) show more modest gains even with Two-Phase. Circuit size alone is not predictive of pipeline effectiveness.

### 8.6 Why Enhanced Backtrace and Static Learning Fail

Exp 4 and Exp 5 test whether better backtrace selection or early conflict detection can improve the baseline pipeline. Both show negligible impact (+0.47pp and +0.00pp respectively). The reason is structural: the bottleneck is not backtrace quality or conflict detection speed, but the interleaving of propagation and state justification in the unified search. No amount of backtrace optimization within the single-search framework can overcome this — it requires the Two-Phase decoupling approach.

### 8.7 Memory Cost of Multi-Frame Expansion

Our measurements confirm the expected trade-off cited in sequential ATPG literature [3]: deeper frames increase memory. In our pipeline, T=4 VmPeak exceeds T=1 on every circuit because time-frame unrolling grows the circuit representation. However, absolute peaks remain small on all 10 evaluated circuits (≤32 MB VmPeak), and ablation configurations that dramatically change FC or runtime — especially Two-Phase ON and enhanced backtrace — do not proportionally increase memory. The practical implication is that the recovery gains from Two-Phase sequential ATPG (§7.3–7.4) are achievable without a large memory penalty at T≤4. Residual targeting reduces ATPG *runtime* by shrinking target fault sets at T>1, but does not reduce the unrolled circuit size, which is why T=4 memory tracks frame depth rather than residual count.

---

## 9. Related Work

### 9.1 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses the problem of generating tests for sequential circuits where internal state is not directly controllable. The standard approach is time-frame expansion: the circuit is unrolled across T clock cycles, and combinational ATPG is applied to the unrolled model [1][2]. The FAN algorithm [1] with backtrack-based search is the foundation of FAN_ATPG. Deeper frames can increase fault detectability by providing more initialization cycles, but also increase search space, memory, and runtime [3].

Our work applies time-frame expansion specifically to partial-scan circuits where non-scan FFs create sequential behavior, and evaluates the incremental benefit of deeper frames through progressive residual targeting.

### 9.2 Partial Scan Design

Partial scan reduces area and timing overhead by scanning only a subset of FFs. Classic methods select scan FFs based on testability metrics (SCOAP), structural loop-breaking, or sequential depth reduction [4][5][6]. More recent work considers timing and power constraints in scan FF selection [7][8][9].

We do **not** propose a new scan selection method. Our non-scan FF set is determined by a fixed timing-prioritized ranking (top x% by minimum-path-slack). The partial-scan circuit is the constrained input to our sequential ATPG evaluation.

### 9.3 Fault Dropping and Residual Targeting

In standard ATPG flows, detected faults are dropped from the target list to avoid redundant pattern generation [10]. Fault dropping is typically within a single ATPG run and not exported across runs. Test compaction techniques further reduce pattern count by targeting multiple faults per pattern [11].

Our progressive residual list extends fault dropping across multiple time-frame depths: faults detected at T=1 are excluded from T=2/T=4, and faults detected by residual T=2 are excluded from residual T=4. This is conceptually fault dropping staged across sequential depth, not a new dropping algorithm.

### 9.4 Timing-Constrained Scan

Scan insertion adds multiplexer delay on functional paths, which can make critical paths fail timing closure. FFs on these paths may be excluded from scan [12][13]. The resulting partial-scan circuit has a fixed set of non-scan FFs determined by timing, not by testability optimization.

Our timing-prioritized non-scan selection approximates this scenario using OpenSTA minimum-path-slack ranking. We do not claim to perform full timing-closure-aware scan synthesis including scan-mux delay modeling.

### 9.5 Low-Power Scan and Test Power

Test power during scan shift is an active research area [7][14][15]. Scan-chain reordering, X-filling, and segmented activation are used to reduce shift power. This work does **not** address test power; non-scan FF selection is timing-driven, not power-driven.

---

## 10. Limitations and Threats to Validity

1. **Benchmark coverage.** Two suites: ITC'99 (8 circuits, 29–88 FFs) and ISCAS'89 (7 circuits, 18–1728 FFs). Larger industrial circuits were not evaluated.
2. **Backtrack limit sensitivity.** Results depend on the choice of T1=800 (T=1) and BACKTRACK=5000 (T>1). A lower T=1 limit would increase the residual at the risk of aborting faults that could have been DT with more search. A higher T=1 limit would reduce the residual but increase T=1 runtime.
3. **Two baselines.** Report **B1** (partial T=1) and **B2** (full-scan) for every circuit. All runs use the same binary and backtrack limits.
4. **s27 is toy-scale** (3 FFs, +43.9pp gain). Used for pipeline verification only — see §6.1.
5. **Shallow depth.** T=8 not evaluated; T=4 adds 0 gain universally.
6. **Mask/netlist alignment.** Regenerate `masks/<circuit>_x10.mask` after netlist changes.
7. **AU semantics.** FAN AU is operational (search failure within budget), not a formal untestability proof.
8. **Single ATPG backend.** Cross-tool validation not performed.

---

## 11. Conclusion

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with a **frame-based backtrack limit** (T1=800 at T=1, 5000 at T>1) and a suite of **five controlled ablation experiments** (baseline, Two-Phase ON, uniform T1, enhanced backtrace, static learning) evaluated on **10 circuits** (6 ITC'99 + 4 ISCAS'89) at **10% non-scan exclusion** (5 additional circuits excluded: b11/s35932 runner crash, b13/s9234/s15850 timeout). There is **no per-target timeout** — the backtrack limit is the sole bounding mechanism.

**Key findings:**

1. **The baseline pipeline (Two-Phase OFF) recovers 10.10pp average gain** (73.48% vs 63.38% T=1 alone). T=2 recovers 7.07pp on average while T=4 adds 3.04pp — the majority of recovery comes from T=2, but T=4 contributes meaningfully when Two-Phase is OFF.

2. **Two-Phase State Justification is the dominant recovery mechanism.** Enabling it increases average FC to 90.42% (+16.94pp vs baseline). Individual circuits show dramatic gains: b05 +58.49pp, s953 +54.51pp, b07 +31.80pp. With Two-Phase ON, T=2 recovers everything — T=4 adds **0 pp universally**.

3. **The T1 backtrack limit differential does not create the residual.** Raising T1 from 800 to 5000 (Exp 3) changes average FC by only +0.02pp. Faults blocked by non-scan FF X-state are structurally unrecoverable at any T=1 backtrack budget — they require T>1 frames regardless.

4. **Enhanced backtrace (+0.47pp) and static learning (+0.00pp) produce negligible improvement.** These heuristics do not address the fundamental bottleneck: non-scan FF X-state blocking at T=1.

5. **The gap to full-scan narrows from 31.26pp (T=1 alone) to 4.24pp (Exp 2, Two-Phase ON).** s1196 and s5378 match or exceed their full-scan coverage; s1238 is within 0.02pp of parity. This suggests that for circuits with favorable non-scan topology, Two-Phase sequential recovery can approach parity with full-scan targeting.

6. **T=4 recovers additional faults only when Two-Phase is OFF.** Without Two-Phase, the unified search struggles at T=2 and leaves some faults for T=4. With Two-Phase ON, the decoupled approach is sufficient at T=2 depth. This confirms that the bottleneck is not frame depth but the interleaving of propagation and justification in the unified search.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/exp1_baseline.csv` | Exp 1: Baseline (T1=800, TP=OFF); includes T1/T2/T4/peak memory (MB) |
| `results/exp2_two_phase.csv` | Exp 2: Two-Phase ON |
| `results/exp3_uniform_T1.csv` | Exp 3: Uniform T1=5000 |
| `results/exp4_enhanced_backtrace.csv` | Exp 4: Enhanced Backtrace |
| `results/exp5_static_learning.csv` | Exp 5: Static Learning |
| `results/phase_d_fullscan_dataset.csv` | **B2** ITC'99 full-scan baseline |
| `results/iscas89_fullscan_baseline.csv` | **B2** ISCAS'89 full-scan baseline |
| `results/residual_faults/` | Per-stage residual fault list files |
| `masks/*_slack.csv`, `masks/*_x10.mask` | OpenSTA slack ranking + non-scan masks |
| `results/sweep_log.txt` | Master sweep execution log |

### B. Engineering Fixes

| Issue | Resolution |
|-------|-----------|
| Floating nets rejected by FAN_ATPG | ERROR→WARN |
| `_const0_` as free module port | LOGIC0/LOGIC1 tie cells |
| Level-indexed array OOB crashes | `maxGateLevel+1` sizing |
| Stale masks after re-synthesis | `gen_nonscan_masks.sh` |
| `report_fault` prints nothing | Fix inverted logic |
| DFF faults lack instance names | Print cell name |
| ISCAS'89 TTU double-module stub | Track `in_target_module` in converter |

### C. Open Follow-ups

| Item | Status |
|------|--------|
| Experiments 1–5 sweep | 10 common circuits complete; 5 excluded (b11/s35932 runner crash, b13/s9234/s15850 timeout at 600s) |
| T=8 pipeline depth | Not evaluated; T=4 adds 0 pp with Two-Phase ON, confirms shallow depth suffices |
| Non-scan FF selection (cone-aware) | Timing-slack selection; cone-aligned selection may reduce B2−Exp gap |
| UD faults (QN, l=-4) | Structurally untestable in B1 and B2; not reducible by frame depth |
| b03 full-scan AU blocker | PID stale from Jun 9; separate issue |
| b11 runner crash | Runner produces empty output with no error — root cause unknown |



## References

[1] H. Fujiwara and T. Shimono, "On the acceleration of test generation algorithms," *IEEE Trans. Computers*, vol. C-32, no. 12, pp. 1137–1144, 1983.

[2] M. Abramovici, M. A. Breuer, and A. D. Friedman, *Digital Systems Testing and Testable Design*. IEEE Press, 1990.

[3] T. M. Niermann and J. H. Patel, "HITEC: A test generation package for sequential circuits," *Proc. European Design Automation Conf.*, pp. 214–218, 1991.

[4] V. D. Agrawal, K.-T. Cheng, D. D. Johnson, and T. Lin, "A complete solution to the partial scan problem," *Proc. ITC*, pp. 44–51, 1987.

[5] K.-T. Cheng and V. D. Agrawal, "A partial scan method for sequential circuits with feedback," *IEEE Trans. Computers*, vol. 39, no. 4, pp. 544–548, 1990.

[6] V. Chickermane and J. H. Patel, "An optimization based approach to the partial scan design problem," *Proc. ITC*, pp. 377–386, 1990.

[7] S. Remersaro et al., "Scan cell reordering for peak power reduction during scan test cycles," *Proc. ATS*, pp. 231–236, 2007.

[8] X. Lin et al., "Scan chain reordering-aware X-filling and stitching for scan shift power reduction," *Proc. DATE*, pp. 1–6, 2016.

[9] M. Cho and D. Z. Pan, "PEAKASO: Peak-temperature aware scan-vector optimization," *Proc. VTS*, pp. 231–236, 2006.

[10] I. Pomeranz and S. M. Reddy, "On improving the stuck-at fault coverage of functional test sequences by using limited-scan operations," *IEEE Trans. VLSI*, vol. 12, no. 7, pp. 780–788, 2004.

[11] I. Hamzaoglu and J. H. Patel, "Test set compaction algorithms for combinational circuits," *IEEE Trans. CAD*, vol. 19, no. 8, pp. 957–963, 2000.

[12] K. D. Wagner, "Design for testability of mixed signal integrated circuits," *Proc. ITC*, pp. 823–828, 1988.

[13] T.-C. Lee et al., "A DFT methodology for at-speed scan testing with timing exception paths," *Proc. ATS*, 2020.

[14] P. M. Rosinger et al., "Analysing trade-offs in scan power and test data compression for SoCs," *IEEE Trans. CAD*, 2004.

[15] K. M. Butler et al., "Minimizing power consumption in scan testing: pattern generation and DFT techniques," *Proc. ITC*, pp. 355–364, 2004.

[16] F. Corno, M. S. Reorda, and G. Squillero, "RT-level ITC'99 benchmarks and first ATPG results," *IEEE Design & Test*, vol. 17, no. 3, pp. 44–53, 2000.
