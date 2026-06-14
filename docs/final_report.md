# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. We implement a *progressive residual multi-frame ATPG* pipeline on FAN_ATPG and evaluate it against **two baselines**: **(B1)** partial-scan T=1 coverage (`FC_T1`) and **(B2)** full-scan coverage (`FC_scan_coll`).

On the sanity case s27 (3 FFs, 67% non-scan), the pipeline recovers +43.9pp vs B1 (37.9% → 81.8%). On Tier A ITC'99 @ **10%** (June 2026, 7/8 complete): **B1** 87.6–93.5%, **Experiment** equals B1 (0 pp gain), **B2** 91.1–97.4%; remaining gap **B2−Experiment** is 0–5.9 pp unchanged by the pipeline. b11 partial-scan B1 did not finish (7200 s timeout).

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

### 1.2 Problem

Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state propagates through functional clocking — can recover some of this lost coverage. However, deeper frames increase the search space and may not benefit every fault. Furthermore, naive deeper-frame ATPG on all faults can underperform T=1 if the larger search space causes abort explosions or if pattern storage/simulation fidelity is imperfect for multi-frame circuits.

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

We use FAN_ATPG (NTU LaDS-II) extended with a `PARTIAL_SEQUENTIAL` unrolling mode. Non-scan FFs propagate state across frames via BUF connections; scan FF PPIs are free at each frame. The `set_nonscan_ff` command designates non-scan FFs.

### 2.4 Fault Classes

After ATPG, each stuck-at fault is classified as:

- **DT** (detected): a test pattern was found.
- **AU** (atpg untestable): the ATPG engine determined no pattern exists.
- **AB** (abort): the engine reached its backtrack limit before finding a pattern.
- **UD** (undetected): the fault was not targeted.

Fault coverage FC = DT / (DT + AU + AB + UD).

### 2.5 Fault Dropping

FAN_ATPG performs *within-run* fault dropping: after generating a pattern, fault simulation identifies other faults also detected by that pattern and marks them DT. Detected faults are skipped in subsequent pattern generation. However, each `add_fault --all` call rebuilds the entire fault list from the circuit. There is no built-in mechanism to import detections from a T=1 run into a T=2 run. This motivates our custom residual fault-list loading.

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

**Full-scan baseline metric:** We report **FC_scan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice, async reset/control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator. FAN applies scan protocol automatically after `add_fault --all`.

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

**Secondary baseline:**

- **T=1→T=4 residual:** ATPG(T=4, target=R1). Skips T=2 to test whether T=2 is necessary. Used in s27 sanity case only.

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
| `scripts/analyze_residual.py` | Per-fault overlap analysis and priority evaluation |
| `scripts/rank_residual_faults.py` | Netlist-based fault priority scoring (negative result, preserved) |
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

These are infrastructure fixes; they are not claimed as research contributions.

---

## 6. Experimental Setup

### 6.1 Benchmarks

| Circuit | Source | FFs | Role |
|---------|--------|-----|------|
| s27 | ISCAS'89 | 3 | Sanity / pipeline verification |
| b03 | ITC'99 | 30 | Tier A |
| b04 | ITC'99 | 66 | Tier A |
| b05 | ITC'99 | 88 | Tier A |
| b07 | ITC'99 | 44 | Tier A |
| b08 | ITC'99 | 67 | Tier A |
| b09 | ITC'99 | 29 | Tier A |
| b11 | ITC'99 | 84 | Tier A (T=1 timeout) |
| b13 | ITC'99 | 86 | Tier A |

s27 has only 3 FFs and serves as a sanity check. The 8 ITC'99 Tier A circuits are synthesized to NanGate45 gate-level Verilog using Yosys; FF counts are from the synthesized netlists.

### 6.2 Partial-Scan Setup (Not the Primary Variable)

OpenSTA ranks FFs by minimum-path-slack on our synthesized NanGate45 gate-level netlists. The top **10%** most timing-critical FFs are designated non-scan. Masks: `masks/<circuit>_x10.mask` (`scripts/gen_nonscan_masks.sh`, June 2026).

| Circuit | FF total (approx.) | Non-scan @10% | Mask |
|---------|-------------------:|--------------:|------|
| b03 | 30 | 4 | `masks/b03_x10.mask` |
| b04 | 66 | 7 | `masks/b04_x10.mask` |
| b05 | 88 | 9 | `masks/b05_x10.mask` |
| b07 | 44 | 5 | `masks/b07_x10.mask` |
| b08 | 67 | 7 | `masks/b08_x10.mask` |
| b09 | 29 | 3 | `masks/b09_x10.mask` |
| b11 | 84 | 9 | `masks/b11_x10.mask` |
| b13 | 86 | 9 | `masks/b13_x10.mask` |

Only 10% is evaluated.

### 6.3 ATPG Configuration

- Fault model: stuck-at (SAF)
- Pipeline depths: T=1 (all faults), T=2 (residual R1), T=4 (residual R2)
- Static/dynamic compression: off (progressive residual runner)
- Two-phase ATPG + state justification: **on by default** in FAN_ATPG (engine optimizations; not the measured independent variable)
- Wall timeout: 7200 s (b11); per-target timeout: 0 s
- Results file: `results/progressive_residual_summary.csv` (**8 runs** = 8 circuits @ 10%)

### 6.4 Metrics and Baselines

**Two baselines** anchor all Tier A reporting:

| Baseline | Setup | Metric | Source |
|----------|-------|--------|--------|
| **B1 — Partial-scan T=1** | 10% non-scan, single frame | **FC_T1** | `progressive_residual_summary.csv` |
| **B2 — Full-scan** | All FFs scan, T=1 | **FC_scan_coll** | `phase_d_fullscan_dataset.csv` |

Pipeline and comparison metrics (same T=1 fault denominator |F| for partial-scan runs):

| Metric | Definition | Compares |
|--------|------------|----------|
| **FC_T1** | \|D1\| / \|F\| | **B1** |
| **FC_T1_T2_T4** | \|D1 ∪ D2 ∪ D4\| / \|F\| | **Experiment** (T=1→T=2→T=4) |
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 | Experiment vs **B1** |
| **partialscan_gap_pp** | FC_scan_coll − FC_T1 | **B2 − B1** |
| **remaining_gap_pp** | FC_scan_coll − FC_T1_T2_T4 | **B2 − Experiment** |
| gain_T2_pp, gain_T4_pp | Stage attribution | vs **B1** |
| T1_rt / T2_rt / T4_rt | Wall time per stage | Cost |

Full-scan runs use the scan-protocol denominator (reset held inactive; TI faults excluded). Partial-scan and full-scan |F| differ slightly per circuit; FC values are compared as reported percentages, not raw fault counts.

---

## 7. Results

### 7.1 Sanity Case: s27 (3 FFs, 67% non-scan)

s27 is treated as a sanity/toy case to verify that the pipeline correctly implements progressive residual targeting.

| Method | FC | Gain vs T=1 |
|--------|----:|-----------:|
| T=1 | 37.9% | baseline |
| T=1→T=4 residual | 81.8% | +43.9pp |
| T=1→T=2→T=4 | 81.8% | +43.9pp |

The +43.9pp gain demonstrates that the pipeline correctly recovers faults whose detection is limited by sequential controllability of non-scan FFs. T=2 and T=4 recover the same faults in the same order; T=1→T=4 (skipping T=2) achieves identical union coverage.

**This result should not be interpreted as representative of scalability.** s27 has only 3 FFs and its residual fault profile is favorable for sequential recovery.

### 7.2 Primary Result: B1 → Experiment → B2 (@10% Non-Scan)

**B1 & experiment:** `results/progressive_residual_summary.csv`. **B2:** `results/phase_d_fullscan_dataset.csv` (`fc_scan_coll`).

**Experiment** = progressive residual pipeline **T=1 → T=2 → T=4**, union FC `FC_T1_T2_T4` over the T=1 fault denominator.

| Circuit | Excl | \|F\| | **B1** partial T=1 | **Experiment** T1∪T2∪T4 | **B2** full-scan | Exp−B1 (pp) | B2−Exp (pp) | +DT@T2 | +DT@T4 | Status |
|---------|-----:|------:|-------------------:|-------------------------:|-----------------:|------------:|------------:|-------:|-------:|--------|
| b03 | 4 | 841 | 89.54% | 89.54% | 91.62% | 0.00 | +2.08 | 0 | 0 | PASS |
| b04 | 7 | 2347 | 87.60% | 87.60% | 93.46% | 0.00 | +5.86 | 0 | 0 | PASS |
| b05 | 9 | 4562 | 92.81% | 92.81% | 95.34% | 0.00 | +2.53 | 0 | 0 | PASS |
| b07 | 5 | 1631 | 93.50% | 93.50% | 93.46% | 0.00 | −0.04 | 0 | 0 | PASS |
| b08 | 7 | 2290 | 92.75% | 92.75% | 94.03% | 0.00 | +1.28 | 0 | 0 | PASS |
| b09 | 3 | 954 | 87.63% | 87.63% | 93.44% | 0.00 | +5.81 | 0 | 0 | PASS |
| b13 | 9 | 2079 | 87.59% | 87.59% | 91.13% | 0.00 | +3.54 | 0 | 0 | PASS |
| b11 | 9 | — | — | — | 97.43% | — | — | — | — | T=1 TIMEOUT |

**Reading the three coverage columns:**

| Column | Meaning |
|--------|---------|
| **B1** | Partial-scan @10%, single-frame ATPG — lower bound / pipeline baseline |
| **Experiment** | Our T=1→T=2→T=4 progressive residual method |
| **B2** | Full-scan single-frame ATPG — upper reference |

| Derived column | Meaning |
|----------------|---------|
| **Exp−B1** | Pipeline gain (`total_gain_pp`) — did multi-frame staging help? |
| **B2−Exp** | Remaining gap to full-scan (`remaining_gap_pp`) — did the experiment close the partial-scan penalty? |
| **+DT@T2 / +DT@T4** | New detections at each residual stage |

On all 7 completed circuits: **Exp = B1** (0 pp gain); **B2−Exp = B2−B1** (pipeline closes none of the partial-scan gap).

![T-stage union coverage at 10% non-scan](figures/coverage_bar_chart.png)

*Figure 1: B1 (T=1) vs pipeline union FC per circuit (10% non-scan).*

![New detections at T=2 and T=4](figures/recovered_faults_chart.png)

*Figure 2: New DT at each residual stage vs B1 (10% setting).*

### 7.3 Key Observations

1. **Two baselines separate two questions.** B1→pipeline measures sequential recovery; B2→B1 measures partial-scan penalty at T=1. Both must be reported.

2. **Partial-scan loss vs full-scan is 0–5.9 pp** on completed Tier A circuits (b07 ≈ 0 pp). Largest gaps: b04, b09 (~5.8 pp).

3. **Pipeline adds 0 pp vs B1** on all 7 completed circuits. **Remaining gap to B2 is unchanged** — T=2/T=4 detect no additional faults.

4. **b11** full-scan **B2 = 97.43%**, but partial-scan **B1 was not obtained** (T=1 wall timeout at 7200 s).

5. **Mask alignment.** Sweep reads `masks/<circuit>_x10.mask`; CSV `excluded_ff` equals mask line count.

### 7.4 Denominator and Coverage Accounting

FAN_ATPG's `report_statistics` for multi-frame circuits reports fault counts against a fault list that may differ from the T=1 collapsed list. We observed that the T=4-all reported fault total sometimes exceeds the T=1 total (more gates → more faults), making direct FC comparison unreliable across depths.

Our union coverage is computed externally using stable fault keys (gateID, faultyLine, faultType) extracted from `report_fault` output, always normalized to the T=1 collapsed fault count as denominator. This ensures:

- Within each (circuit, ratio) case, all stage-wise FC values are comparable.
- Cross-ratio and cross-circuit comparisons should be interpreted with care, as denominators and fault profiles differ.

---

## 8. Discussion

### 8.1 When the T=1→T=2→T=4 Pipeline Helps

The s27 sanity case (+43.9pp) shows the intended behavior: residual faults undetectable at T=1 because non-scan state is not freely controllable, but detectable after multi-frame sequential justification. **The measured variable is pipeline gain (ΔFC), not absolute partial-scan FC.**

### 8.2 When the Pipeline Does Not Help (Current Tier A @10%)

On 7/8 completed circuits, **total_gain_pp = 0** vs **B1**. The **partialscan_gap_pp** to **B2** (0–5.9 pp) is **fully unchanged** after T=2/T=4. The 0-gain result has two independent root causes detailed in §8.6: (1) UD residuals are QN-pin structural observability gaps that FAN_ATPG's engine excludes from targeting at any frame depth; (2) AU residuals are targeted by T=2 but remain untestable because timing-slack-selected non-scan FFs fall outside the AU fault fan-out cones.

**b11:** **B2 = 97.43%** full-scan; partial-scan **B1 not measured** (T=1 timeout @ 7200 s).

### 8.3 Interpreting B1 vs B2

**B2 − B1** is the partial-scan coverage penalty at single-frame depth. It is **not** the pipeline metric. On b04/b09 the penalty is ~5.8 pp; the pipeline recovers **none** of it at T=2/T=4. Closing the gap to full-scan would require improvements beyond the current progressive residual flow (e.g., engine AU reduction, different non-scan selection, or deeper frames — not observed to help here).

### 8.4 T=2 vs T=4

On completed @10% runs, **T=4 adds nothing** where T=2 gain is zero.

### 8.5 Priority Scoring (Negative Result)

Static fault priority scoring (observability/controllability distance, cone size, fanout) showed **no lift over random ordering** for predicting T=2/T=4 recovery. Abandoned.

### 8.6 Root Cause: Residual Fault Profile Decomposition at @10%

Two structurally distinct fault categories compose R1, and each blocks pipeline improvement by a different mechanism.

**Category 1 — UD faults (QN observability gap, faultyLine = −4).**
In all 7 completed circuits, 100% of UD faults carry `faultyLine = −4`, denoting QN-pin stuck-at faults on flip-flops. FAN_ATPG's ATPG main loop excludes these faults from pattern generation via the condition `faultyLine >= 0` (`atpg.cpp:94`); the same filter applies at T=2 and T=4. The faults are correctly loaded from the residual fault file but are never targeted. Crucially, the same faults appear as UD in B2 (full scan):

| Circuit | B1 UD | B2 UD | Difference |
|---------|------:|------:|-----------:|
| b03     |    64 |    62 |          2 |
| b04     |   137 |   134 |          3 |
| b05     |   178 |   176 |          2 |
| b07     |    92 |    90 |          2 |
| b08     |   138 |   136 |          2 |
| b09     |    62 |    60 |          2 |
| b13     |   182 |   180 |          2 |

The ≤3-fault difference is attributable to fault collapsing differences between B1 and B2 denominators. QN observability is a design-level structural property, unchanged by scan configuration. UD faults contribute ≈0.1 pp to the B2−B1 gap; they cannot be recovered by any frame depth.

**Category 2 — AU faults (non-scan FF outside fault fan-out cone).**
The remaining R1 faults are AU with `faultyLine >= 0` — combinational-gate stuck-at faults that FAN_ATPG targets normally at T=2. Partial scan produces substantially more AU faults than full scan:

| Circuit | B1 AU | B2 AU | Extra AU in B1 |
|---------|------:|------:|---------------:|
| b03     |    24 |    21 |              3 |
| b04     |   154 |    40 |            114 |
| b05     |   150 |    65 |             85 |
| b07     |    14 |    33 |            −19 †|
| b08     |    28 |     1 |             27 |
| b09     |    56 |     6 |             50 |
| b13     |    76 |     9 |             67 |

†b07: partial scan produces *fewer* AU than full scan. This anomaly occurs because the excluded FF outputs are in a region where their unknown state relaxes, rather than tightens, testability constraints for certain faults.

The B2−B1 gap is almost entirely explained by this AU count difference. T=2 targets all AU faults in R1 but finds 0 new patterns at @10%. A multi-ratio experiment (x5/x10/x15/x20; archived sweep data) demonstrates that T=1 DT, AU, and FC are **completely flat across all ratios** for 5/6 circuits (b04, b05, b07, b08, b09): adding more non-scan FFs does not change which faults are AU. This confirms that the timing-slack-selected FFs are structurally outside the fan-out cones of the AU faults — their state does not influence AU fault detectability, so T=2 state justification has no effect.

**Effective T=2 target count.** The residual fault file for b04 contains 291 entries (`R1_count`), but the engine targets only the 154 AU faults (`faultyLine >= 0`). The 134 UD faults (`faultyLine = −4`), 2 TI faults, and 1 AB fault are loaded but filtered before pattern generation. The pipeline infrastructure is correct; the 0-gain result is a property of the fault profile, not a loading or accounting error.

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

1. **Benchmark set.** Tier A: 8 ITC'99 circuits @ **10%** non-scan; **7/8** partial-scan runs complete (b11 T=1 timeout).
2. **Two baselines.** Report **B1** (partial T=1) and **B2** (full-scan) for every circuit; pipeline vs **B1**, gap vs **B2**.
3. **s27 is toy-scale.** +43.9pp vs B1 is pipeline verification only.
4. **Shallow depth.** T=8 not evaluated; T=4 adds 0 gain in current @10% sweep.
5. **Mask/netlist alignment.** Regenerate `masks/<circuit>_x10.mask` after netlist changes.
6. **Full-scan ceiling.** Partial-scan T=1 already near full-scan on most Tier A circuits.
7. **AU semantics.** FAN AU is operational (search failure), not formal untestability proof.
8. **Single ATPG backend.** Cross-tool validation not performed.

---

## 11. Conclusion

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with fixed-denominator union accounting. Evaluation uses **two baselines**: partial-scan T=1 (**B1**) and full-scan (**B2**).

At 10% non-scan exclusion, **B1** is 87.6–93.5% on 7/8 Tier A circuits; **B2** is 91.1–97.4%. Partial-scan loss (**B2 − B1**) is 0–5.9 pp. **Pipeline gain vs B1 is 0.00 pp** everywhere completed; the gap to **B2** is unchanged. The pipeline is validated on s27; on current Tier A @10% it does not recover additional coverage beyond **B1**, and does not close the distance to **B2**.

Fault profile analysis (§8.6) identifies two independent causes. First, UD residuals are QN-pin stuck-at faults (`faultyLine = −4`) that the FAN_ATPG engine excludes from pattern generation at any frame depth; these faults are structurally identical in B1 and B2 and contribute ≈0 pp to the B2−B1 gap. Second, AU residuals are targeted by T=2 but remain untestable because timing-slack-selected non-scan FFs lie outside the AU fault fan-out cones; a multi-ratio experiment confirms T=1 coverage is flat regardless of the exclusion ratio for 5/6 circuits. Closing the B2−B1 gap requires non-scan FF selection aligned to AU fault detection cones, not deeper frame expansion.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/progressive_residual_summary.csv` | B1 + pipeline (@10%, 7/8 complete) |
| `results/phase_d_fullscan_dataset.csv` | **B2** full-scan FC_scan_coll |
| `results/residual_faults/` | Per-stage residual fault list files |
| `masks/*_slack.csv`, `masks/*_x10.mask` | OpenSTA slack ranking + non-scan masks (regenerated June 2026) |
| `results/archive/` | Superseded CSVs (legacy T=8 sweep, two-phase A/B, ISCAS timing) |

### B. Engineering Fixes

| Issue | Resolution |
|-------|-----------|
| Floating nets rejected by FAN_ATPG | ERROR→WARN |
| `_const0_` as free module port | LOGIC0/LOGIC1 tie cells |
| Level-indexed array OOB crashes | `maxGateLevel+1` sizing |
| Stale masks after re-synthesis | `gen_nonscan_masks.sh` |
| `report_fault` prints nothing | Fix inverted logic |
| DFF faults lack instance names | Print cell name |

### C. Open Follow-ups

| Item | Status |
|------|--------|
| Full-scan FC headroom (AU/UD) | Ongoing engine/netlist quality work; see `phase_d_fullscan_dataset.csv` |
| Tier B (b12/b14/b15) | Deferred — hour-scale / crash; out of Tier A pipeline sweep |
| T=8 pipeline depth | Not evaluated; T=4 adds 0 pp on current Tier A sweep |
| Archived legacy CSVs | `results/archive/` — do not cite for current report |
| Non-scan FF selection (cone-aware) | Timing-slack selection shown ineffective for 5/6 circuits (flat T=1 FC across x5–x20); AU fault fan-out cone alignment is the required property for pipeline gain |
| UD faults (QN, l=−4) | Structurally untestable in both B1 and B2; not reducible by frame depth; design-level observability issue |

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
