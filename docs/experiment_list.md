# Experimental Design

All experiments run the **same progressive residual pipeline** (T=1→T=2→T=4) on the **same 15 circuits**. Each experiment changes exactly **one parameter** relative to the baseline pipeline (Exp 1).

**15 circuits:** 8 ITC'99 (b03–b13) + 7 ISCAS'89 (s953, s1196, s1238, s5378, s9234, s15850, s35932).

## Unified Pipeline Configuration

Baseline (Exp 1):
```
Stage  T=1: all faults, 1 frame, T1=800
Stage  T=2: residual R1, 2 frames, BACKTRACK=5000, Two-Phase OFF
Stage  T=4: residual R2, 4 frames, BACKTRACK=5000, Two-Phase OFF
FC = |D1 ∪ D2 ∪ D4| / |F|
```

- No pattern compression.
- No per-target timeout; bounding via backtrack limit only.
- No enhancement flags unless specified.

## Experiment overview

| # | Name | Changed parameter | Unique runs | Status |
|---|------|-------------------|-------------|--------|
| 1 | Pipeline (baseline) | — | 15 × 3 = 45 | **Done†** |
| 2 | Full-scan baseline (B2) | All FFs scan (separate setup) | 15 × 1 = 15 | **Done** |
| 3 | Mechanism: Uniform T1 | T1: 800 → 5000 | 15 × 3 = 45 | **Pending** |
| 4 | Mechanism: Two-Phase | Two-Phase: OFF → ON | 15 × 3 = 45 | **Pending** |
| 5 | Enhanced backtrace | `set_enhanced_backtrace on` | 15 × 3 = 45 | **Pending** |
| 6 | Static learning | `set_static_learning on` | 15 × 3 = 45 | **Pending** |

Total runs: 225 (45 per pipeline experiment). Exp 1 + 2 done; remaining 180.

† Pipeline data currently covers 9 circuits; remaining 6 pending.

## Detailed design

### Experiment 1: Progressive Residual Pipeline (baseline)

Two-Phase OFF. T1=800. FC_T1 = B1 (partial-scan baseline). FC_T1∪T2∪T4 = pipeline result.

**Result file:** `results/progressive_residual_summary.csv`

**Status:** **Done** (9/15 circuits; 6 pending).

---

### Experiment 2: Full-Scan Baseline (B2)

T=1, all FFs scan, BACKTRACK=5000, no `set_nonscan_ff`. Upper-bound reference.

**Result files:** `results/phase_d_fullscan_dataset.csv` (ITC'99), `results/iscas89_fullscan_baseline.csv` (ISCAS'89).

**Status:** **Done.**

---

### Experiment 3: Uniform T1 (Mechanism)

**Change:** T1 limit raised from 800 to 5000.

**Diagnoses:** If gain over Exp 1 shrinks → the T1 limit differential is what creates the residual.

---

### Experiment 4: Two-Phase State Justification (Mechanism)

**Change:** Two-Phase OFF → ON at T=2 and T=4.

**Diagnoses:** If FC improves over Exp 1 → Two-Phase is the recovery mechanism.

---

### Experiment 5: Enhanced Backtrace Ablation

**Change:** `set_enhanced_backtrace on` (PCA composite scoring).

**Diagnoses:** Does PCA backtrace improve FC or reduce aborts vs SCOAP-only?

---

### Experiment 6: Static Learning Ablation

**Change:** `set_static_learning on` (SOCRATES-style implication precomputation).

**Diagnoses:** Does early conflict detection reduce backtracks or improve FC?
