# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. Multi-frame sequential ATPG can potentially recover this lost coverage, but deeper frames increase search complexity and may not help every fault. We implement a *progressive residual multi-frame ATPG* flow on FAN_ATPG: run T=1 on all faults, construct a residual fault list excluding detected faults, run T=2 only on the residual set, and repeat for T=4, reporting union coverage over the original per-case fault denominator. On s27 (3 FFs, 67% non-scan) the flow recovers +43.9pp (37.9% → 81.8%), demonstrating that the implementation correctly handles sequentially controllable residual faults. On ITC'99 circuits b07 and b13, recovery is small (+0.9–1.4pp at 20% and 50% non-scan ratios), suggesting that residual faults are dominated by factors other than shallow sequential reachability. We conclude that deeper sequential ATPG should be applied selectively based on residual fault profile, and that the primary contribution is a reproducible residual recoverability analysis flow rather than a claim of universal improvement.

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

This work does **not** propose a new ATPG search algorithm, a new partial-scan selection method, or a new fault model. The partial-scan circuit is a constrained setting produced by a timing-prioritized non-scan FF selection (top x% by minimum-path-slack). The research focus is on evaluating whether deeper sequential ATPG with progressive residual targeting can recover coverage under these constraints, and on building a reproducible analysis pipeline for this evaluation.

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

1. How much additional coverage can T=2 or T=4 provide beyond T=1?
2. Does progressive residual targeting (T=1→T=2→T=4) differ from direct T=4 on residuals (T=1→T=4)?
3. Is naive T=4-all — running T=4 on the entire fault set — comparable to the progressive flow?

**Important:** For each (circuit, ratio) case, all comparisons use the same T=1 collapsed fault set F as denominator. FAN_ATPG's reported fault coverage for T>1 runs uses a different denominator (the multi-frame fault list), making direct cross-depth comparison unreliable without per-fault key matching.

**Full-scan baseline metric (2026-06-09):** We report **FC_scan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice (Cummings, SNUG 2002), async reset/control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator. Raw fault coverage (FC_raw), which treats reset as a free PI, is reported in the appendix only. Implementation: FAN applies scan protocol automatically after `add_fault --all` (overridable via `set_scan_protocol off`); see `docs/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md`.

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

**Baselines for comparison:**

- **Naive T=4-all:** ATPG(T=4, target=F). Run T=4 on all original faults.
- **Union(T=1, T=4-all):** D1 ∪ D4_all. Tests whether multi-frame detection adds beyond T=1.
- **T=1→T=4 residual:** ATPG(T=4, target=R1). Skips T=2 to test whether T=2 is necessary.

### 4.1 Why Residual Targeting

Progressive residual targeting provides three benefits:

1. **Preserves T=1 detections.** Deeper frames never re-target already-detected faults.
2. **Reduces target count.** T=2 targets only R1 (≤|F|); T=4 targets only R2 (≤|R1|), reducing ATPG effort.
3. **Enables recoverability analysis.** By isolating which faults are recovered at each depth, we can characterize the residual fault profile.

### 4.2 Fixed-Denominator Union Accounting

FAN_ATPG's `report_statistics` for T>1 runs reports fault coverage against the multi-frame fault list, whose denominator may differ from the T=1 collapsed fault list. To ensure fair comparison, we:

1. Extract per-fault D1, D2, D4 sets using `report_fault` with stable (gateID, faultyLine, faultType) keys.
2. Compute union coverage |D1 ∪ D2 ∪ D4| / |F| using the T=1 fault count |F|.

This approach guarantees that coverage numbers are comparable across all stages within the same (circuit, ratio) case. However, denominators differ across exclusion ratios and circuits, so cross-ratio comparisons should be interpreted carefully.

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
| b07 | ITC'99 | 45 | Stress case |
| b13 | ITC'99 | 65 | Stress case |

s27 has only 3 FFs and serves as a sanity check. b07 and b13 are the primary stress cases. ITC'99 circuits are synthesized to NanGate45 gate-level Verilog using Yosys.

### 6.2 Non-Scan FF Selection

OpenSTA ranks FFs by minimum-path-slack. The top x% most timing-critical FFs are designated non-scan. The resulting non-scan mask lists FF cell names.

| Circuit | Ratio | Non-scan FFs | Scan FFs |
|---------|-------|-------------|----------|
| s27 | 67% | 2 | 1 |
| b07 | 20% | 9 | 36 |
| b07 | 50% | 22 | 23 |
| b13 | 20% | 13 | 52 |
| b13 | 50% | 32 | 33 |

### 6.3 ATPG Configuration

- Fault model: stuck-at (SAF)
- Time-frame depths: T=1, T=2, T=4
- Static/dynamic compression: off
- Backtrack limit: 500 (default, compile-time constant)
- Timeout: 180s per run

### 6.4 Metrics

| Metric | Definition |
|--------|-----------|
| FC_T1 | \|D1\| / \|F\| |
| FC_T1_T4_union | \|D1 ∪ D4_all\| / \|F\| |
| FC_T1→T4 | \|D1 ∪ D4_residual\| / \|F\| |
| FC_T1→T2→T4 | \|D1 ∪ D2_residual ∪ D4_residual\| / \|F\| |
| T=4 all FC | FAN-reported FC for multi-frame ATPG (different denominator; informational) |
| Gain | FC_proposed − FC_T1 (percentage points) |

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

### 7.2 Stress Cases: b07 and b13

| Case | T=1 FC | T2-all FC† | T4-all FC† | union(T1,T4) | T1→T4 res | T1→T2→T4 | Gain |
|------|-------:|----------:|----------:|------------:|---------:|----------:|-----:|
| b07 x=20% | 28.9% | 25.2% | 26.1% | 30.3% | 30.2% | 30.3% | +1.4pp |
| b07 x=50% | 19.5% | 17.3% | 16.1% | 20.2% | 20.3% | 20.4% | +0.9pp |
| b13 x=20% | 42.2% | 35.4% | 37.6% | 43.3% | 43.6% | 43.6% | +1.4pp |
| b13 x=50% | 30.0% | 24.7% | 25.5% | 30.6% | 30.9% | 30.9% | +0.9pp |

*† T2-all and T4-all FC computed using per-fault key matching against the T=1 fault set as denominator. FAN_ATPG's native report for multi-frame circuits uses a different denominator and should not be directly compared.*

![Coverage comparison](figures/coverage_bar_chart.png)

*Figure 1: Coverage across methods for each case. "Progressive T1→T2→T4" is the proposed flow.*

![Recovered faults](figures/recovered_faults_chart.png)

*Figure 2: Number of newly detected faults from residual T=2 and residual T=4.*

### 7.3 Key Observations

1. **Gains are small on ITC'99 circuits.** On b07 and b13, residual multi-frame ATPG adds only +0.9 to +1.4 percentage points regardless of exclusion ratio (20% or 50%). T=2 contributes minimally (4–10 faults); T=4 adds slightly more (9–20 faults) but the absolute gain remains marginal.

2. **Higher exclusion does not increase recovery.** For b07, gain decreases from +1.4pp (20% exclusion) to +0.9pp (50% exclusion). For b13, the pattern is the same. More non-scan FFs create a larger residual set, but the additional residual faults are not recovered by T=4.

3. **Naive T=4-all coverage is not directly comparable with T=1 in FAN_ATPG.** FAN_ATPG's native multi-frame `report_statistics` uses a fault list denominator that differs from the T=1 collapsed fault count, so directly comparing FAN-reported T=4-all FC against T=1 FC is unreliable. We compute externally key-matched T2-all and T4-all FC values (reported in Table Section 7.2, marked with †) by mapping per-fault DT sets back to the T=1 fault denominator. These key-matched values still underperform or only slightly improve over T=1, indicating that naive all-fault deeper-frame ATPG does not provide a robust coverage improvement in our backend, independent of denominator mismatch.

4. **Progressive flow closely matches T=1→T=4.** For all cases, skipping T=2 (T1→T4 residual) produces nearly identical union coverage to the full T1→T2→T4 flow. T=2 is not strictly necessary as a separate recovery stage at current depths.

### 7.4 Denominator and Coverage Accounting

FAN_ATPG's `report_statistics` for multi-frame circuits reports fault counts against a fault list that may differ from the T=1 collapsed list. We observed that the T=4-all reported fault total sometimes exceeds the T=1 total (more gates → more faults), making direct FC comparison unreliable across depths.

Our union coverage is computed externally using stable fault keys (gateID, faultyLine, faultType) extracted from `report_fault` output, always normalized to the T=1 collapsed fault count as denominator. This ensures:

- Within each (circuit, ratio) case, all stage-wise FC values are comparable.
- Cross-ratio and cross-circuit comparisons should be interpreted with care, as denominators and fault profiles differ.

---

## 8. Discussion

### 8.1 When Deeper Frames Help

On s27 with 67% non-scan FFs, the residual fault set (41 of 66 faults) primarily consists of faults that are undetectable at T=1 due to lack of controllability over the two non-scan FFs. With multi-frame justification, the ATPG engine can set these FF values over multiple cycles, recovering the faults. This is the scenario where residual multi-frame ATPG is effective.

### 8.2 When Deeper Frames Do Not Help

On b07 and b13, the residual fault sets are large (1082–1518 faults) but most are classified as AU (atpg untestable) by T=1. These residual faults are not recovered by shallow multi-frame expansion up to T=4 under our backend. Their T=1 AU-dominated profile suggests that the limiting factor may be structural, synthesis-induced, or backend-limited rather than simply insufficient sequential depth. Without full-scan residual classification or deeper T=8/T=16 experiments, we cannot definitively separate structural untestability from backend limitations or deeper sequential controllability requirements.

### 8.3 T=2 Stage Value

The T=2 stage contributes minimally (4–20 new faults across all cases). Skipping T=2 (T=1→T=4 residual) achieves nearly identical union coverage. For practical deployment, T=1→T=4 may be sufficient; for diagnostic analysis, the T=1→T=2→T=4 flow provides finer-grained recoverability characterization.

### 8.4 Priority Scoring (Negative Result)

We implemented a static fault priority scoring function based on observability distance, controllability distance, local cone size, and fanout count. This scoring showed **no lift over random ordering** for predicting which residual faults would be recovered by deeper frames. We abandoned this direction.

### 8.5 Runtime

On these small benchmarks, ATPG runtime ranges from 0.01 to 0.64 seconds per stage. Runtime is not the bottleneck at this scale; target-count reduction and recoverability characterization are the primary analytical contributions. Larger circuits are needed to evaluate runtime scalability of deeper-frame ATPG.

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

1. **Small benchmark set.** Only three circuits (s27, b07, b13) at 2–3 ratios each. Results may not generalize.
2. **s27 is toy-scale.** With 3 FFs, the +43.9pp gain is a sanity check, not scalability evidence.
3. **b07/b13 gains are small.** The <1.5pp gain on larger circuits suggests that residual faults are predominantly not recoverable at T=4 under our setup.
4. **Maximum depth T=4.** The project spec originally proposed T=8. Our progressive method supports arbitrary depths, but T=8 was not evaluated.
5. **Naive T=4-all baseline affected by denominator mismatch.** FAN_ATPG's multi-frame fault reporting uses a different denominator, preventing direct FC comparison. Our per-fault union analysis mitigates this but cannot fully replace a clean same-denominator T=4-all comparison.
6. **Denominator comparable only within same (circuit, ratio) case.** Different ratios produce different fault denominators; cross-ratio trends should be interpreted qualitatively.
7. **Timing-prioritized selection is approximate.** Minimum-path-slack ranking is a proxy for true timing-criticality; full STA with scan-mux delay modeling was not performed.
8. **Residual fault classification is incomplete.** We did not run full-scan ATPG on b07/b13 to distinguish structural AU from sequential-controllability AU.
9. **Runtime conclusions are preliminary.** Benchmarks are small; larger circuits are needed for meaningful runtime analysis.
10. **FAN_ATPG is a single backend.** Results may differ with other ATPG engines.
11. **Per-target timeout not needed at current scale.** We additionally instrumented an optional per-target-fault wall-clock timeout (`set_per_target_timeout <sec>`, default 0 = disabled) to check whether hard residual faults monopolize the T=4 invocation budget. On the current s27, b07, and b13 benchmark set, no T=4 run hit the global 180-second timeout, and practical per-target timeout settings did not produce TO faults. Therefore, the limited b07/b13 recovery is not explained by timeout starvation; it is consistent with the AU-dominated residual profile observed under shallow T=4 expansion. The per-target timeout remains useful as instrumentation and as a safeguard for larger benchmarks. See `docs/t4_timeout_analysis.md` for validation details.

---

## 11. Conclusion

We implemented and evaluated a progressive residual multi-frame ATPG flow for timing-constrained partial-scan circuits. Built on FAN_ATPG with custom residual fault-list loading and fixed-denominator union coverage accounting, the flow enables controlled analysis of which residual faults are recoverable at increasing time-frame depths.

On the sanity case s27 (3 FFs, 67% non-scan), the flow recovers +43.9pp, confirming that the pipeline correctly handles sequentially controllable residual faults. On ITC'99 circuits b07 and b13, recovery is marginal (+0.9–1.4pp at 20% or 50% exclusion), suggesting that residual faults in these cases are predominantly not recoverable by shallow multi-frame expansion up to T=4.

The primary contribution is a reproducible residual recoverability analysis pipeline, not a claim of universal improvement. Deeper sequential ATPG should be applied adaptively: when the residual fault profile indicates recoverability, progressive multi-frame targeting provides a controlled framework; when residual faults are dominated by factors beyond shallow sequential reachability, deeper-frame ATPG adds minimal value. Future work includes T=8 evaluation, full-scan residual classification, budget-aware scheduling, and testing on a larger benchmark set.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/progressive_residual_summary.csv` | Full 5-case progressive residual experiment data |
| `results/itc99_partial_scan.csv` | ITC'99 backend status and full-scan baselines |
| `results/residual_faults/` | Per-stage residual fault list files |

### B. Engineering Fixes

| Issue | Resolution |
|-------|-----------|
| Floating nets rejected by FAN_ATPG | ERROR→WARN |
| `_const0_` as free module port | LOGIC0/LOGIC1 tie cells |
| Level-indexed array OOB crashes | `maxGateLevel+1` sizing |
| Stale masks after re-synthesis | `gen_nonscan_masks.sh` |
| `report_fault` prints nothing | Fix inverted logic |
| DFF faults lack instance names | Print cell name |

### C. Known Blockers

| Item | Status / mitigation |
|------|---------------------|
| ITC netlist quality (b05/b08–b15) | **In progress** — `build_itc99_netlists.sh` + `validate_netlist.py` (undriven=0, no OAI/AOI) |
| b05 missing from regen list | Add to pipeline; old DFFR-only netlist with floating outputs |
| ATPG timeouts | Unified: `ATPG_WALL_TIMEOUT=3600s`, `ATPG_PER_TARGET_TIMEOUT=120s` (`scripts/atpg_timeouts.sh`) |
| Large ITC (b12/b14/b15) ATPG | **Deferred** from sweeps — MUX backtrace crash / hour-scale runtime; netlist validate PASS |
| Benchmark scope | **Tier A (8 ITC)** active; b17+ out of scope — see `2026-06-10-saf-atpg-speed-improvement.md` |
| SAF ATPG speed plan | Phases S0–S4: scope, config, MUX backtrace, heuristics — `docs/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md` |
| T=8 partial-scan recovery | Not yet evaluated on rebuilt ITC netlists |
| BACKTRACK_LIMIT | Raised to **5000** (Phase D5) |

**Resolved (Phase D):** b03 FC_scan ~93%; b07 ~94% on current netlists. Compound OAI/AOI atomic modeling (D3.2/D3.3) is transitional — synthesis will expand OAI/AOI; FAN keeps MUX2 only.

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
