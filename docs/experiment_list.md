# Experimental Design

All experiments run the **same progressive residual pipeline** (T=1→T=2→T=4) on the **same 15 circuits** (8 ITC'99 + 7 ISCAS'89). Each experiment changes exactly **one parameter** relative to the baseline.

**Report-ready subset:** 10 circuits that PASS in all 5 experiments — b03, b04, b05, b07, b08, b09, s953, s1196, s1238, s5378. Primary ablation narrative uses **x = 10%** non-scan exclusion; **ratio sweep R1** (§ below) extends Exp 1–5 to **5%–20%**. Remaining 5 (b11, b13, s9234, s15850, s35932) excluded from report tables.

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
|:--:|------|-------------------|--------|
| 1 | Baseline | — | **10 common PASS** (b03,b04,b05,b07,b08,b09,s953,s1196,s1238,s5378 complete; b11/b13/s9234/s15850/s35932 pending) |
| 2 | Two-Phase ON | Two-Phase: OFF→ON at T>1 | **10 common PASS** |
| 3 | Uniform T1 | T1: 800→5000 | **10 common PASS** |
| 4 | Enhanced Backtrace | `set_enhanced_backtrace on` | **10 common PASS** |
| 5 | Static Learning | `set_static_learning on` | **10 common PASS** |
| B2 | Full-scan (reference) | All FFs scan, T=1 | **Done** |
| R1 | **Ratio sweep** | Non-scan x = 5/10/15/20%; Exp 1–5 each | **Done** (10 circuits, 200/200 PASS) |

## Results file mapping

| Exp | Data file | Content |
|-----|-----------|---------|
| 1 | `results/exp1_baseline.csv` | Per-circuit pipeline FC, runtime, fault counts, memory (VmPeak MB) @10% |
| 2 | `results/exp2_two_phase.csv` | Same fields, Two-Phase ON @10% |
| 3 | `results/exp3_uniform_T1.csv` | Same fields, T1=5000 @10% |
| 4 | `results/exp4_enhanced_backtrace.csv` | Same fields, enhanced backtrace ON @10% |
| 5 | `results/exp5_static_learning.csv` | Same fields, static learning ON @10% |
| R1 | `results/ratio_sweep/x{pct}/exp{N}_*.csv` | Same schema; x = 5/10/15/20%, Exp 1–5 |
| B2 | `results/phase_d_fullscan_dataset.csv` | ITC'99 full-scan FC |
| B2 | `results/iscas89_fullscan_baseline.csv` | ISCAS'89 full-scan FC |
| all | `results/sweep_log.txt` | Ablation execution log (@10%) |
| R1 | `results/ratio_sweep_log.txt` | Ratio sweep execution log |
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
T1_mem_mb, T2_mem_mb, T4_mem_mb, peak_mem_mb,
per_target_timeout_sec, status
```

**Memory fields:** Per-stage VmPeak (MB) from FAN `report_memory_usage` at the end of each T=1, T=2, and T=4 FAN invocation. `peak_mem_mb` = max(T1, T2, T4) for that circuit run. Stages run in separate processes, so peaks are not summed.

## Memory usage (10 circuits, all 5 experiments)

**Measurement:** FAN VmPeak from `/proc/self/status`, recorded after each pipeline stage. Pipeline peak is the maximum across the three stage runs.

**Frame-depth scaling (Exp 1 baseline):** T=4 always dominates peak memory. T4/T1 ratio is 1.05×–1.17× on small/medium circuits and 1.26× on s5378 (largest evaluated).

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

**Ablation impact on memory:** Average pipeline peak is nearly identical across all five experiments (~15 MB). Ablation flags (Two-Phase, uniform T1, enhanced backtrace, static learning) do not materially change peak memory; frame unrolling at T=4 is the dominant factor. Two-Phase ON raises T=2 VmPeak on s5378 (26.1→28.9 MB) but pipeline peak remains ~31 MB.

| Exp | Avg peak (MB) | Max peak (MB) | Worst circuit |
|:---:|:-------------:|:-------------:|:-------------|
| 1 Baseline | 14.96 | 31.43 | s5378 |
| 2 Two-Phase ON | 14.91 | 31.25 | s5378 |
| 3 Uniform T1 | 14.96 | 31.43 | s5378 |
| 4 Enhanced Backtrace | 14.96 | 31.43 | s5378 |
| 5 Static Learning | 15.04 | 32.00 | s5378 |

**Takeaway:** Peak memory stays modest on all 10 report circuits (≤32 MB VmPeak). Memory is not a practical constraint for this pipeline at T≤4; depth scaling matters more than ablation configuration.

## Detailed design

### Experiment 1: Baseline

Two-Phase OFF. T1=800. FC_T1 = B1 (partial-scan reference). FC_T1∪T2∪T4 = pipeline result.

**Result file:** `results/exp1_baseline.csv`
**Status:** 10 common circuits PASS. b11/b13/s9234/s15850/s35932 pending (background sweep, 600s timeout).

---

### Experiment 2: Two-Phase ON

**Change:** `set_two_phase_justification on` at T>1.
**Diagnosis:** If FC exceeds Exp 1 → decoupling propagation from state justification is the recovery mechanism. Expected to run faster than Exp 1 for b11/b13.

**Result file:** `results/exp2_two_phase.csv`
**Status:** 10 common circuits PASS. b11/s35932 excluded (runner crash). b13/s9234/s15850 pending.

**Note:** b11 and s35932 excluded from all experiments — runner produces empty output with no error.

---

### Experiment 3: Uniform T1

**Change:** T1 raised from 800 to 5000 at T=1.
**Diagnosis:** If gain over Exp 1 shrinks → the T1 limit differential is what creates the residual.

**Result file:** `results/exp3_uniform_T1.csv`
**Status:** 10 common circuits PASS. b13/s9234/s15850 pending (background sweep, 600s timeout). b11/s35932 excluded (runner crash).

---

### Experiment 4: Enhanced Backtrace

**Change:** `set_enhanced_backtrace on` (composite-score heuristic: 0.6×SCOAP_controllability + 0.3×depth − 0.1×fanout).
**Diagnosis:** Does composite-score backtrace improve FC or reduce aborts vs SCOAP-only?

**Result file:** `results/exp4_enhanced_backtrace.csv`
**Status:** 10 common circuits PASS. b13/s9234/s15850 pending (background sweep). b11/s35932 excluded (runner crash).

---

### Experiment 5: Static Learning

**Change:** `set_static_learning on` (fanout-implication precomputation — immediate implications only, not full recursive SOCRATES).
**Diagnosis:** Does early conflict detection reduce backtracks or improve FC?

**Result file:** `results/exp5_static_learning.csv`
**Status:** 10 common circuits PASS. b13/s9234/s15850 pending (background sweep). b11/s35932 excluded (runner crash).

---

### B2: Full-Scan Reference Ceiling

Not an ablation experiment. Upper-bound for gap-to-full-scan analysis.

**Result files:** `results/phase_d_fullscan_dataset.csv` (ITC'99), `results/iscas89_fullscan_baseline.csv` (ISCAS'89).

**Status:** Done.

---

## Non-scan ratio sweep (R1)

**Purpose:** Test whether ablation conclusions (Two-Phase dominance; uniform T1 / static learning negligible) hold as timing-driven non-scan exclusion increases.

**Design:**

| Parameter | Value |
|-----------|-------|
| Ratios | 5%, 10%, 15%, 20% (5% steps) |
| Circuits | 10 report-ready (same as Exp 1–5) |
| Experiments per ratio | Exp 1–5 (identical configs to ablation sweep) |
| Total runs | 200 (4 × 5 × 10) |
| Masks | `masks/<circuit>_x{pct}.mask` from OpenSTA slack (`k = max(1, ⌈n·ratio⌉)`) |
| Driver | `scripts/run_ratio_experiment_sweep.py` |
| Timeout | `ATPG_WALL_TIMEOUT=3600` per circuit |

**Output:** `results/ratio_sweep/x{pct}/exp{N}_{name}.csv` (same CSV schema as Exp 1–5).

**Status:** **Done** — 200/200 PASS (`results/ratio_sweep_log.txt`).

### R1 summary (10-circuit averages)

| Ratio | Σ non-scan FFs | Exp 1 FC_T1 | Exp 1 pipeline | Exp 2 pipeline | Exp 2 gain | T=1 gap to B2 | Pipeline gap to B2 (Exp 2) |
|:-----:|:--------------:|:-----------:|:--------------:|:--------------:|:----------:|:-------------:|:--------------------------:|
| 5%    | 33 | 80.91% | 86.35% | 91.81% | 10.89pp | 13.73pp | 2.83pp |
| 10%   | 60 | 71.20% | 77.72% | 90.57% | 19.37pp | 23.44pp | 4.07pp |
| 15%   | 91 | 63.81% | 69.47% | 89.94% | 26.13pp | 30.83pp | 4.70pp |
| 20%   | 118 | 62.02% | 67.84% | 88.59% | 26.57pp | 32.62pp | 6.05pp |

**Takeaways:**

- T=1 gap to B2 grows monotonically with ratio (13.7pp → 32.6pp).
- Baseline pipeline gain stays flat (~5–6pp); Two-Phase gain scales (10.9pp → 26.6pp).
- Exp 3 and Exp 5 are identical to Exp 1 at all ratios (ΔFC = 0.00pp); Exp 4 within ±1.15pp.
- Two-Phase ON: T=4 adds 0 pp at every ratio (same as @10% ablation).
- Circuit sensitivity is topology-dependent: b05/b08 flat across ratios; b04 drops sharply between 10% and 15% T=1 FC.

Full per-circuit tables: `docs/final_report.md` §7.6.
