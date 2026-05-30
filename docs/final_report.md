# True Progressive Residual Multi-Frame ATPG for Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing  
**Group 5:** 丁睿濂, 駱彥竹, 黃思維  
**Date:** June 2026

---

## Abstract

Full-scan design simplifies ATPG but some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit with reduced controllability. Sequential ATPG over multiple time frames can recover lost coverage, but deeper frames are expensive and may not benefit every fault. We propose *True Progressive Residual Multi-Frame ATPG*: run T=1 on all faults, drop detected faults, run T=2 only on residual faults, drop those detected, and run T=4 only on the remaining residual set. All coverage is reported over the original physical fault denominator. Built on FAN_ATPG with custom residual fault-list loading (`add_fault -f`), we evaluate the method on three benchmark circuits at multiple exclusion ratios. On s27 with 67% non-scan FFs, the proposed method recovers +43.9pp of coverage (37.9% → 81.8%). On ITC'99 circuits b07 and b13, recovery is marginal (+0.9–1.4pp) regardless of exclusion ratio, because residual faults are dominated by structural untestability rather than sequential controllability loss. We conclude that progressive residual multi-frame ATPG is effective when the residual fault set is limited by sequential constraints, and should be applied adaptively rather than universally.

---

## 1. Introduction

Scan-based testing is the dominant DFT strategy. In full-scan design, all flip-flops are connected into a scan chain, granting ATPG direct controllability and observability over all internal state. However, a subset of FFs may remain non-scan because converting them to scan cells would violate timing constraints — the extra scan multiplexer would push critical-path slack negative.

When FFs cannot be scanned, the circuit becomes a partial-scan design. Single-frame (T=1) ATPG loses coverage because non-scan FFs are not freely controllable: their state is unknown (X) and cannot be set to arbitrary values. Multi-frame sequential ATPG can recover some of this coverage by propagating state through non-scan FFs over multiple clock cycles.

However, deeper-frame ATPG is not a universal solution. Naively running T=4 on all faults can underperform T=1 because:

1. The larger search space may cause ATPG to abort on faults that T=1 already solved.
2. T=4 may miss some T=1 detections if pattern storage or simulation fidelity is imperfect.
3. Many residual faults may be structurally untestable, regardless of time-frame depth.

We propose *True Progressive Residual Multi-Frame ATPG*, which preserves T=1 detections, targets deeper frames only at genuinely residual faults, and reports union coverage over a fixed original physical fault denominator.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF is connected to a scan chain. The ATPG engine can set any FF's state to 0 or 1 in a single cycle. In partial-scan design, a subset of FFs are designated as *non-scan*: their state evolves only through functional clocking, not scan loading. At T=1 with unknown initial state, non-scan FFs are uncontrollable.

### 2.2 Sequential ATPG and Time Frames

Sequential ATPG unrolls the circuit across multiple time frames. In the `PARTIAL_SEQUENTIAL` mode of FAN_ATPG:

- **T=1:** All FFs are treated per their scan/non-scan designation. Non-scan FFs at frame 0 are TIEX (unknown, uncontrollable).
- **T>1:** Non-scan FF state propagates across frames: PPO[t] → BUF → PPI[t+1]. The first T−1 frames provide initialization, faults are observed in the final frame.

### 2.3 Fault Classes

After ATPG, each fault is assigned a status:

- **DT** (detected): a pattern was found that detects the fault.
- **AU** (ATPG untestable): no pattern can exist for this fault.
- **AB** (abort): the ATPG engine reached its backtrack limit before finding a pattern.
- **UD** (undetected): the fault was not targeted (e.g., unreachable).

Fault coverage (FC) = DT / (DT + AU + AB + UD).

### 2.4 Fault Dropping

FAN_ATPG performs *within-run* fault dropping: after a pattern is generated, fault simulation checks whether other faults are also detected. Detected faults are marked DT and skipped in subsequent pattern generation. However, this dropping is per-run only — a new ATPG run with `add_fault --all` rebuilds the entire fault list from scratch. There is no built-in mechanism to import detections from a T=1 run into a T=2 run.

---

## 3. Problem Formulation

Given:
- A gate-level partial-scan circuit with scan FFs *S* and non-scan FFs *N*.
- An original physical fault set *F* (the T=1 collapsed fault list).
- For each time-frame depth *T*, a detected set *D_T* = {*f* ∈ *F* : *f* is DT after ATPG at depth *T*}.

The baseline is T=1 coverage: `FC_T1 = |D1| / |F|`.

The residual after T=1 is `R1 = F − D1`. Residual after T=2 is `R2 = F − D1 − D2`.

The final detection set is `D_final = D1 ∪ D2 ∪ D4`, and `FC_final = |D_final| / |F|`.

Our goal is to maximize `FC_final` while minimizing the total number of ATPG targets at T=2 and T=4.

---

## 4. Proposed Method

### 4.1 True Progressive Residual Multi-Frame ATPG

```
Algorithm: Progressive Residual ATPG
Input: Circuit C, non-scan FF set N, fault set F
Output: Detection set D_final, coverage FC_final

1. D1 = ATPG(T=1, target=F)
2. R1 = F − D1                          ▷ residual after T=1
3. D2 = ATPG(T=2, target=R1)            ▷ T=2 only on residual
4. R2 = F − D1 − D2                     ▷ residual after T=2
5. D4 = ATPG(T=4, target=R2)            ▷ T=4 only on remaining
6. D_final = D1 ∪ D2 ∪ D4
7. return D_final, |D_final| / |F|
```

### 4.2 Why This Is Better Than Naive T=4

- **Preserves T=1 detections:** T=2 and T=4 never re-target already-detected faults.
- **Reduces target count:** T=2 targets only R1 (≤|F|), T=4 targets only R2 (≤R1).
- **Avoids retargeting:** Already-detected faults are not re-tested, saving runtime and avoiding potential ABORT explosion.
- **Enables adaptive use:** If R1 is small or structurally dominated, skip T=2/T=4.

### 4.3 Adaptive Triggering

Based on our experiments, we propose a simple heuristic:

- If `coverage_gap = full_scan_FC − T1_FC < 10pp`: stop at T=1.
- If `coverage_gap ≥ 10pp` *and* the residual set is not structurally AU-dominated: run T=2, then T=4.

This heuristic correctly triggers on s27 (gap=57pp) and suppresses on b07/b13 (gap=10–23pp but AU-dominated, actual gain <2pp). However, the gap threshold must be validated on more circuits.

---

## 5. Implementation

### 5.1 Platform

Built on **ScanForge / FAN_ATPG** (NTU LaDS-II). FAN_ATPG was extended with:

- `PARTIAL_SEQUENTIAL` mode for multi-frame partial-scan unrolling.
- `set_nonscan_ff` to designate non-scan FFs.
- `add_fault -f <file>` to load a custom fault list for residual targeting.

### 5.2 Custom Residual Fault-List Loading

The `add_fault -f` command reads a text file with format `gateID SA0|SA1 faultyLine` per line. It extracts all faults from the circuit first, then loads only the matching entries into the active fault list. This enables T=2/T=4 to target exactly the residual set from the previous stage.

### 5.3 Progressive Residual Pipeline

`scripts/run_progressive_residual.py` orchestrates the full flow:

1. Runs T=1 with `add_fault --all`, parses `report_fault` to extract D1.
2. Generates residual fault file R1, runs T=2 with `add_fault -f R1`.
3. Generates residual fault file R2, runs T=4 with `add_fault -f R2`.
4. Computes union coverage D1 ∪ D2 ∪ D4 over the original physical denominator.

### 5.4 Engineering Stabilization

Several backend fixes were required to make the pipeline functional:

- **LOGIC0/LOGIC1 tie-cell fix:** `fixup_verilog.py` instantiates NanGate45 tie cells instead of creating free PI ports.
- **maxGateLevel event-stack sizing:** ATPG and simulator level-indexed arrays resized to `maxGateLevel + 1` to fix out-of-bounds crashes on ITC'99 circuits.
- **Stale mask regeneration:** Non-scan FF masks must be regenerated after each synthesis run (Yosys assigns new instance names).
- **Per-fault reporting:** `report_fault` output includes gateID and fault status for stable fault-key matching across runs.

---

## 6. Experimental Setup

### 6.1 Benchmarks

| Circuit | Source | FFs | Synthesis |
|---------|--------|-----|-----------|
| s27 | ISCAS'89 | 3 | NanGate45 |
| b07 | ITC'99 | 45 | Yosys → NanGate45 |
| b13 | ITC'99 | 65 | Yosys → NanGate45 |

### 6.2 Exclusion Ratios

| Circuit | Ratios | Non-scan FFs |
|---------|--------|-------------|
| s27 | 67% | U_G5, U_G6 (2 of 3) |
| b07 | 20%, 50% | 9, 22 of 45 |
| b13 | 20%, 50% | 13, 32 of 65 |

Non-scan FFs are selected by OpenSTA: top x% by minimum-path-slack timing criticality.

### 6.3 ATPG Configuration

- T=1, T=2, T=4 time frames
- Stuck-at fault model
- Static compression: off
- Dynamic compression: off
- Backtrack limit: 500 (default)

### 6.4 Metrics

- FC_T1, FC_T1∪T2, FC_T1∪T2∪T4 (over original physical denominator)
- Recovered faults: |D2 − D1|, |D4 − D1 − D2|
- Gain: FC_T1∪T2∪T4 − FC_T1 (percentage points)
- Runtime per stage

---

## 7. Results

### 7.1 Main Results Table

| Circuit | Excl. FFs | T=1 FC | T1∪T2 FC | T1∪T2∪T4 FC | Gain | Recovered by T2 | Recovered by T4 |
|---------|----------:|-------:|---------:|------------:|-----:|----------------:|----------------:|
| s27 x=67% | 2/3 | 37.9% | 68.2% | **81.8%** | **+43.9pp** | 20 | 9 |
| b07 x=20% | 9/45 | 28.9% | 29.3% | 30.3% | +1.4pp | 7 | 20 |
| b07 x=50% | 22/45 | 19.5% | 19.9% | 20.4% | +0.9pp | 8 | 9 |
| b13 x=20% | 13/65 | 42.2% | 42.7% | 43.6% | +1.4pp | 10 | 17 |
| b13 x=50% | 32/65 | 30.0% | 30.2% | 30.9% | +0.9pp | 4 | 12 |

![Coverage comparison across stages](figures/coverage_bar_chart.png)

*Figure 1: Progressive residual multi-frame ATPG coverage. Each group shows T=1 (blue), T1∪T2 (orange), and T1∪T2∪T4 (green). Gain in percentage points is annotated above each bar.*

### 7.2 Recovered Faults by Depth

![Recovered faults by residual depth](figures/recovered_faults_chart.png)

*Figure 2: Newly detected faults from residual T=2 (orange) and residual T=4 (green). Values above bars indicate fault count.*

### 7.3 Key Observations

1. **s27 shows strong recovery (+43.9pp).** Two-thirds of FFs are non-scan, creating a large residual set where faults are limited by sequential controllability. T=2 recovers 20 faults, T=4 adds 9 more. The union reaches 81.8% of full-scan coverage.

2. **b07/b13 show marginal recovery (+0.9–1.4pp) regardless of exclusion ratio.** At 20% exclusion, the gain is 1.4pp; at 50% exclusion, the gain actually *decreases* to 0.9pp. Higher exclusion creates more residual faults, but they are structurally untestable (AU-dominated) rather than sequentially limited.

3. **T=2 is the primary contributor on s27 but not on b07/b13.** On s27, T=2 provides 69% of total recovery; on b07, T=2 provides only 26–47%.

4. **T=4 adds more than T=2 on b07/b13 in absolute terms.** At x=20%, T=4 recovers 17–20 faults vs. 7–10 from T=2. However, the absolute gain is still marginal.

---

## 8. Discussion

### 8.1 Why s27 Benefits Strongly

s27 is a small ISCAS'89 circuit with 3 FFs. At 67% exclusion, 2 of 3 FFs are non-scan. The residual fault set (41 of 66 faults) consists of faults whose detection depends on controlling or observing those two FFs. With T=2 providing 2 cycles of state initialization and T=4 providing 4 cycles, the sequential engine can justify the required non-scan state, recovering 29 of 41 residual faults.

### 8.2 Why b07/b13 Do Not Benefit

The ITC'99 circuits b07 and b13, synthesized with NanGate45, have fundamentally different fault profiles. At T=1, 50–65% of faults are already classified as AU (structurally untestable). These AU faults are not caused by sequential constraints — they are inherent to the circuit structure (e.g., unreachable states, tied signals, redundant logic). Additional time frames cannot resolve structural untestability.

When the exclusion ratio increases from 20% to 50%, the AU count increases, but these new AU faults are also structural. The sequential recovery remains at ~0.9–1.4pp regardless of exclusion level.

### 8.3 Adaptive Use

Our results support adaptive triggering of multi-frame ATPG:

- If the coverage gap between full-scan and T=1 no-recovery is large (>20pp), and the residual faults are not structural-AU-dominated, run progressive residual T=2 → T=4.
- Otherwise, stop at T=1.

This rule correctly identifies s27 as a strong-recovery case and b07/b13 as low-gain cases. However, the specific threshold must be validated on more benchmarks.

### 8.4 Why Priority Scoring Was Abandoned

We implemented a static priority scoring function based on observability distance, controllability distance, local cone size, and fanout count. Across all circuits and ratios, priority ordering showed **no lift over random ordering** for predicting which residual faults T=2/T=4 would detect. This suggests that simple graph-theoretic features are not predictive of multi-frame ATPG solvability.

### 8.5 Limitations

- **Benchmark set is small:** Only 3 circuits, 5 cases total.
- **FAN_ATPG backend limits:** BACKTRACK_LIMIT (500) is a compile-time constant. ABORT explosion was not observed in our runs, but deeper frames or larger circuits may trigger it.
- **NanGate45 synthesis:** ITC'99 circuits synthesized with NanGate45 produce different fault profiles than ISCAS'89 circuits. Our findings may not generalize to other technology libraries.
- **T=8 not evaluated:** The project spec originally proposed T=8. Our progressive method supports arbitrary depths, but T=8 experiments were not run.
- **b05, b11, b12, b14, b15:** Several ITC'99 circuits were not testable due to Verilog syntax issues, ATPG timeouts, or runtime concerns.

---

## 9. Related Work

Partial-scan DFT has been studied since the 1990s [Agrawal et al., JETA'92; Cheng & Agrawal, JETA'92]. Classical methods select FFs for scan based on SCOAP testability metrics. More recent work explores stress-aware and power-aware selection [Cho & Pan, VTS'06; Remersaro et al., ATS'07].

Sequential ATPG with time-frame expansion is a standard technique [Fujiwara & Shimono, 1983]. The FAN algorithm with multi-frame unrolling is implemented in academic ATPG tools including FAN_ATPG (NTU LaDS-II).

Our contribution is not a new selection method or ATPG algorithm, but a *pipeline design*: true progressive residual targeting with custom fault-list loading, fixed-denominator union coverage, and adaptive triggering. This enables practical evaluation of multi-frame recovery under timing-driven non-scan constraints.

---

## 10. Conclusion

We presented *True Progressive Residual Multi-Frame ATPG*, a method for evaluating coverage recovery in partial-scan circuits under fixed non-scan constraints. The key contributions are:

1. **Residual pipeline:** T=1 → T=2 residual → T=4 residual, with custom fault-list loading and fixed-denominator union coverage.
2. **Implementation:** `add_fault -f <file>` for residual targeting; `run_progressive_residual.py` for end-to-end automation.
3. **Empirical evidence:** +43.9pp recovery on s27 x=67%; marginal recovery (+1.4pp) on b07/b13, independent of exclusion ratio.
4. **Adaptive recommendation:** Multi-frame ATPG should be triggered only when T=1 coverage loss is large and residual faults are not structurally dominated.

The honest conclusion is that progressive residual multi-frame ATPG is effective under the right residual-fault conditions, but not universally. Future work should explore better residual classification (to predict which AU faults are genuinely sequential), T=8 evaluation, budget control, and a larger benchmark set.

---

## 11. Appendix

### A. Engineering Stabilization

| Issue | Fix |
|-------|-----|
| Floating QN nets rejected by FAN_ATPG | ERROR→WARN in `netlist.cpp` |
| `_const0_` as free module port | LOGIC0_X1/LOGIC1_X1 tie cells in `fixup_verilog.py` |
| OOB crash in level-indexed arrays | `maxGateLevel + 1` sizing |
| Stale mask FF names after re-synthesis | `gen_nonscan_masks.sh` after synthesis |
| `report_fault` prints nothing without `-s` | Fix `stateSet &&` logic |
| DFF faults lack cell instance name | Print cell name for all gate types |

### B. Result File Locations

| File | Content |
|------|---------|
| `results/progressive_residual_summary.csv` | Full 5-case experiment table |
| `results/residual_faults/` | Per-stage residual fault lists |
| `results/itc99_partial_scan.csv` | Full ITC'99 backend status |
| `scripts/run_progressive_residual.py` | Pipeline runner |
| `scripts/analyze_residual.py` | Post-processing fault overlap analysis |

### C. Remaining Blockers

| Blocker | Status |
|---------|--------|
| b05 assign syntax | Verilog parser incompatibility |
| b11, b12, b14 timeout | ATPG >120s |
| b15 untested | 839 FFs, runtime concern |
| T=8 not evaluated | Future work |
| BACKTRACK_LIMIT compile-time | Not varied for experiments |
| Priority scoring not effective | Abandoned |

---

## References

[1] H. Fujiwara and T. Shimono, "On the acceleration of test generation algorithms," *IEEE Trans. Computers*, vol. C-32, no. 12, 1983.

[2] V. D. Agrawal, K.-T. Cheng, D. D. Johnson, and T. Lin, "Testability-based partial scan analysis," *J. Electronic Testing*, vol. 3, 1992.

[3] K.-T. Cheng and V. D. Agrawal, "Partial scan flip-flop selection by use of empirical testability," *J. Electronic Testing*, vol. 3, 1992.

[4] F. Corno, M. S. Reorda, and G. Squillero, "RT-level ITC'99 benchmarks and first ATPG results," *IEEE Design & Test*, vol. 17, no. 3, 2000.

[5] M. Cho and D. Z. Pan, "PEAKASO: Peak-Temperature Aware Scan-Vector Optimization," *Proc. VTS*, 2006.

[6] S. Remersaro et al., "Scan Cell Reordering for Peak Power Reduction during Scan Test Cycles," *Proc. ATS*, 2007.

[7] NanGate Open Cell Library, FreePDK 45nm.

[8] NTU LaDS-II, FAN_ATPG, https://github.com/NTU-LaDS-II/FAN_ATPG.
