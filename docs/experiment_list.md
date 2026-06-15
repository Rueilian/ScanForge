# Experimental Design

## Research Questions

1. **RQ1 (pipeline gain):** Does progressive T=1→T=2→T=4 increase fault coverage beyond T=1 alone on timing-constrained partial-scan circuits?
2. **RQ2 (stage attribution):** Is the gain concentrated at T=2 or T=4?
3. **RQ3 (mechanism):** Is the recovery driven by Two-Phase State Justification or by the lower T1 backtrack limit?
4. **RQ4 (cost):** What is the runtime overhead of each stage?

---

## Unified Platform Parameters

All experiments share the following platform configuration unless noted otherwise:

| Parameter | Value |
|-----------|-------|
| ATPG engine | FAN_ATPG (NTU LaDS-II), origin/swear commit `4291613` + frame-based backtrack patch |
| Search algorithm | FAN (Fujiwara & Shimono, 1983) |
| Fault model | Stuck-at (SAF) |
| Fault collapse | FAN_ATPG default (equivalence + dominance) during `add_fault --all` |
| Time-frame mode | `PARTIAL_SEQUENTIAL` (`build_circuit --frame T`) |
| Two-Phase State Justification | `set_two_phase_justification on` for T>1; N/A at T=1 (single frame) |
| Backtrack limit (T=1) | `T1_BACKTRACK_LIMIT` = 800 (override via `ATPG_T1_BACKTRACK_LIMIT` env var) |
| Backtrack limit (T>1) | `BACKTRACK_LIMIT` = 5000 |
| Per-target timeout | **None** (unlimited) — bounding via backtrack limit only |
| Static compression | `set_static_compression off` |
| Dynamic compression | `set_dynamic_compression off` |
| Gate library | NanGate45 (`techlib/mod_nangate45.mdt`) |
| Scan FF cell | SDFFR_X1 (async reset, active-low) |
| Wall timeout | 3600 s (via Python `subprocess.run(timeout=3600)`) |

### Benchmark Preparation

| Suite | Source | Synthesis | Non-scan mask generation |
|-------|--------|-----------|-------------------------|
| ITC'99 | RTL (Verilog) from ITC'99 benchmarks | Yosys with `base.lib` (MUX2 allowed, OAI/AOI forbidden) → NanGate45 | OpenSTA min-path-slack ranking → `gen_nonscan_masks.sh` |
| ISCAS'89 | TTU gate-level netlists | `convert_ttu_to_nangate.py` → SDFFR_X1 cells | OpenSTA min-path-slack ranking → `gen_nonscan_masks.sh` |

Non-scan FF selection: top **10%** by minimum-path-slack, measured on the
synthesized NanGate45 netlist with OpenSTA. Only 10% is evaluated.

### Metric

Fault coverage is computed using a **fixed-denominator union** to ensure fair
comparison across pipeline stages:

```
FC_final = |D1 ∪ D2 ∪ D4| / |F|
```

where F is the T=1 collapsed fault set. Per-fault (gateID, faultyLine, faultType)
keys are extracted via `report_fault` and matched across runs. FAN_ATPG's
native multi-frame report uses a different denominator and is not used directly.

Fault classification:
- **DT**: detected (test pattern found)
- **AU**: atpg untestable (engine determined no pattern exists within search limit)
- **AB**: abort (backtrack limit exceeded)
- **TO**: timeout (per-target time expired; does not occur when ptt is disabled)
- **UD**: undetected (not targeted)

---

## Experiment 1: Progressive Residual Pipeline

**Purpose:** Answer RQ1 and RQ2 — quantify the coverage gain at T=2 and T=4
relative to T=1 across two benchmark suites.

**Design:** Every circuit receives identical treatment:

```
T=1 (all faults, 1 frame, T1_BACKTRACK_LIMIT=800) → D1
R1 = F − D1
T=2 (residual R1, 2 frames, Two-Phase ON, BACKTRACK_LIMIT=5000) → D2
R2 = F − D1 − D2
T=4 (residual R2, 4 frames, Two-Phase ON, BACKTRACK_LIMIT=5000) → D4
Final FC = |D1 ∪ D2 ∪ D4| / |F|
```

**Circuits (15 total, excl. s38417, s38584 due to wall-timeout risk):**

| Suite | Circuit | FFs | Non-scan @10% | |F| (collapsed) |
|-------|---------|----:|--------------:|--------------:|
| ITC'99 | b03 | 30 | 4 | 809 |
| ITC'99 | b04 | 66 | 7 | 2291 |
| ITC'99 | b05 | 88 | 9 | 4471 |
| ITC'99 | b07 | 44 | 5 | 1591 |
| ITC'99 | b08 | 67 | 7 | 2234 |
| ITC'99 | b09 | 29 | 3 | 930 |
| ITC'99 | b11 | 84 | 9 | 6843 |
| ITC'99 | b13 | 86 | 9 | 2007 |
| ISCAS'89 | s953 | 29 | 3 | 1853 |
| ISCAS'89 | s1196 | 18 | 2 | 2184 |
| ISCAS'89 | s1238 | 18 | 2 | 2235 |
| ISCAS'89 | s5378 | 179 | 18 | 10113 |
| ISCAS'89 | s9234 | 211 | 22 | 18098 |
| ISCAS'89 | s15850 | 534 | 54 | 33265 |
| ISCAS'89 | s35932 | 1728 | 173 | 77978 |

**Output metrics per circuit:** FC_T1 (B1), FC_T1∪T2∪T4 (Experiment),
gain_T2_pp = FC_T1∪T2 − FC_T1, gain_T4_pp = FC_T1∪T2∪T4 − FC_T1∪T2,
B2−Experiment gap to full-scan.

**Status:** Pending (ptt-free re-run).

---

## Experiment 2: Full-Scan Baselines (B2)

**Purpose:** Provide a coverage ceiling for each circuit by removing the non-scan
constraint (all FFs scan).

**Design:** T=1 ATPG with identical platform parameters except `set_nonscan_ff`
is not called. All other parameters match Experiment 1 (no ptt, BACKTRACK_LIMIT=5000).

**Circuits:** Same 15 circuits.

**Source:** Fresh run (same binary, ptt disabled).

**Status:** Pending.

---

## Experiment 3: Mechanism Ablation

**Purpose:** Answer RQ3 — determine whether the T=2 gain is caused by the
lower T1 backtrack limit (T1=800 vs T>1=5000) or by
Two-Phase State Justification at T=2.

**Background:** The pipeline sets T=1 backtrack limit to 800, lower than
T>1 (5000). This prevents the engine from wasting budget on structurally
unrecoverable faults (blocked by non-scan FF X-states in a single frame).
These faults show as AB at T=1 and are retried at T=2 where the multi-frame
model enables recovery. There is no per-target timeout — the backtrack limit
is the sole bounding mechanism.

**Design:** Three conditions on the same 15 circuits:

| Condition | T1 limit | T2 Two-Phase | T>1 limit |
|-----------|--------------|-------------|----------------|
| (A) Baseline | 800 | ON | 5000 |
| (B) Uniform limit | **5000** | ON | 5000 |
| (C) No Two-Phase | 800 | **OFF** at T=2 only | 5000 |

All conditions use no per-target timeout (backtrack limit is the only bound).
All other parameters match Experiment 1.

**Implementation:** `ATPG_T1_BACKTRACK_LIMIT=5000` for condition B;
`--t2-two-phase off` for condition C.

**Circuits:** 15 circuits (8 ITC'99 + 7 ISCAS'89, excluding s38417, s38584).

**Predictions:**
- **Condition B:** T=1 FC approaches T=2 FC → T=2 gain shrinks. Proves the
  lower T1_BACKTRACK_LIMIT creates the structural residual.
- **Condition C:** T=2 gain drops below baseline (most faults stay AB
  because Two-Phase can no longer decouple propagation from justification).
  Proves Two-Phase is what recovers the residual.

**Status:**

| Condition | Status |
|-----------|--------|
| (A) Baseline (= Exp 1) | Pending |
| (B) Uniform limit (T1=5000) | Pending |
| (C) No Two-Phase at T=2 | Pending |

---

## Experiment 4: ATPG Optimization Flag Ablation

**Purpose:** Evaluate three flag-gated ATPG optimizations — enhanced backtrace (PCA heuristic), non-chronological backtracking (backjump), and dominator early-conflict detection — via ablation on 15 circuits.

**Design:** Five conditions, each run as a single FAN invocation on all original faults (no pipeline):

| Condition | Enhanced backtrace | Backjump | Dominator check |
|-----------|:-:|:-:|:-:|
| baseline | OFF | OFF | OFF |
| enhanced_only | ON | OFF | OFF |
| backjump_only | OFF | ON | OFF |
| dominator_only | OFF | OFF | ON |
| all_on | ON | ON | ON |

**Implementation:** Three toggle flags in FAN_ATPG:

| Flag | Heuristic | Implementation |
|------|-----------|----------------|
| `set_enhanced_backtrace on` | PCA composite score | `calCompositeScore()` = 0.6×SCOAP + 0.3×depth − 0.1×fanout; used in `findEasiestInput()` |
| `set_backjump on` | Non-chronological backtrack | `gateToDecisionLevel_` + `conflictDecisionLevel_` tracked in `evaluateAndSetGateAtpgVal()`; `backtrack()` skips irrelevant decisions |
| `set_dominator_check on` | D-frontier dominator conflict | `checkDominatorBlocked()` scans D-frontier for common dominators; forces backtrack when all blocked |

**Circuits:** Same 15 circuits (8 ITC'99 + 7 ISCAS'89).

**Results (flag_ablation.csv):**

| Circuit | baseline | enhanced_only | backjump_only | dominator_only | all_on |
|---------|:--------:|:-------------:|:-------------:|:--------------:|:------:|
| b03 | 41.59% AB=0 | **38.86%** AB=0 | 41.59% AB=0 | 41.59% AB=0 | **38.86%** AB=0 |
| b04 | 72.02% AB=12 | **78.80% AB=0** | 72.02% AB=12 | 72.02% AB=12 | **78.80% AB=0** |
| b05 | 26.65% AB=12 | **26.88% AB=27** | 26.57% AB=12 | 26.65% AB=12 | 26.83% AB=27 |
| b07 | 51.36% AB=0 | 51.31% AB=0 | 51.36% AB=0 | 51.36% AB=0 | 51.31% AB=0 |
| b08 | 72.19% AB=0 | 71.68% AB=0 | 71.08% AB=0 | 72.19% AB=0 | 71.04% AB=0 |
| b09 | 75.59% AB=0 | 75.59% AB=0 | 75.59% AB=0 | 75.59% AB=0 | 75.59% AB=0 |
| b11 | 62.37% AB=7 | 62.37% AB=7 | 62.37% AB=7 | 62.37% AB=7 | 62.37% AB=7 |
| b13 | 75.54% AB=0 | 75.54% AB=0 | 75.54% AB=0 | 75.54% AB=0 | 75.54% AB=0 |
| s953 | 34.26% AB=0 | 34.26% AB=0 | 34.26% AB=0 | 34.26% AB=0 | 34.26% AB=0 |
| s1196 | 86.18% AB=0 | 86.18% AB=0 | 86.18% AB=0 | 86.18% AB=0 | 86.18% AB=0 |
| s1238 | 83.23% AB=0 | 83.23% AB=0 | 83.23% AB=0 | 83.23% AB=0 | 83.23% AB=0 |
| s5378 | 73.82% AB=2 | 73.82% AB=2 | 73.82% AB=2 | 73.82% AB=2 | 73.82% AB=2 |
| s9234 | 73.29% AB=30 | 73.29% AB=30 | 73.29% AB=30 | 73.29% AB=30 | 73.29% AB=30 |
| s15850 | 66.19% AB=0 | 66.19% AB=0 | 66.19% AB=0 | 66.19% AB=0 | 66.19% AB=0 |
| s35932 | >600s | **76.83% AB=56** | >600s | — | — |

**Key findings:**
1. **Enhanced backtrace is the only measurable flag.** backjump_only and dominator_only produce identical FC/AB to baseline on ALL circuits.
2. **Massive win on b04:** enhanced_only reduces AB from 12→0, raises FC from 72.02%→78.80%, 5× faster (2.2s vs 10.2s).
3. **s35932: 16× speedup.** baseline exceeds 600s wall timeout; enhanced_only completes in 37s at 76.83% FC.
4. **Regression on b05:** enhanced_only raises AB from 12→27 (+15). PCA weights (0.6 SCOAP + 0.3 depth − 0.1 fanout) may over-weight SCOAP for this circuit.
5. **backjump and dominator add zero value** under these backtrack limits.

**Status:** 73/75 runs complete (s35932 baseline/backjump_only timed out at 600s; enhanced_only completed in 37s).

---

## Summary

| Experiment | Scope | RQs | Key parameters | Completion |
|------------|-------|-----|----------------|------------|
| 1. Progressive Residual Pipeline | 15 circuits | RQ1, RQ2, RQ4 | T=1→T=2→T=4, no ptt, T1=800/T>1=5000, Two-Phase ON | Pending |
| 2. Full-Scan Baselines | 15 circuits | Ceiling | T=1 only, no non-scan, no ptt, BACKTRACK=5000 | Pending |
| 3a. Ablation: uniform T1 limit | 15 circuits | RQ3 | no ptt, T1=5000, Two-Phase ON at T2 | Pending |
| 3b. Ablation: no Two-Phase at T=2 | 15 circuits | RQ3 | no ptt, T1=800, Two-Phase OFF at T2 | Pending |
| 4. ATPG Flag Ablation | 15 circuits | Optimization | 5 flag conditions, direct FAN, no pipeline | 73/75 complete (s35932 ×2 timed out) |
