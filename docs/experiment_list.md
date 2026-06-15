# Experimental Design

All experiments run the **same progressive residual pipeline** (T=1→T=2→T=4) on the **same 15 circuits** (8 ITC'99 + 7 ISCAS'89). Each experiment changes exactly **one parameter** relative to the baseline.

## Unified Pipeline Configuration

```
Stage  T=1: all faults, 1 frame, T1_BACKTRACK_LIMIT=800
Stage  T=2: residual R1, T frames=2, BACKTRACK=5000
Stage  T=4: residual R2, T frames=4, BACKTRACK=5000
FC = |D1 ∪ D2 ∪ D4| / |F|
```

- No pattern compression.
- No per-target timeout; bounding via backtrack limit only.
- No enhancement flags unless specified.

## Experiment overview

| # | Name | Changed parameter | Status |
|---|------|-------------------|--------|
| 1 | Baseline | — | **Partial** (11/15 circuits done; b11,b13 T=2 timeout; s15850,s35932 pending) |
| 2 | Two-Phase ON | Two-Phase: OFF→ON at T>1 | **Partial** (13/15 circuits done; b11,s35932 excluded — runner crashes; see below) |
| 3 | Uniform T1 | T1: 800→5000 | **Partial** (10/15 circuits; b13,s9234,s15850 timeout; b11,s35932 excluded) |
| 4 | Enhanced Backtrace | `set_enhanced_backtrace on` | **Running** |
| 5 | Static Learning | `set_static_learning on` | **Pending** |
| B2 | Full-scan (reference) | All FFs scan, T=1 | **Done** |

## Results file mapping

| Exp | Data file | Content |
|-----|-----------|---------|
| 1 | `results/exp1_baseline.csv` | Per-circuit pipeline FC, runtime, fault counts |
| 2 | `results/exp2_two_phase.csv` | Same fields, Two-Phase ON |
| 3 | `results/exp3_uniform_T1.csv` | Same fields, T1=5000 |
| 4 | `results/exp4_enhanced_backtrace.csv` | Same fields, enhanced backtrace ON |
| 5 | `results/exp5_static_learning.csv` | Same fields, static learning ON |
| B2 | `results/phase_d_fullscan_dataset.csv` | ITC'99 full-scan FC |
| B2 | `results/iscas89_fullscan_baseline.csv` | ISCAS'89 full-scan FC |
| all | `results/sweep_log.txt` | Execution log (timestamps, timeouts) |
| all | `results/residual_faults/` | Per-circuit T=2 and T=4 residual fault lists |

## CSV fields (same schema for all 5 experiments)

```
circuit, ratio, excluded_ff, total_ff, denominator,
T1_DT, T1_AU, T1_AB, T1_TO, T1_FC,
R1_count, T2_target, T2_new_DT, T2_AU, T2_AB, T2_TO,
R2_count, T4_target, T4_new_DT, T4_AU, T4_AB, T4_TO,
final_DT, FC_T1, FC_T1_T2, FC_T1_T2_T4,
gain_T2_pp, gain_T4_pp, total_gain_pp,
T1_rt, T2_rt, T4_rt, total_rt,
recovered_per_sec_T2, recovered_per_sec_T4,
per_target_timeout_sec, status
```

## Detailed design

### Experiment 1: Baseline

Two-Phase OFF. T1=800. FC_T1 = B1 (partial-scan reference). FC_T1∪T2∪T4 = pipeline result.

**Result file:** `results/exp1_baseline.csv`
**Status:** Partial. 11/15 circuits collected. b11/b13 T=2 timeout (Two-Phase OFF too slow for control-heavy circuits). s15850/s35932 killed mid-run (restart pending).

---

### Experiment 2: Two-Phase ON

**Change:** `set_two_phase_justification on` at T>1.
**Diagnosis:** If FC exceeds Exp 1 → decoupling propagation from state justification is the recovery mechanism. Expected to run faster than Exp 1 for b11/b13.

**Result file:** `results/exp2_two_phase.csv`
**Status:** Partial. 11/15 circuits collected. b11 T=2 timeout (~3 min), s9234/s15850/s35932 pending (restart with 180s timeout).

Preliminary results (13 circuits): Two-Phase ON significantly outperforms Exp 1 baseline.
b05 recovered 2626 faults at T=2 (vs 7 in Exp 1), FC=87.68% (vs 29.2% T=1).
b07 FC=87.93% (vs 56.13% T=1), s953 FC=91.26% (vs 36.75% T=1), s15850 FC=90.16%.
These confirm Two-Phase is the primary recovery mechanism — Exp 1 without it gains almost nothing at T=2.

**Note:** b11 and s35932 excluded from all experiments — runner produces empty output with no error.

---

### Experiment 3: Uniform T1

**Change:** T1 raised from 800 to 5000 at T=1.
**Diagnosis:** If gain over Exp 1 shrinks → the T1 limit differential is what creates the residual.

**Result file:** `results/exp3_uniform_T1.csv`
**Status:** Partial. 10/15 circuits collected. b13/s9234/s15850 timeout (180s; T1=5000 too slow for large circuits).

Key results: Uniform T1=5000 with Two-Phase OFF yields lower final FC than Two-Phase ON (Exp 2) for most circuits, confirming Two-Phase is more impactful than T1 limit. b03 gain=0pp (T1 already saturated), b04 gain=10.21pp, b05 gain=16.9pp, b08 gain=19.02pp.

---

### Experiment 4: Enhanced Backtrace

**Change:** `set_enhanced_backtrace on` (composite-score heuristic: 0.6×SCOAP_controllability + 0.3×depth − 0.1×fanout).
**Diagnosis:** Does composite-score backtrace improve FC or reduce aborts vs SCOAP-only?

**Result file:** `results/exp4_enhanced_backtrace.csv`
**Status:** Running (started; small ITC'99 circuits done, ISCAS pending).

---

### Experiment 5: Static Learning

**Change:** `set_static_learning on` (fanout-implication precomputation — immediate implications only, not full recursive SOCRATES).
**Diagnosis:** Does early conflict detection reduce backtracks or improve FC?

**Result file:** `results/exp5_static_learning.csv`

---

### B2: Full-Scan Reference Ceiling

Not an ablation experiment. Upper-bound for gap-to-full-scan analysis.

**Result files:** `results/phase_d_fullscan_dataset.csv` (ITC'99), `results/iscas89_fullscan_baseline.csv` (ISCAS'89).

**Status:** Done.
