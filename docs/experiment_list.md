# Experimental Design

## Research Questions

1. **RQ1 (pipeline gain):** Does progressive T=1→T=2→T=4 increase fault coverage beyond T=1 alone on timing-constrained partial-scan circuits?
2. **RQ2 (stage attribution):** Is the gain concentrated at T=2 or T=4?
3. **RQ3 (mechanism):** Is the recovery driven by Two-Phase State Justification or by the frame-based fast backtrack limit at T=1?
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
| Backtrack limit (T=1) | `FAST_BACKTRACK_LIMIT` = 800 (override via `ATPG_FAST_BACKTRACK_LIMIT` env var) |
| Backtrack limit (T>1) | `BACKTRACK_LIMIT` = 5000 |
| Static compression | `set_static_compression off` |
| Dynamic compression | `set_dynamic_compression off` |
| Gate library | NanGate45 (`techlib/mod_nangate45.mdt`) |
| Scan FF cell | SDFFR_X1 (async reset, active-low) |
| Per-target timeout | 5 s (`set_per_target_timeout 5.0`) |
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
- **TO**: timeout (per-target time expired)
- **UD**: undetected (not targeted)

---

## Experiment 1: Progressive Residual Pipeline

**Purpose:** Answer RQ1 and RQ2 — quantify the coverage gain at T=2 and T=4
relative to T=1 across two benchmark suites.

**Design:** Every circuit receives identical treatment:

```
T=1 (all faults, 1 frame, ptt=5 s) → D1
R1 = F − D1
T=2 (residual R1, 2 frames, Two-Phase ON, ptt=5 s) → D2
R2 = F − D1 − D2
T=4 (residual R2, 4 frames, Two-Phase ON, ptt=5 s) → D4
Final FC = |D1 ∪ D2 ∪ D4| / |F|
```

**Circuits (17 total):**

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
| ISCAS'89 | s38417 | 1636 | 164 | 82810 |
| ISCAS'89 | s38584 | 1426 | 143 | 81247 |

**Output metrics per circuit:** FC_T1 (B1), FC_T1∪T2∪T4 (Experiment),
gain_T2_pp = FC_T1∪T2 − FC_T1, gain_T4_pp = FC_T1∪T2∪T4 − FC_T1∪T2,
B2−Experiment gap to full-scan.

**Status:** All 17 circuits completed.

---

## Experiment 2: Full-Scan Baselines (B2)

**Purpose:** Provide a coverage ceiling for each circuit by removing the non-scan
constraint (all FFs scan).

**Design:** T=1 ATPG with identical platform parameters except `set_nonscan_ff`
is not called. All other parameters match Experiment 1.

| Suite | Source | ptt |
|-------|--------|-----|
| ISCAS'89 | Fresh run (same binary, same ptt=5 s) | 5 s |
| ITC'99 | Legacy Phase D reference run | 0 (unlimited) |

**Circuits:** All 17 (ISCAS'89 fresh; ITC'99 from Phase D dataset).

**Status:** Complete.

---

## Experiment 3: Mechanism Ablation

**Purpose:** Answer RQ3 — determine whether the T=2 gain is caused by the
frame-based fast backtrack limit (FAST=800 at T=1 vs 5000 at T>1) or by
Two-Phase State Justification at T=2.

**Background:** The pipeline sets T=1 backtrack limit to FAST=800 lower than
T>1 (5000). This prevents the engine from wasting budget on structurally
unrecoverable faults (blocked by non-scan FF X-states in a single frame).
These faults show as AB at T=1 and are retried at T=2 where the multi-frame
model enables recovery. ptt=5 s is an additional safety-net bound but has
been shown via separate ablation (no_ptt on b03–b09, results identical to
baseline) to be irrelevant given the backtrack limits — the frame-based
fast limit is the real bounding mechanism.

**Design:** Three conditions on 15 circuits (excl. s38417, s38584 due to wall-timeout risk at ptt=0):

| Condition | T1 fast limit | T1/T>1 ptt | T2 Two-Phase | T>1 fast limit |
|-----------|--------------|-----------|-------------|----------------|
| (A) Baseline | 800 | **0** | ON | 5000 |
| (B) No fast limit | **5000** | 0 | ON | 5000 |
| (C) No Two-Phase | 800 | 0 | **OFF** at T=2 only | 5000 |

All conditions use **ptt=0** to avoid confound: the bounding mechanism must
be the backtrack limit, not the per-target timeout. All other parameters match
Experiment 1.

**Implementation:** `ATPG_FAST_BACKTRACK_LIMIT=5000` for condition B;
`--t2-two-phase off` for condition C; `ATPG_PER_TARGET_TIMEOUT=0` for all.

**Circuits:** 15 circuits (8 ITC'99 + 7 ISCAS'89, excluding s38417, s38584).

**Predictions:**
- **Condition B:** T=1 FC approaches T=2 FC → T=2 gain shrinks. Proves the
  FAST_BACKTRACK_LIMIT at T=1 is what creates the structural residual.
- **Condition C:** T=2 gain drops below baseline (most faults stay AB
  because Two-Phase can no longer decouple propagation from justification).
  Proves Two-Phase is what recovers the residual.

**Status:**

| Condition | Status |
|-----------|--------|
| (A) Baseline (ptt=0, re-run) | Pending (separate run) |
| (B) No fast limit (T1=5000) | Pending |
| (C) No Two-Phase at T=2 | Pending |

---

## Summary

| Experiment | Scope | RQs | Key parameters | Completion |
|------------|-------|-----|----------------|------------|
| 1. Progressive Residual Pipeline | 17 circuits | RQ1, RQ2, RQ4 | T=1→T=2→T=4, ptt=5s, Two-Phase ON, 10% non-scan | 17/17 |
| 1b. Baseline (ptt=0) for ablation comparison | 15 circuits | RQ3 control | Same as Exp. 1 but ptt=0 | Pending |
| 2. Full-Scan Baselines | 17 circuits | Ceiling | T=1 only, no non-scan, ptt=5s (ISCAS'89) / ptt=0 (ITC'99) | 17/17 |
| 3a. Ablation: no fast limit at T=1 | 15 circuits | RQ3 | ptt=0, FAST=5000 at T1, Two-Phase ON at T2 | Pending |
| 3b. Ablation: no Two-Phase at T=2 | 15 circuits | RQ3 | ptt=0, FAST=800, Two-Phase OFF at T2 | Pending |
