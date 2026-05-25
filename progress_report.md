# Progress Report
## Course: EEE5001 VLSI Testing
## Date: 2026-05-26

---

## Group Information

| Item | Info |
|------|------|
| Group Number | Group 5 |
| Topic | 3. Self-Defined — Stress-Aware Partial Scan Selection |
| Members | 丁睿濂, 駱彥竹, 黃思維 |

---

## Topic Description

**Title:** ScanForge: A Stress-Aware Partial Scan Selection Framework

**One-sentence contribution:**
> We propose a partial scan FF selection framework that jointly optimizes SCOAP-derived testability and scan-shift stress distribution, demonstrating that segment-aware greedy selection achieves better stress-testability tradeoffs than global stress-penalized ranking on ISCAS'89 benchmarks.

**Problem:**
Given a circuit with N flip-flops, select K = ⌊r × N⌋ FFs for partial scan (scan ratio r ∈ (0,1]) such that:
- Testability (SCOAP-derived coverage proxy) is preserved
- Per-FF switching stress during scan shift is reduced
- Spatial stress concentration (segment hotspots) along the chain is minimized

**Why this matters:**
During scan shift, switching activity can reach 50% toggle rate — far above the 10–30% seen in functional operation. Concentrated switching on a subset of FFs creates local hotspots and uneven stress distribution. Standard SCOAP-based partial scan selection ignores this problem entirely.

---

## Proposed Technique

### Selection modes implemented

| Mode | Formula | Style |
|------|---------|-------|
| `random` | random shuffle | baseline |
| `co` | CO (observability) | sort |
| `combined` | CC0 + CC1 + 2×CO | sort |
| `co_wear` | norm(CO) − λ·norm(stress) | sort |
| `combined_wear` | norm(CC0+CC1+2CO) − λ·norm(stress) | sort |
| `co_wear_leveling` | greedy: norm(CO) − λ·(max_seg_stress / max_full_stress) | greedy |
| `combined_wear_leveling` | same with combined SCOAP | greedy |

### Stress metrics (finalized)

**Per-FF stress** (used in global-sort wear modes):
```
stress_score_i = toggle_rate_i = toggle_count_i / total_shift_cycles
```
Directly corresponds to per-cell switching activity — standard metric in low-power scan literature.

**Segment stress** (used in greedy wear-leveling modes):
```
segment_stress_j = mean(stress_score_i  for FF i in sliding window j)
hotspot: segment_stress_j > mean_all_segments + 1·stddev
```
Captures spatial clustering of high-stress FFs. Motivated by thermal hotspot analysis (PEAKASO, VTS 2006).

### Coverage metric

SCOAP-derived coverage proxy (not exact fault coverage):
```
coverage_proxy = sum(CC0 + CC1 + 2·CO for selected FFs)
               / sum(CC0 + CC1 + 2·CO for all FFs)
```
Explicit disclaimer: this is a testability preservation proxy, not exact stuck-at fault coverage.

---

## Current Implementation Status

| Component | Status |
|-----------|--------|
| `.sf` file parser | ✅ Complete |
| Full-scan simulation | ✅ Complete |
| 7 selection modes | ✅ Complete |
| Per-FF stress CSV export | ✅ Complete |
| Segment stress profiling + hotspot | ✅ Complete |
| Sweep mode + Pareto tags | ✅ Complete |
| Runtime logging (selection + simulation) | ✅ Complete |
| Coverage proxy | ✅ Complete |
| Multi-mode sweep script (`scripts/run_experiment.sh`) | ✅ Complete |
| Greedy O(M·K²·W) → O(M·K²) optimization | ✅ Complete — ~26× speedup on s35932 |
| Full experiment matrix (12 circuits × 7 modes × λ sweep) | ✅ Complete — 5520 data rows |
| Publication-quality figures | 🔲 Pending |
| Literature comparison table | 🔲 Pending |
| Exact fault coverage | 🔲 Out of scope (proxy used with disclaimer) |

**Backend:** Built on FAN_ATPG (NTU LaDS-II) for SCOAP export via `.sf` format.
**Benchmarks:** ISCAS'89 (s27–s38584, 12 circuits, 3–1728 FFs).

---

## Preliminary Experimental Results

Experiment matrix completed: 12 ISCAS'89 circuits × 7 modes × 5 λ values × segment window W=16,
using fine-grained ratio sweep (5%–100% in 5% steps). All results in `results/all_experiments.csv`.

### Finding 1: `co_wear_leveling` Pareto-dominates `co` on medium circuits

At 50% scan ratio, λ=0.5:

| Circuit | FFs | `co` CovProxy | `co_wear_leveling` CovProxy | `co` MaxStress | `co_wear_leveling` MaxStress |
|---------|-----|--------------|----------------------------|---------------|------------------------------|
| s510    | 6   | same         | same (0 loss)              | —             | **−2.3%** |
| s953    | 29  | 0.8667       | 0.8667 (0 loss)            | 0.4607        | **0.3648 (−20.8%)** |
| s1238   | 18  | same         | same (0 loss)              | —             | **−2.0%** |

`co_wear_leveling` achieves the same SCOAP-derived coverage as the classical `co` baseline while
reducing per-FF max switching stress by up to **20.8%** — without any coverage penalty.

### Finding 2: `co_wear` (global sort) is unstable on large circuits

`co_wear` consistently reduces coverage (Δcov = −6% to −19%) but stress reduction is
**unreliable** — on 7 of 12 circuits, max_stress actually increases after applying the penalty.
This suggests global-sort stress penalization does not generalize across circuit sizes.

### Finding 3: λ robustness on s953

For `co_wear_leveling` on s953 at 50%:

| λ | CovProxy | MaxStress |
|---|---------|-----------|
| 0.00 | 0.8667 | 0.4607 (= pure `co`) |
| 0.25 | 0.8667 | **0.3648** |
| 0.50 | 0.8667 | 0.3648 |
| 0.75 | 0.8667 | 0.3648 |
| 1.00 | 0.8667 | 0.3648 |

Any λ > 0 triggers the optimal selection. The method is **insensitive to λ** in [0.25, 1.0],
indicating robustness to hyperparameter choice.

### Finding 4: Leveling effect diminishes on large circuits (> 100 FFs)

For s5378 (179 FFs), s9234 (211 FFs), s15850 (534 FFs) and above, `co_wear_leveling` selects
identical FFs as pure `co`. The segment-level greedy objective does not change the selection
when the number of FFs is large relative to the segment window. This is an identified limitation.

### Finding 5: Runtime scalability (after greedy optimization)

The original greedy called `summarizeSegmentStress` (O(chain×W)) per candidate per step and
allocated a sorted temp vector per candidate, giving O(M·K²·W) total.

We replaced this with an inline O(chain) sliding-window sum using a virtual-insert lambda,
eliminating all per-candidate allocations. New complexity: **O(M·K²)** — a W× improvement.

Selection time for `co_wear_leveling` at 50% ratio (before → after):

| Circuit | FFs | Before | After | Speedup |
|---------|-----|--------|-------|---------|
| s953    | 29  | 0.13 ms | 0.03 ms | ~4× |
| s5378   | 179 | 7.8 ms | 0.6 ms | ~13× |
| s9234   | 211 | 12.9 ms | 1.0 ms | ~13× |
| s15850  | 534 | 231 ms | 10 ms | ~23× |
| s35932  | 1728 | 7,684 ms | 293 ms | **~26×** |

`co` and `co_wear` remain < 1 ms on all circuits. The greedy modes are now practical for
circuits up to ~500 FFs (<10 ms) and usable up to 1728 FFs (<300 ms).

---

## Job Partition

| Member | Responsibilities |
|--------|----------------|
| 丁睿濂 | 主題發想、主要程式碼撰寫（ScanForge engine、selection modes、FAN_ATPG integration） |
| 駱彥竹 | 方法探索、主題討論（metric 定義、演算法設計、相關文獻調查） |
| 黃思維 | Bug 修復、測試、報告撰寫 |

---

## Schedule

| Date | Milestone |
|------|-----------|
| 2026-05-26 | Progress report submission |
| 2026-05-27–05-31 | ~~Run full experiment matrix~~ **DONE** — Generate figures from CSV |
| 2026-06-01–06-07 | Generate figures; write problem description + method sections |
| 2026-06-08–06-10 | Write results + discussion; build literature comparison table |
| 2026-06-11–06-14 | Finalize report; prepare PPT |
| 2026-06-16 | **Presentation** |
| 2026-06-17 noon | **Final report + code submission** |
| 2026-06-17 13:30–17:30 | **Demo** |

---

## References

1. M. Cho and D. Z. Pan, "PEAKASO: Peak-Temperature Aware Scan-Vector Optimization," *Proc. IEEE VLSI Test Symposium (VTS)*, pp. 231–236, 2006.

2. V. D. Agrawal, K.-T. Cheng, D. D. Johnson, and T. Lin, "Testability-based partial scan analysis," *Journal of Electronic Testing: Theory and Applications (JETA)*, vol. 3, pp. 319–334, 1992.

3. K.-T. Cheng and V. D. Agrawal, "Partial scan flip-flop selection by use of empirical testability," *Journal of Electronic Testing: Theory and Applications (JETA)*, vol. 3, pp. 309–318, 1992.

4. S. Remersaro et al., "Scan Cell Reordering for Peak Power Reduction during Scan Test Cycles," *Proc. IEEE Asian Test Symposium (ATS)*, 2007.

5. X. Lin et al., "Scan Chain Reordering-Aware X-Filling and Stitching for Scan Shift Power Reduction," *Proc. Design, Automation and Test in Europe (DATE)*, 2016.

---

## AI Usage Declaration

This project made use of the following AI tools:

**Claude (Anthropic)**
- Code implementation and debugging (C++ source)
- Literature search and summarization
- Metric definition review and comparison with published work
- Report and specification drafting

**GitHub Copilot**
- Code completion and suggestion during development

**DeepSeek V4 Pro**
- Code generation and algorithm discussion

**Cursor**
- AI-assisted code editing and refactoring within the IDE

All key design decisions, algorithm logic, and experimental analysis were reviewed and confirmed by team members. AI tools were used as productivity aids; all claims in this report are understood and verified by the team.

---

## Appendix: Planned Experiment Matrix

### Circuits
s27, s208, s510, s953, s1196, s1238, s5378, s9234, s15850, s35932, s38417, s38584

### Modes (all 7)
`random`, `co`, `combined`, `co_wear`, `combined_wear`, `co_wear_leveling`, `combined_wear_leveling`

### Scan ratios
25%, 50%, 75%, 100%

### Hyperparameters
- λ ∈ {0, 0.25, 0.5, 0.75, 1.0}
- segment window ∈ {8, 16}

### Metrics reported per (circuit, mode, ratio)
coverage_proxy, coverage_loss, toggles, switching_activity,
max_stress, stress_variance, stress_imbalance,
max_segment_stress, segment_variance, hotspot_count,
selection_time_ms, simulation_time_ms
