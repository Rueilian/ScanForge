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
> This work presents a partial-scan FF selection framework that jointly optimizes SCOAP-derived testability and scan-shift stress distribution, and shows that segment-aware greedy selection can improve the stress-testability tradeoff relative to global stress-penalized ranking on selected ISCAS'89 benchmarks.

**Problem:**
Given a circuit with N flip-flops, select K ≈ r × N FFs for partial scan, where the scan ratio r ∈ (0,1] and K is computed by rounding rN with a minimum of 1, such that:
- Testability (SCOAP-derived coverage proxy) is preserved
- Per-FF switching stress during scan shift is reduced
- Spatial stress concentration (segment hotspots) along the chain is minimized

**Why this matters:**
During scan shift, switching activity is substantially higher than under normal functional operation and can create local hotspots and uneven stress distribution [1][4][5]. Standard SCOAP-based partial scan selection does not optimize for this stress concentration.

---

## Proposed Technique

### Selection modes implemented

The testability-driven baselines follow prior partial-scan literature [2][3]. The modes `co_wear`, `combined_wear`, `co_wear_leveling`, and `combined_wear_leveling` are stress-aware variants that augment SCOAP-based selection with switching-stress information.

| Mode | Formula | Style |
|------|---------|-------|
| `random` | random shuffle | baseline |
| `co` | CO (observability) | ranking |
| `combined` | CC0 + CC1 + 2×CO | ranking |
| `co_wear` | norm(CO) − λ·norm(stress) | ranking |
| `combined_wear` | norm(CC0+CC1+2CO) − λ·norm(stress) | ranking |
| `co_wear_leveling` | greedy: norm(CO) − λ·(max_seg_stress / max_full_stress) | greedy selection |
| `combined_wear_leveling` | greedy: norm(CC0+CC1+2CO) − λ·(max_seg_stress / max_full_stress) | greedy selection |

### Stress metrics

**Per-FF stress** (used in global ranking stress-aware modes):
```
stress_score_i = toggle_rate_i = toggle_count_i / total_shift_cycles
```
This metric reflects per-cell switching activity, a standard concern in low-power scan literature [1][4][5].

**Segment stress** (used in greedy stress-leveling modes):
```
segment_stress_j = mean(stress_score_i  for FF i in sliding window j)
hotspot: segment_stress_j > mean_all_segments + 1·stddev
```
This metric captures the spatial clustering of high-stress FFs and is consistent with thermal-hotspot analysis in PEAKASO [1].

### Coverage metric

SCOAP-derived coverage proxy:
```
coverage_proxy = sum(CC0 + CC1 + 2·CO for selected FFs)
               / sum(CC0 + CC1 + 2·CO for all FFs)
```
This metric is used as a testability-preservation proxy rather than as an exact stuck-at fault coverage measure.

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
| Multi-mode sweep script | ✅ Complete |
| Greedy O(M·K²·W) → O(M·K²) optimization | ✅ Complete |
| Full experiment matrix (12 circuits × 7 modes × λ sweep) | ✅ Complete |
| Literature comparison table | 🔲 In preparation |
| Exact fault coverage | 🔲 Not yet integrated |
| Post-selection ATPG / fault simulation | 🔲 Not yet integrated |
| Final comparison tables | 🔲 In preparation |
| Figure-generation and reproducibility flow | 🔲 In preparation |

**Backend:** Implemented on top of FAN_ATPG (NTU LaDS-II) for SCOAP export via `.sf` format.
**Benchmarks:** ISCAS'89 (s27–s38584, 12 circuits, 3–1728 FFs).

---

## Preliminary Experimental Results

The experiment matrix covers 12 ISCAS'89 circuits, 7 modes, 5 λ values, and a ratio sweep from 5% to 100% in 5% increments with segment window W=16. All results are recorded in `results/all_experiments.csv`.

### Finding 1: `co_wear_leveling` preserves coverage while reducing max stress on several medium circuits

At 50% scan ratio, λ=0.5:

| Circuit | FFs | `co` CovProxy | `co_wear_leveling` CovProxy | `co` MaxStress | `co_wear_leveling` MaxStress |
|---------|-----|--------------|----------------------------|---------------|------------------------------|
| s510    | 6   | 0.6000       | 0.6000                     | 0.5085        | **0.4859 (−4.4%)** |
| s953    | 29  | 0.8667       | 0.8667                     | 0.4607        | **0.3648 (−20.8%)** |
| s1238   | 18  | 0.8258       | 0.8258                     | 0.5808        | **0.5609 (−3.4%)** |

On these medium circuits, `co_wear_leveling` matches the SCOAP-derived coverage of the `co` baseline while reducing per-FF maximum switching stress by **3.4%–20.8%**.

### Finding 2: `co_wear` shows inconsistent tradeoffs across circuits

At 50% scan ratio with λ=0.5, `co_wear` reduces coverage on **11 of 12** circuits and increases `max_stress` on **6 of 12** circuits. Representative examples are listed below.

| Circuit | `co` CovProxy | `co_wear` CovProxy | `co` MaxStress | `co_wear` MaxStress | Interpretation |
|---------|---------------|--------------------|----------------|---------------------|----------------|
| s208    | 0.7500 | 0.6842 | 0.2500 | 0.3362 | degradation in both coverage and stress |
| s1196   | 0.8300 | 0.7937 | 0.5216 | 0.5315 | degradation in both coverage and stress |
| s9234   | 0.9087 | 0.8517 | 0.4993 | 0.5023 | lower coverage with slightly higher stress |
| s5378   | 0.7950 | 0.6014 | 0.5166 | 0.4742 | lower stress, but with substantial coverage loss |

These results suggest that simple global stress penalization does not consistently preserve a good stress-testability tradeoff across circuit sizes.

### Finding 3: Sensitivity to λ on s953

For `co_wear_leveling` on s953 at 50%:

| λ | CovProxy | MaxStress |
|---|---------|-----------|
| 0.00 | 0.8667 | 0.4607 (= pure `co`) |
| 0.25 | 0.8667 | **0.3648** |
| 0.50 | 0.8667 | 0.3648 |
| 0.75 | 0.8667 | 0.3648 |
| 1.00 | 0.8667 | 0.3648 |

Any λ > 0 yields the same selected set. The method is therefore **insensitive to λ** in [0.25, 1.0], indicating robustness to hyperparameter choice.

### Finding 4: Leveling effect diminishes on large circuits as stress spread narrows

For larger circuits such as s5378 (179 FFs), `co_wear_leveling` often selects FF sets that are identical or nearly identical to those selected by pure `co`. At 50% scan ratio with λ=0.5, s5378 shows nearly identical outcomes for the two methods:

| Circuit | Mode | CovProxy | MaxStress |
|---------|------|----------|-----------|
| s5378 | `co` | 0.7950 | 0.5166 |
| s5378 | `co_wear_leveling` | 0.7950 | 0.5170 |
| s953 | `co` | 0.8667 | 0.4607 |
| s953 | `co_wear_leveling` | 0.8667 | 0.3648 |

These results suggest that the effectiveness of stress-leveling depends on the circuit's intrinsic stress spread. When stress values are tightly clustered, there may be few genuinely low-stress alternatives at the top-K boundary, so the stress penalty has little room to change the selected set. We treat this as a limitation of the current benchmark regime rather than proof of a universal ceiling.

### Finding 5: Runtime scalability (after greedy optimization)

The initial greedy implementation recomputed segment summaries for each candidate at every step, resulting in O(M·K²·W) total complexity. An inline sliding-window evaluation reduces the greedy implementation to **O(M·K²)**.

Selection time for `co_wear_leveling` at 50% ratio (before → after):

| Circuit | FFs | Before | After | Speedup |
|---------|-----|--------|-------|---------|
| s953    | 29  | 0.13 ms | 0.03 ms | ~4× |
| s5378   | 179 | 7.8 ms | 0.6 ms | ~13× |
| s9234   | 211 | 12.9 ms | 1.0 ms | ~13× |
| s15850  | 534 | 231 ms | 10 ms | ~23× |
| s35932  | 1728 | 7,684 ms | 293 ms | **~26×** |

`co` and `co_wear` remain below 1 ms on all evaluated circuits. The greedy modes require less than 10 ms up to approximately 500 FFs and remain below 300 ms at 1728 FFs.

---

## Remaining Work and Future Directions

Although the current implementation already supports stress-aware partial-scan selection, stress profiling, and full benchmark sweeps, several items remain necessary before the final submission.

1. **Exact fault-coverage evaluation:** The current study uses a SCOAP-based coverage proxy. The most important next step is to integrate exact stuck-at fault coverage for each partial-scan configuration so that testability claims can be validated with ATPG or fault simulation results.

2. **Post-selection ATPG regeneration:** After a partial-scan set is chosen, the flow should regenerate or reevaluate test patterns under that specific scan configuration. This would allow a direct comparison between proxy-based ranking and true fault-detection effectiveness.

3. **Expanded experimental validation:** The present report emphasizes ISCAS'89 results and representative cases. Future experiments should further analyze sensitivity across scan ratios, λ values, and segment-window settings, and should verify whether the same trends hold consistently on larger and more diverse circuits.

4. **Comparison against stronger baselines:** The current comparison focuses on random selection and SCOAP-derived baselines. The final report should include a tighter comparison with literature-motivated baselines and should clarify where the proposed segment-aware strategy provides measurable benefit.

5. **Discussion of limitations and applicability:** The current results already suggest that the benefit of stress-leveling depends on circuit characteristics such as stress spread. The final version should make these boundary conditions more explicit and explain when the proposed method is expected to help most.

6. **Final artifact refinement:** The remaining work also includes refining figures and tables, strengthening the literature comparison, improving the final discussion section, and packaging the code and scripts into a more reproducible submission flow.

---

## Job Partition

| Member | Responsibilities |
|--------|----------------|
| 丁睿濂 | Topic definition; main implementation (ScanForge engine, selection modes, FAN_ATPG integration) |
| 駱彥竹 | Method exploration and discussion (metric definition, algorithm design, literature review) |
| 黃思維 | Bug fixing, testing, and report writing |

---

## Schedule

| Date | Milestone |
|------|-----------|
| 2026-05-26 | Progress report submission |
| 2026-05-27–05-31 | Full experiment matrix completed; refine selected figures and captions |
| 2026-06-01–06-07 | Write problem description + method sections |
| 2026-06-08–06-10 | Write results + discussion; build literature comparison table |
| 2026-06-11–06-14 | Finalize report; prepare PPT |
| 2026-06-16 | **Presentation** |
| 2026-06-17 noon | **Final report + code submission** |
| 2026-06-17 13:30–17:30 | **Demo** |

---

## References

[1] M. Cho and D. Z. Pan, "PEAKASO: Peak-Temperature Aware Scan-Vector Optimization," *Proc. IEEE VLSI Test Symposium (VTS)*, pp. 231–236, 2006.

[2] V. D. Agrawal, K.-T. Cheng, D. D. Johnson, and T. Lin, "Testability-based partial scan analysis," *Journal of Electronic Testing: Theory and Applications (JETA)*, vol. 3, pp. 319–334, 1992.

[3] K.-T. Cheng and V. D. Agrawal, "Partial scan flip-flop selection by use of empirical testability," *Journal of Electronic Testing: Theory and Applications (JETA)*, vol. 3, pp. 309–318, 1992.

[4] S. Remersaro et al., "Scan Cell Reordering for Peak Power Reduction during Scan Test Cycles," *Proc. IEEE Asian Test Symposium (ATS)*, 2007.

[5] X. Lin et al., "Scan Chain Reordering-Aware X-Filling and Stitching for Scan Shift Power Reduction," *Proc. Design, Automation and Test in Europe (DATE)*, 2016.

---

## AI Usage Declaration

The project used the following AI tools:

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

All key design decisions, algorithm logic, and experimental analysis were reviewed and confirmed by the team. AI tools served only as auxiliary tools, and all claims reported here were examined and validated by the authors.

---

## Appendix: Executed Experiment Matrix

### Circuits
s27, s208, s510, s953, s1196, s1238, s5378, s9234, s15850, s35932, s38417, s38584

### Modes (all 7)
`random`, `co`, `combined`, `co_wear`, `combined_wear`, `co_wear_leveling`, `combined_wear_leveling`

### Scan ratios
5%, 10%, 15%, ..., 100% (fine-grained 5% sweep)

### Hyperparameters
- λ ∈ {0, 0.25, 0.5, 0.75, 1.0}
- segment window = 16

### Metrics reported per (circuit, mode, ratio, λ)
coverage_proxy, coverage_loss, toggles, switching_activity,
max_stress, stress_variance, stress_imbalance,
max_segment_stress, segment_variance, hotspot_count,
selection_time_ms, simulation_time_ms
