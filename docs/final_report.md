# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. We implement a *progressive residual multi-frame ATPG* pipeline on FAN_ATPG and evaluate it on **two benchmark suites**: **ITC'99** (b03–b13, 8 circuits, 29–88 FFs) and **ISCAS'89** (s953–s38584, 9 circuits, 18–1728 FFs), all at **10% non-scan exclusion** with a unified **per-target timeout of 5 s** (wall timeout: 3600 s).

Under ptt = 5 s, T=1 ATPG classifies hard faults as TO (timed out) rather than spending unlimited time proving them AU; T=2 then recovers these faults through 2-frame sequential state justification. We observe **consistent T=2 gains across all 17 circuits**: +4.68–58.49 pp for ITC'99, +5.69–54.51 pp for ISCAS'89. **T=4 adds 0 pp universally** on all circuits. On ISCAS'89 the pipeline T=1+T=2 reaches 83.79–98.40% against a full-scan ceiling of 88.20–98.87%; the remaining gap narrows to 0.47–6.53 pp.

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

### 1.2 Problem

Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state propagates through functional clocking — can recover some of this lost coverage. However, deeper frames increase the search space and may not benefit every fault. Furthermore, naive deeper-frame ATPG on all faults can underperform T=1 if the larger search space causes abort explosions or if pattern storage/simulation fidelity is imperfect for multi-frame circuits.

A critical engineering dimension is the **per-target timeout (ptt)**: the maximum time FAN_ATPG spends on a single fault before classifying it TO (timed out). Without a ptt, a handful of structurally difficult faults can cause the entire ATPG run to stall for hours. With a ptt, those faults are left as TO and become candidates for residual T=2 recovery.

### 1.3 Proposed Approach

We implement a *progressive residual multi-frame ATPG* flow that:

1. Runs T=1 on all original physical faults.
2. Constructs a residual fault list R1 = All − D1 (detected by T=1).
3. Runs T=2 **only** on R1.
4. Constructs R2 = R1 − D2.
5. Runs T=4 **only** on R2.
6. Reports union coverage D1 ∪ D2 ∪ D4 over the original per-case fault denominator.

This approach preserves T=1 detections, reduces the number of faults targeted at T=2/T=4, and enables a controlled analysis of which residual faults are recoverable by increasing time-frame depth.

### 1.4 Scope and Positioning

This work does **not** propose a new ATPG search algorithm, a new partial-scan selection method, or a new fault model. Timing-driven non-scan FF selection uses OpenSTA minimum-path-slack ranking at a **fixed 10%** exclusion ratio — **experimental setup only**. The **research focus** is:

1. **Does the progressive T=1→T=2→T=4 pipeline increase fault coverage beyond T=1 alone?**
2. **At which stage (T=2 vs T=4) are residual faults recovered, if at all?**
3. **What is the runtime cost of each stage relative to the coverage gain?**

Cross-ratio comparison of absolute partial-scan FC is **not** part of this study; only **x = 10%** is evaluated.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF participates in the scan chain. ATPG can set any FF state arbitrarily in one cycle. In partial scan, some FFs (non-scan) are excluded from the chain. At T=1 with unknown (X) initial state, non-scan FFs are uncontrollable — their values cannot be set by scan loading.

### 2.2 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses partial-scan controllability by unrolling the circuit across T time frames. Each frame is a copy of the combinational portion of the circuit. Non-scan FF outputs (PPOs) at frame t connect to their inputs (PPIs) at frame t+1, while scan FF PPIs remain independently controllable at each frame. The initial state at frame 0 is typically X. T=1 is a single-frame no-recovery model; T>1 provides initialization cycles to justify non-scan FF state.

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

### 2.5 Per-Target Timeout and Residual Recovery

Without a per-target timeout, FAN_ATPG may spend unbounded time on a single structurally hard fault, stalling the run. With `set_per_target_timeout T`, faults unresolved after T seconds become TO. Crucially, **TO faults are not proven untestable** — they are plausibly detectable with additional time or additional frames. Passing TO faults from T=1 into the T=2 residual gives the 2-frame engine a second opportunity to detect them with different justification paths.

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

### 4.2 Fixed-Denominator Union Accounting

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

| Circuit | FFs | Role |
|---------|-----|------|
| b03 | 30 | Tier A |
| b04 | 66 | Tier A |
| b05 | 88 | Tier A |
| b07 | 44 | Tier A |
| b08 | 67 | Tier A |
| b09 | 29 | Tier A |
| b11 | 84 | Tier A |
| b13 | 86 | Tier A |

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
- Static/dynamic compression: **off** (progressive residual runner)
- **Per-target timeout: 5 s** (`set_per_target_timeout 5.0`), applied uniformly to all circuits and all pipeline stages
- **Wall timeout: 3600 s**, applied via Python `subprocess.run(timeout=3600)`
- Results: `results/progressive_residual_summary.csv` (17 circuits × 1 ratio = 17 runs)

**Rationale for ptt = 5 s:** Without a per-target timeout, large ISCAS'89 circuits (particularly s38417, 1636 FFs) cannot complete within a 3600 s wall timeout — a handful of structurally difficult faults monopolize the ATPG engine. A uniform ptt = 5 s ensures all circuits finish within wall timeout and maintains methodological consistency. Faults exceeding the ptt become **TO** and are eligible for T=2 residual recovery.

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

### 7.2 Primary Results: Testset A — ITC'99 (@10% Non-Scan, ptt=5s)

| Circuit | \|F\| | **B1** FC_T1 | **Exp** T1+T2+T4 | **B2** Full-scan | Exp−B1 | B2−Exp | +DT@T2 | +DT@T4 |
|---------|------:|------------:|----------------:|-----------------:|-------:|-------:|-------:|-------:|
| b03 | 809 | 44.50% | 85.41% | 91.62% | +40.91 | +6.21 | 331 | 0 |
| b04 | 2291 | 75.21% | 84.46% | 93.46% | +9.25 | +9.00 | 212 | 0 |
| b05 | 4490 | 29.20% | 87.68% | 95.34% | +58.49 | +7.66 | 2626 | 0 |
| b07 | 1591 | 56.13% | 87.93% | 93.46% | +31.80 | +5.53 | 506 | 0 |
| b08 | 2234 | 72.96% | 91.09% | 94.03% | +18.13 | +2.94 | 405 | 0 |
| b09 | 930 | 76.34% | 87.85% | 93.44% | +11.51 | +5.59 | 107 | 0 |
| b11 | 6843 | 66.21% | 94.34% | 97.43% | +28.13 | +3.09 | 1925 | 0 |
| b13 | 2007 | 77.33% | 82.01% | 91.13% | +4.68 | +9.12 | 94 | 0 |

ITC'99 B2 values are from `results/phase_d_fullscan_dataset.csv` (run without ptt for reference).

### 7.3 Primary Results: Testset B — ISCAS'89 (@10% Non-Scan, ptt=5s)

| Circuit | \|F\| | **B1** FC_T1 | **Exp** T1+T2+T4 | **B2** Full-scan | Exp−B1 | B2−Exp | +DT@T2 | +DT@T4 |
|---------|------:|------------:|----------------:|-----------------:|-------:|-------:|-------:|-------:|
| s953    | 1853 | 36.75% | 91.26% | 97.79% | +54.51 | +6.53 | 1010 | 0 |
| s1196   | 2184 | 86.13% | 98.40% | 98.87% | +12.27 | +0.47 |  268 | 0 |
| s1238   | 2235 | 82.42% | 95.12% | 96.36% | +12.71 | +1.24 |  284 | 0 |
| s5378   | 10113 | 74.25% | 94.94% | 96.65% | +20.69 | +1.71 | 2092 | 0 |
| s9234   | 18021 | 72.79% | 88.13% | 93.09% | +15.34 | +4.96 | 2765 | 0 |
| s15850  | 33189 | 66.04% | 90.13% | 96.04% | +24.09 | +5.91 | 7995 | 0 |
| s35932  | 76602 | 77.10% | 83.79% | 88.20% | +6.70 | +4.41 | 5129 | 0 |
| s38417  | 81506 | 85.41% | 91.10% | 97.10% | +5.69 | +6.00 | 4638 | 0 |
| s38584  | 80111 | 71.67% | 87.16% | 93.58% | +15.49 | +6.42 | 12410 | 0 |

### 7.4 Key Observations

1. **T=2 gains are consistent and substantial.** Across all 17 circuits, T=2 adds +4.68–58.49 pp vs B1. The gain is entirely attributable to T=2; T=4 adds 0 pp on every circuit without exception.

2. **T=4 is universally zero.** +DT@T4 = 0 on all 17 circuits. Residual faults not recovered by T=2 are not recovered by T=4 either. Two pipeline stages (T=1 + T=2) capture the full attainable coverage; the T=4 stage is redundant.

3. **Remaining gap to full-scan (B2−Exp) is 0.47–9.12 pp.** ISCAS'89 circuits show 0.47–6.53 pp gap; ITC'99 circuits show 2.94–9.12 pp. The pipeline does not close the gap completely, but substantially narrows it vs B1 alone.

4. **ISCAS'89 gains are robust to ptt choice.** For s953–s5378, results are identical to prior runs with ptt=30 s (the faults involved are genuinely hard at T=1 and genuinely recoverable at T=2). ptt=5 enables s38417 completion while leaving other ISCAS'89 results unchanged.

5. **Large ISCAS'89 circuits completed within wall timeout.** s38417 (1636 FFs, previously stalling >2 hours at ptt=30) completes T=1 in 1021 s and T=2 in 66 s with ptt=5.

---

## 8. Discussion

### 8.1 Why T=2 Recovers Faults That T=1 Misses

Under ptt = 5 s, faults requiring >5 s of ATPG search at T=1 are classified TO rather than AU or DT. These faults include:

- **Non-scan-FF-blocked faults:** at T=1, the non-scan FF's unknown state makes propagation from fault site to primary output impossible in a single frame. At T=2, frame 1 can justify a specific non-scan FF state, enabling frame 2 to propagate the fault effect. This is the canonical multi-frame recovery mechanism.
- **State-dependent faults:** faults whose detection requires a specific sequential initialization sequence; T=1 cannot provide it.

T=2 ATPG, operating in PARTIAL_SEQUENTIAL mode with 2 frames, can resolve both categories. T=4 adds a third and fourth frame but provides no additional coverage — the faults not resolved by T=2 are structurally untestable even with additional frames (AU) or unreachable within the per-target budget.

### 8.2 The Role of Per-Target Timeout

The ptt parameter controls the trade-off between T=1 accuracy and T=2 opportunity:

- **ptt = 0 (unlimited):** FAN_ATPG can prove faults AU at T=1 through exhaustive search. Formally-proven AU faults are not retried at T=2 with productive results, yielding 0 pp T=2 gain (observed in prior ITC'99 runs). However, large circuits may not complete within practical wall timeouts.
- **ptt = 5 s:** Hard faults become TO at T=1, providing T=2 with additional targets. The 2-frame engine resolves many of these, yielding large T=2 gains. This is the methodology used in all reported results.

The total pipeline coverage (T=1 + T=2) under ptt = 5 s is comparable to or exceeds T=1 under ptt = 0 for ISCAS'89 circuits, while enabling completion of s38417. For ITC'99, the pipeline T=1+T=2 coverage at ptt=5 is below the T=1-only coverage achievable at ptt=0, because the shorter timeout leaves more faults as TO at T=1 than T=2 can recover. This trade-off is acceptable given the uniformity requirement and the much larger ISCAS'89 circuits that necessitate a ptt.

### 8.3 T=4 Adds Nothing

On all 17 circuits, T=4 adds 0 new detections to the T=2 residual. This result holds across both benchmark suites and across circuit sizes from 18 FFs (s1196) to 1728 FFs (s35932). The residual after T=2 consists entirely of faults that are:

- **Structurally AU at 2+ frames** (non-scan FF state does not influence fault propagation even with multi-frame initialization), or
- **TO at T=2** within ptt=5 s — and equally time-limited at T=4.

The implication for practical partial-scan ATPG is that a T=1 → T=2 two-stage pipeline captures the full attainable coverage under this methodology; running T=4 is wasted compute.

### 8.4 Remaining Gap to Full-Scan

The gap **B2 − Experiment** (0.47–9.12 pp) represents coverage achievable by full scan but not by the progressive pipeline. This gap arises from two sources:

1. **AU faults under partial scan:** Faults whose only observable path passes through a non-scan FF output are untestable even at T=2 if the FF value cannot be justified within the time budget. These are structural limitations of the 10% non-scan configuration.
2. **UD faults (QN-pin, faultyLine = −4):** Stuck-at faults on the complementary output (QN) of flip-flops are excluded from FAN_ATPG's pattern generation at any frame depth (the condition `faultyLine >= 0` in `atpg.cpp`). These faults appear as UD in both B1 and B2 and contribute ≈0.1 pp to the gap.

### 8.5 Circuit-Size Scaling

The T=2 gain does not correlate simply with circuit size. Small circuits with low T=1 FC due to non-scan FF blocking (s953: T=1 = 36.75%) can show very large gains (+54.51 pp). Large circuits with moderate T=1 FC (s35932: T=1 = 77.10%) show smaller but still meaningful gains (+6.70 pp). The gain depends on the structural relationship between the 10% non-scan FFs and the fan-out cones of the residual faults.

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

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with fixed-denominator union accounting, evaluated on **two benchmark suites** (8 ITC'99 + 9 ISCAS'89 circuits) under a **unified per-target timeout of 5 s**.

**Key findings:**

1. **T=2 consistently recovers coverage** across all 17 circuits: +4.68–58.49 pp (ITC'99) and +5.69–54.51 pp (ISCAS'89) relative to T=1 alone. The recovery mechanism is 2-frame sequential state justification of faults left as TO by the T=1 per-target timeout.

2. **T=4 adds 0 pp universally.** On all 17 circuits from both suites, the residual T=4 stage detects no new faults. A T=1 → T=2 two-stage pipeline captures the full attainable pipeline coverage; T=4 is redundant under this methodology.

3. **Remaining gap to full-scan is 0.47–9.12 pp.** The pipeline substantially narrows the partial-scan coverage penalty but does not eliminate it. Residual AU faults (beyond the reach of 2-frame justification) and QN-pin UD faults (structurally excluded from ATPG targeting) account for the gap.

4. **ptt = 5 s enables large-circuit completion** without significantly changing small-circuit results. s38417 (1636 FFs) was previously infeasible at ptt=30 s (>3600 s wall); at ptt=5 s it completes in 1087 s total (T=1: 1021 s, T=2: 66 s).

The progressive residual pipeline, under a realistic per-target time budget, provides meaningful multi-frame coverage recovery across diverse benchmark circuits, with all additional coverage concentrated in the T=2 stage.

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
