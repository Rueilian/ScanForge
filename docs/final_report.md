# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. Non-scan FF outputs are unknown (X) at T=1, making faults whose propagation path passes through them **AU** (atpg untestable) in a single frame. We implement two contributions on FAN_ATPG: **(1)** a **Two-Phase State Justification** engine that decouples fault propagation (last frame) from state justification (earlier frames), enabling efficient multi-frame search; and **(2)** a **progressive residual T=1→T=2→T=4 pipeline** with per-target timeout (ptt=5s) for runtime feasibility. We evaluate on **two benchmark suites**: **ITC'99** (b03–b13, 8 circuits) and **ISCAS'89** (s953–s38584, 9 circuits), all at **10% non-scan exclusion**.

Key findings: **(1)** Two-Phase state justification at T=2 recovers faults that are structurally AU at T=1 — **14/17 circuits show substantial gain** (ITC'99: +4.68–58.53pp, ISCAS'89: +12.27–54.51pp for 6 circuits); 3 large ISCAS'89 circuits (s35932, s38417, s38584) show minimal gain (+0.05–0.47pp) because T=1 already exceeds 87% FC with the higher-backtrack engine configuration. **(2)** T=4 adds **0 pp universally** on all 17 circuits — two frames are sufficient for the sequential depth of these synthesized circuits. **(3)** The pipeline narrows the gap to full-scan from 1.47–66.14pp (T=1 alone) to 0.47–9.12pp (pipeline).

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

### 1.2 Problem

In a partial-scan circuit at T=1, non-scan FF outputs are in an unknown (X) initial state. Any fault whose propagation path passes through a non-scan FF primary output (PPO) is therefore **structurally untestable in a single frame** — classified AU (atpg untestable) by the ATPG engine. Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state can be justified through functional clocking — can recover some of this lost coverage.

However, deeper frames increase the search space. Standard multi-frame ATPG interleaves fault propagation (in the last frame) and state justification (in earlier frames) within a single backtrack search, causing propagation backtrack explosions to exhaust the budget before state justification begins.

A separate engineering dimension is the **per-target timeout (ptt)**: the maximum time spent on a single fault. Large circuits may stall on structurally hard faults; a uniform ptt bounds this cost across all pipeline stages.

### 1.3 Proposed Approach

We implement a *progressive residual multi-frame ATPG* flow with two core contributions:

**Contribution 1 — Two-Phase State Justification (engine):** Decouples propagation from state justification. Phase 1 solves PODEM on the last frame only (treating non-scan PPIs as free PIs). If Phase 1 succeeds, Phase 2 backward-justifies the required PPI values through frames 0..T−2 with a fresh backtrack budget. This prevents propagation explosions from starving state justification.

**Contribution 2 — Progressive Residual Pipeline (methodology):**
1. Runs T=1 on all original physical faults (ptt=5s).
2. Constructs a residual fault list R1 = All − D1 (detected by T=1).
3. Runs T=2 **only** on R1 (Two-Phase ON, ptt=5s).
4. Constructs R2 = R1 − D2.
5. Runs T=4 **only** on R2.
6. Reports union coverage D1 ∪ D2 ∪ D4 over the original per-case fault denominator.

ptt=5s is a **runtime enabler**: it limits T=1 effort on faults that are structurally AU at single frame, allowing large circuits to complete within wall timeout. The recovery mechanism is Two-Phase at T=2, not the timeout itself.

### 1.4 Scope and Positioning

This work does **not** propose a new partial-scan selection method or a new fault model. Timing-driven non-scan FF selection uses OpenSTA minimum-path-slack ranking at a **fixed 10%** exclusion ratio — **experimental setup only**. The **research focus** is:

1. **Does Two-Phase state justification at T=2 recover faults that are AU at T=1?**
2. **Does deeper staging (T=4) recover additional faults beyond T=2?**
3. **What is the runtime cost of each stage relative to the coverage gain?**

Cross-ratio comparison of absolute partial-scan FC is **not** part of this study; only **x = 10%** is evaluated.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF participates in the scan chain. ATPG can set any FF state arbitrarily in one cycle. In partial scan, some FFs (non-scan) are excluded from the chain. At T=1 with unknown (X) initial state, non-scan FFs are uncontrollable — their values cannot be set by scan loading.

### 2.2 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses partial-scan controllability by unrolling the circuit across T time frames. Each frame is a copy of the combinational portion of the circuit. Non-scan FF outputs (PPOs) at frame t connect to their inputs (PPIs) at frame t+1, while scan FF PPIs remain independently controllable at each frame. The initial state at frame 0 is typically X. T=1 is a single-frame model where non-scan FF PPOs remain X; T>1 provides initialization cycles to justify non-scan FF state.

### 2.3 FAN_ATPG and PARTIAL_SEQUENTIAL Mode

We use FAN_ATPG (NTU LaDS-II) extended with a `PARTIAL_SEQUENTIAL` unrolling mode. Non-scan FFs propagate state across frames via BUF connections; scan FF PPIs are free at each frame. The `set_nonscan_ff` command designates non-scan FFs. The `set_per_target_timeout` command limits ATPG effort per fault.

### 2.4 Fault Classes

After ATPG, each stuck-at fault is classified as:

- **DT** (detected): a test pattern was found.
- **AU** (atpg untestable): the ATPG engine determined no pattern exists within the search limit.
- **AB** (abort): the engine reached its backtrack limit before finding a pattern.
- **TO** (timeout): per-target time expired; testability not determined.
- **UD** (undetected): the fault was not targeted.

Fault coverage FC = DT / (DT + AU + AB + TO + UD).

### 2.5 Per-Target Timeout and Its Role

Without a per-target timeout, FAN_ATPG may spend unbounded time on a single structurally hard fault, stalling the run. With `set_per_target_timeout T`, faults unresolved after T seconds become TO (timeout). In this work, ptt=5s serves as a **runtime enabler**: it caps T=1 effort on faults that are structurally AU at single frame (non-scan FF X-state blocked), preventing them from consuming hours of search time. These faults become TO at T=1 and are retried at T=2.

**Important**: The recovery mechanism is Two-Phase state justification at T=2, not the ptt. Even without ptt, T=1 would classify these faults as AU after exhaustive search, and T=2 would still recover them — but T=1 might take too long on large circuits.

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

1. **RQ1 (pipeline gain):** For a fixed partial-scan circuit, how many percentage points does FC(T1∪T2∪T4) exceed FC(T1)?
2. **RQ2 (stage attribution):** How much of that gain comes from residual T=2 vs residual T=4?
3. **RQ3 (cost):** What are the T=1 / T=2 / T=4 runtimes, and is deeper staging justified by recovered fault count?

**Important:** For each (circuit, ratio) case, all comparisons use the same T=1 collapsed fault set F as denominator. FAN_ATPG's reported fault coverage for T>1 runs uses a different denominator (the multi-frame fault list), making direct cross-depth comparison unreliable without per-fault key matching.

**Full-scan baseline metric:** We report **FC_scan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice, async reset/control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator.

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

This decoupling prevents propagation backtrack explosions from exhausting the budget before state justification begins, and concentrates engine effort on the subproblem that is actually failing. The `useTwoPhaseJustification_` mode is **enabled by default** and active for all T>1 pipeline stages.

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
| `scripts/run_progressive_residual_iscas89_sweep.py` | ISCAS'89 sweep driver (9 circuits) |
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
| FAN compound-gate modeling sprawl | Keep **`Gate::MUX`** (Phase D1); **revert OAI/AOI atomic gates** (D3.2/D3.3) after pipeline validation |
| ISCAS'89 TTU double-module stub | Track `in_target_module` flag in `convert_ttu_to_nangate.py` to skip `module dff(CK,Q,D)` primitives |

These are infrastructure fixes; they are not claimed as research contributions.

---

## 6. Experimental Setup

### 6.1 Benchmarks

We evaluate on two benchmark suites.

**Testset A — ITC'99** (synthesized to NanGate45 via Yosys with base-gate library):

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

**Testset B — ISCAS'89** (TTU gate-level netlists converted to NanGate45 SDFFR_X1):

| Circuit | FFs | Non-scan @10% | Full-scan B2 |
|---------|----:|-------------:|-------------:|
| s953    |  29 |  3 | 97.79% |
| s1196   |  18 |  2 | 98.87% |
| s1238   |  18 |  2 | 96.36% |
| s5378   | 179 | 18 | 96.65% |
| s9234   | 211 | 22 | 93.09% |
| s15850  | 534 | 54 | 96.04% |
| s35932  | 1728 | 173 | 88.20% |
| s38417  | 1636 | 164 | 97.10% |
| s38584  | 1426 | 143 | 93.58% |

Circuits s27 and s510 (< 10 FFs) are excluded from the pipeline evaluation; s27 is retained as a sanity check only. ISCAS'89 full-scan B2 was measured under the same ptt = 5 s setting (see §6.3).

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

### 6.3 ATPG Configuration

All runs — full-scan baseline and pipeline — use a **unified** configuration:

- Fault model: stuck-at (SAF)
- Pipeline depths: T=1 (all faults), T=2 (residual R1), T=4 (residual R2)
- Engine: **Two-Phase State Justification ON** for all T>1 stages
- Static/dynamic compression: **off** (progressive residual runner)
- **Per-target timeout: 5 s** (`set_per_target_timeout 5.0`), applied uniformly to all circuits and all pipeline stages
- **Wall timeout: 3600 s**, applied via Python `subprocess.run(timeout=3600)`
- Results: `results/progressive_residual_summary.csv` (17 circuits × 1 ratio = 17 runs)

**Rationale for ptt = 5 s:** Without a per-target timeout, large ISCAS'89 circuits (particularly s38417, 1636 FFs) cannot complete within a 3600 s wall timeout — a handful of structurally difficult faults monopolize the ATPG engine. A uniform ptt = 5 s ensures all circuits finish within wall timeout and maintains methodological consistency. ptt is a **runtime enabler**, not the recovery mechanism.

### 6.4 Metrics and Baselines

**Two baselines** anchor all reporting:

| Baseline | Setup | Metric | Source |
|----------|-------|--------|--------|
| **B1 — Partial-scan T=1** | 10% non-scan, ptt=5s | **FC_T1** | `progressive_residual_summary.csv` |
| **B2 — Full-scan** | All FFs scan, T=1, ptt=5s | **FC_fullscan** | `iscas89_fullscan_baseline.csv` (ISCAS'89); `phase_d_fullscan_dataset.csv` (ITC'99, ptt=0) |

Pipeline and comparison metrics (same T=1 fault denominator |F|):

| Metric | Definition | Compares |
|--------|------------|----------|
| **FC_T1** | \|D1\| / \|F\| | **B1** |
| **FC_T1_T2_T4** | \|D1 ∪ D2 ∪ D4\| / \|F\| | **Experiment** (T=1→T=2→T=4) |
| **gain_T2_pp** | FC_T1_T2 − FC_T1 | T=2 stage gain |
| **gain_T4_pp** | FC_T1_T2_T4 − FC_T1_T2 | T=4 stage gain |
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 | Experiment vs **B1** |
| **B2−Experiment** | FC_fullscan − FC_T1_T2_T4 | Remaining gap to full-scan |

---

## 7. Results

### 7.1 Sanity Case: s27 (3 FFs, 67% non-scan)

s27 is treated as a sanity/toy case to verify that the pipeline correctly implements progressive residual targeting.

| Method | FC | Gain vs T=1 |
|--------|----:|-----------:|
| T=1 | 37.9% | baseline |
| T=1→T=2→T=4 | 81.8% | +43.9pp |

The +43.9pp gain demonstrates that the pipeline correctly recovers faults limited by non-scan FF controllability. **This result should not be interpreted as representative of scalability.** s27 has only 3 FFs.

### 7.2 Primary Results: ITC'99 (@10% Non-Scan, ptt=5s)

| Circuit | \|F\| | **B1** FC_T1 | **Exp** T1+T2+T4 | **B2** Full-scan | Exp−B1 | B2−Exp | +DT@T2 | +DT@T4 |
|---------|------:|------------:|----------------:|-----------------:|-------:|-------:|-------:|-------:|
| b03 | 809 | 44.50% | 85.41% | 91.62% | +40.91 | +6.21 | 331 | 0 |
| b04 | 2291 | 75.21% | 84.46% | 93.46% | +9.25 | +9.00 | 212 | 0 |
| b05 | 4471 | 29.10% | 87.63% | 95.34% | +58.53 | +7.71 | 2617 | 0 |
| b07 | 1591 | 56.13% | 87.93% | 93.46% | +31.80 | +5.53 | 506 | 0 |
| b08 | 2234 | 72.96% | 91.09% | 94.03% | +18.13 | +2.94 | 405 | 0 |
| b09 | 930 | 76.34% | 87.85% | 93.44% | +11.51 | +5.59 | 107 | 0 |
| b11 | 6843 | 66.21% | 94.32% | 97.43% | +28.10 | +3.11 | 1923 | 0 |
| b13 | 2007 | 77.33% | 82.01% | 91.13% | +4.68 | +9.12 | 94 | 0 |

ITC'99 B2 values are from `results/phase_d_fullscan_dataset.csv` (run without ptt for reference).

### 7.3 Primary Results: ISCAS'89 (@10% Non-Scan, ptt=5s)

| Circuit | \|F\| | **B1** FC_T1 | **Exp** T1+T2+T4 | **B2** Full-scan | Exp−B1 | B2−Exp | +DT@T2 | +DT@T4 |
|---------|------:|------------:|----------------:|-----------------:|-------:|-------:|-------:|-------:|
| s953    | 1853 | 36.75% | 91.26% | 97.79% | +54.51 | +6.53 | 1010 | 0 |
| s1196   | 2184 | 86.13% | 98.40% | 98.87% | +12.27 | +0.47 |  268 | 0 |
| s1238   | 2235 | 82.42% | 95.12% | 96.36% | +12.71 | +1.24 |  284 | 0 |
| s5378   | 10113 | 74.24% | 94.94% | 96.65% | +20.70 | +1.71 | 2093 | 0 |
| s9234   | 18098 | 72.89% | 88.18% | 93.09% | +15.29 | +4.91 | 2768 | 0 |
| s15850  | 33265 | 66.13% | 90.15% | 96.04% | +24.02 | +5.89 | 7991 | 0 |
| s35932  | 77978 | 87.59% | 87.64% | 88.20% | +0.05 | +0.56 |   39 | 0 |
| s38417  | 82810 | 95.22% | 95.69% | 97.10% | +0.47 | +1.41 |  390 | 0 |
| s38584  | 81247 | 92.58% | 92.66% | 93.58% | +0.08 | +0.92 |   62 | 0 |

### 7.4 Key Observations

1. **T=2 gains are substantial for 14/17 circuits.** ITC'99: +4.68–58.53pp. ISCAS'89 (6 circuits): +12.27–54.51pp. **Three large ISCAS'89 circuits — s35932, s38417, s38584 — show minimal T=2 gain (+0.05–0.47pp)** because T=1 already achieves >87% FC (s35932: 87.59%, s38417: 95.22%, s38584: 92.58%). The improved engine configuration (origin/swear branch with BACKTRACK_LIMIT=5000) enables T=1 to prove most faults DT even in single frame, leaving a small residual.

2. **T=4 is universally zero.** +DT@T4 = 0 on all 17 circuits. Residual faults not recovered by T=2 are not recovered by T=4 either. Two frames are sufficient for the sequential depth of these synthesized circuits; the T=4 stage is redundant.

3. **Remaining gap to full-scan is 0.47–9.12 pp.** ITC'99: 2.94–9.12pp. ISCAS'89: 0.47–6.53pp. The pipeline substantially narrows the gap vs B1 alone, but does not close it completely.

4. **Runtime cost.** T=1 dominates (0.11–111.33 s). T=2 adds 0.09–147.08 s. T=4 adds minimal time (0.11–200.87 s) with zero new detections. For s38417, ptt=5 enables completion: T=1 = 92.28 s, T=2 = 92.82 s, T=4 = 83.82 s.

5. **Recovery mechanism confirmed.** For circuits with large T=2 gain, the recovered faults are structurally AU at T=1 (non-scan FF X-state blocked) and become DT at T=2 through Two-Phase state justification. For large circuits with high T=1 FC, the recovery is small because few faults remain in the residual.

---

## 8. Discussion

### 8.1 Why T=2 Recovers Faults That T=1 Misses

At T=1 with a partial-scan circuit, non-scan FF outputs are in an unknown (X) state. Faults whose propagation path requires a specific non-scan FF value are structurally **AU** — the ATPG engine correctly determines that no single-frame test exists. These are not timeout artifacts; they are genuine untestable faults at depth T=1.

Two-Phase State Justification at T=2 recovers these faults through a two-step process:

1. **Phase 1 (propagation in frame 1):** Non-scan FF PPIs in frame 1 are temporarily decoupled from their driving frame-0 outputs and treated as free primary inputs. The engine can now assign any logic value to these PPIs, creating a propagation path from the fault site to an observable output. At T=1, no such decoupling exists — the non-scan FF PPO is X and blocks propagation.

2. **Phase 2 (state justification in frame 0):** For each PPI value assigned in Phase 1, the engine checks whether that value can be justified through the frame-0 logic cone (from PIs and scan-FF outputs). If the non-scan FF has a functional path from a controllable source (scan FF or PI), justification succeeds and the fault is classified DT.

The fault types recovered are:

- **Non-scan-FF-blocked faults:** Propagation requires a specific non-scan FF output value (e.g., 0 to enable a pass-transistor or AND gate input). At T=1 the value is X; at T=2, Phase 1 assigns the needed value, Phase 2 justifies it.
- **State-dependent faults:** Detection requires sequential initialization. At T=2, frame 0 can initialize the circuit state before frame 1 propagates the fault.

### 8.2 The Role of Per-Target Timeout

The ptt parameter serves as a **runtime enabler**, not a recovery mechanism:

- **Without ptt:** T=1 spends unbounded backtrack search on faults that are structurally AU at single frame. The engine will eventually classify them AU (after hitting the backtrack limit), but this can take hours per fault on large circuits.
- **With ptt=5 s:** T=1 caps effort at 5 s per fault. Hard faults become TO rather than consuming the full backtrack budget. These TO faults are passed to T=2, where Two-Phase recovers most of them.

The key insight: **the recovery would also occur without ptt** (T=1 would eventually AU, T=2 would DT), but ptt makes the pipeline practically feasible by bounding T=1 runtime. The ptt does not create the AU-to-DT conversion; Two-Phase does.

### 8.3 T=4 Adds Nothing

On all 17 circuits, T=4 adds 0 new detections to the T=2 residual. This result holds across both benchmark suites and across circuit sizes from 18 FFs (s1196) to 1728 FFs (s35932). The residual after T=2 consists of faults that are:

- **Structurally AU at 2+ frames** (non-scan FF state does not influence fault propagation even with multi-frame initialization), or
- **TO at T=2** within ptt=5 s — and equally time-limited at T=4.

Two frames are sufficient because the non-scan FFs in these synthesized circuits have a maximum sequential depth of 1 through non-scan logic: frame 0 provides initialization, frame 1 propagates. Additional frames do not unlock new state reachability.

### 8.4 Remaining Gap to Full-Scan

The gap **B2 − Experiment** (0.47–9.12 pp) represents coverage achievable by full scan but not by the progressive pipeline. This gap arises from two sources:

1. **AU faults under partial scan:** Faults whose only observable path passes through a non-scan FF output are untestable even at T=2 if the FF value cannot be justified within the time budget. These are structural limitations of the 10% non-scan configuration.
2. **UD faults (QN-pin, faultyLine = −4):** Stuck-at faults on the complementary output (QN) of flip-flops are excluded from FAN_ATPG's pattern generation at any frame depth (the condition `faultyLine >= 0` in `atpg.cpp`). These faults appear as UD in both B1 and B2 and contribute ≈0.1 pp to the gap.

### 8.5 Circuit-Size Scaling

The T=2 gain depends on the structural relationship between the 10% non-scan FFs and the fan-out cones of the residual faults, not simply on circuit size. Small circuits with severe non-scan FF blocking (s953: T=1 = 36.75%) can show very large T=2 gains (+54.51pp). Large circuits like s35932, s38417, and s38584 show minimal gains (+0.05–0.47pp) because their T=1 coverage is already high (87.59–95.22%) with the higher-backtrack engine configuration — the non-scan FFs at 10% exclusion do not block enough faults to create a meaningful T=2 residual.

### 8.6 Priority Scoring (Negative Result)

Static fault priority scoring (observability/controllability distance, cone size, fanout) showed **no lift over random ordering** for predicting T=2/T=4 recovery. Abandoned.

---

## 9. Related Work

### 9.1 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses the problem of generating tests for sequential circuits where internal state is not directly controllable. The standard approach is time-frame expansion: the circuit is unrolled across T clock cycles, and combinational ATPG is applied to the unrolled model [1][2]. The FAN algorithm [1] with backtrack-based search is the foundation of FAN_ATPG. Deeper frames can increase fault detectability by providing more initialization cycles, but also increase search space, memory, and runtime [3].

Our work applies time-frame expansion specifically to partial-scan circuits where non-scan FFs create sequential behavior, and evaluates the incremental benefit of deeper frames through progressive residual targeting.

### 9.2 Partial Scan Design

Partial scan reduces area and timing overhead by scanning only a subset of FFs. Classical methods select scan FFs based on testability metrics (SCOAP), structural loop-breaking, or sequential depth reduction [4][5][6]. More recent work considers timing and power constraints in scan FF selection [7][8][9].

We do *not* propose a new scan selection method. Our non-scan FF set is determined by a fixed timing-prioritized ranking (top x% by minimum-path-slack). The partial-scan circuit is the constrained input to our sequential ATPG evaluation.

### 9.3 Fault Dropping and Residual Targeting

In standard ATPG flows, detected faults are dropped from the target list to avoid redundant pattern generation [10]. Fault dropping is typically within a single ATPG run and not exported across runs. Test compaction techniques further reduce pattern count by targeting multiple faults per pattern [11].

Our progressive residual list extends fault dropping across multiple time-frame depths: faults detected at T=1 are excluded from T=2/T=4, and faults detected by residual T=2 are excluded from residual T=4. This is conceptually fault dropping staged across sequential depth, not a new dropping algorithm.

### 9.4 Timing-Constrained Scan

Scan insertion adds multiplexer delay on functional paths, which can make critical paths fail timing closure. FFs on these paths may be excluded from scan [12][13]. The resulting partial-scan circuit has a fixed set of non-scan FFs determined by timing, not by testability optimization.

Our timing-prioritized non-scan selection approximates this scenario using OpenSTA minimum-path-slack ranking. We do not claim to perform full timing-closure-aware scan synthesis including scan-mux delay modeling.

### 9.5 Low-Power Scan and Test Power

Test power during scan shift is an active research area [7][14][15]. Scan-chain reordering, X-filling, and segmented activation are used to reduce shift power. This work does *not* address test power; non-scan FF selection is timing-driven, not power-driven.

---

## 10. Limitations and Threats to Validity

1. **Benchmark coverage.** Two suites: ITC'99 (8 circuits, 29–88 FFs) and ISCAS'89 (9 circuits, 18–1728 FFs). Larger industrial circuits not evaluated.
2. **ptt sensitivity.** Results depend on ptt = 5 s choice. Smaller ptt reduces T=1 coverage but increases T=2 opportunity; larger ptt (or ptt=0) may allow T=1 to prove more faults AU, reducing T=2 gain. The unified ptt=5 s was chosen for feasibility of large circuits (s38417).
3. **Two baselines.** Report **B1** (partial T=1) and **B2** (full-scan) for every circuit. ITC'99 B2 values are from prior ptt=0 runs; ISCAS'89 B2 values use ptt=5 s (consistent with pipeline).
4. **s27 is toy-scale.** +43.9pp vs B1 is pipeline verification only.
5. **Shallow depth.** T=8 not evaluated; T=4 adds 0 gain universally on current sweeps.
6. **Mask/netlist alignment.** Regenerate `masks/<circuit>_x10.mask` after netlist changes.
7. **AU semantics.** FAN AU is operational (search failure within budget), not a formal untestability proof.
8. **Single ATPG backend.** Cross-tool validation not performed.

---

## 11. Conclusion

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with Two-Phase State Justification and fixed-denominator union accounting, evaluated on **two benchmark suites** (8 ITC'99 + 9 ISCAS'89 circuits) under a **unified per-target timeout of 5 s**.

**Key findings:**

1. **Two-Phase state justification at T=2 recovers faults that are structurally AU at T=1** due to non-scan FF X-state blocking. 14/17 circuits show substantial T=2 gain: +4.68–58.53pp (ITC'99) and +12.27–54.51pp (ISCAS'89, 6 circuits). Three large ISCAS'89 circuits (s35932, s38417, s38584) show minimal gain (+0.05–0.47pp) because T=1 already achieves >87% coverage with the higher-backtrack engine configuration.

2. **T=4 adds 0 pp universally.** On all 17 circuits from both suites, the residual T=4 stage detects no new faults. A T=1 → T=2 two-stage pipeline captures the full attainable pipeline coverage; T=4 is redundant under this methodology.

3. **Remaining gap to full-scan is 0.47–9.12 pp.** The pipeline substantially narrows the partial-scan coverage penalty but does not eliminate it. Residual AU faults (beyond the reach of 2-frame justification) and QN-pin UD faults (structurally excluded from ATPG targeting) account for the gap.

4. **ptt = 5 s enables large-circuit completion** without being the recovery mechanism itself. s38417 (1636 FFs) was previously infeasible at ptt=30 s (>3600 s wall); at ptt=5 s it completes within wall timeout. The recovery is driven by Two-Phase state justification, not the timeout.

5. **Two-Phase State Justification** is the core engine contribution. By decoupling frame-1 propagation from frame-0 state justification, it makes multi-frame ATPG practically effective on partial-scan circuits.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/progressive_residual_summary.csv` | B1 + pipeline (17 circuits: 8 ITC'99 + 9 ISCAS'89, @10%, ptt=5s) |
| `results/iscas89_fullscan_baseline.csv` | **B2** full-scan for ISCAS'89 (ptt=5s) |
| `results/phase_d_fullscan_dataset.csv` | **B2** full-scan for ITC'99 (ptt=0, reference) |
| `results/residual_faults/` | Per-stage residual fault list files |
| `masks/*_slack.csv`, `masks/*_x10.mask` | OpenSTA slack ranking + non-scan masks |
| `results/logs/` | Sweep run logs (fullscan, ITC'99, ISCAS'89) |

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
| ITC'99 B2 at ptt=5s | Not yet run; current B2 from ptt=0 reference run |
| T=8 pipeline depth | Not evaluated; T=4 adds 0 pp — unlikely to change |
| Non-scan FF selection (cone-aware) | Timing-slack selection; cone-aligned selection may reduce B2−Exp gap |
| UD faults (QN, l=−4) | Structurally untestable in B1 and B2; not reducible by frame depth |
| b03 full-scan AU blocker | PID stale from Jun 9; separate issue (`b03_dffr.v`, forced FAULT_UNTESTABLE in atpg.cpp) |

---

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
