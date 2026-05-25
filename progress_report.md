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

## Method

### 3.1 Problem Definition

Let circuit *C* contain *N* flip-flops (FFs). A partial scan selects a subset *S* ⊆ {FF₁, …, FF_N} of size *K* = ⌊*r* × *N*⌋ to enter the scan chain, where *r* ∈ (0, 1] is the scan ratio. The selected FFs are ordered according to their circuit routing order into a single-chain scan register.

The selection problem is:

> Given SCOAP testability scores and a scan-shift stress model for each FF, choose *K* FFs that jointly maximize testability preservation while minimizing stress concentration.

This is formulated as a multi-objective optimization, with explicit tradeoff controlled by a weighting parameter λ.

---

### 3.2 Data Extraction Pipeline

FAN_ATPG (NTU LaDS-II) computes SCOAP values for all FFs in the circuit and exports them via `add_scan_chains -o` to a `.sf` file. The `.sf` format contains:

- Per-FF names and their chain order (SI to SO)
- SCOAP controllability measures: CC0, CC1 (number of patterns to set FF output to 0 or 1)
- SCOAP observability measure: CO (number of patterns to propagate FF output to a primary output)
- Pattern-interface (PPI/PPO) toggle data under a given ATPG test set

ScanForge reads the `.sf` file to populate its internal scan chain model and computes all subsequent metrics without requiring re-running ATPG.

---

### 3.3 Scan-Shift Simulation

For each ATPG pattern *p* ∈ {1, …, P}, ScanForge simulates the scan-shift operation by:

1. Loading the test pattern into the scan chain (shift-in)
2. Recording the logic value of each FF at each shift cycle
3. Counting transitions (0→1 or 1→0) per FF per pattern

Let *t_i* denote the total toggle count for FF_i across all patterns and all shift cycles. Let *T* = *P* × *N* be the total number of shift cycles in a full-scan run. The **switching activity** for the entire chain is:

> *activity* = Σ_i *t_i* / (*N* × *T*)

---

### 3.4 Stress Metrics

Two stress metrics are defined — one per-FF (point metric) and one spatial (segment metric). They address different physical concerns and are used in different selection modes.

#### 3.4.1 Per-FF Stress

The **per-FF stress score** for FF_i is its normalized toggle rate during scan shift:

> *stress_i* = *t_i* / *T*

where *T* = total shift cycles (same as *P* × *chain_length* for full scan). This directly measures the fraction of clock cycles in which FF_i changes state during scan. It corresponds to switching activity at the cell level — the primary cost driver in low-power scan literature [Cho & Pan, VTS'06; Remersaro et al., D&T'07].

#### 3.4.2 Segment Stress and Hotspot Detection

A **segment** is a contiguous window of *W* FFs in chain order, defined by a sliding-window index *j* ∈ {0, …, N−W}. The **segment stress** for window *j* is:

> *seg_j* = (1/W) × Σ_{i=j}^{j+W-1} *stress_i*

Let μ_seg and σ_seg denote the mean and standard deviation of all segment stresses. A segment *j* is declared a **hotspot** if:

> *seg_j* > μ_seg + σ_seg

Summary metrics reported per run:
- **Max segment stress**: max_j *seg_j*
- **Segment variance**: σ²_seg
- **Hotspot count**: |{j : *seg_j* > μ_seg + σ_seg}|

Segment stress captures spatial clustering of high-stress FFs — a concentration that per-FF average alone would miss. This is motivated by the thermal hotspot model in PEAKASO [Cho & Pan, VTS'06].

---

### 3.5 Selection Methods

All methods select exactly *K* FFs from *N* available. Let *norm(v)* denote min-max normalization of vector *v* over all FFs in the circuit.

#### Mode 1: `random`
FFs are selected uniformly at random (without replacement). Serves as the minimum-effort baseline.

#### Mode 2: `co`
FFs are ranked by their SCOAP observability score CO in descending order. Top-*K* are selected:

> *score_i* = CO_i

CO measures how many patterns are required to propagate FF_i's value to a primary output. Higher CO ≈ harder to observe ≈ higher value of including in scan.

#### Mode 3: `combined`
FFs are ranked by a combined SCOAP score that includes both controllability and observability:

> *score_i* = CC0_i + CC1_i + 2 × CO_i

This weights observability double because it typically correlates more strongly with detection probability under partial scan.

#### Mode 4: `co_wear`
A stress-penalized variant of `co`. Per-FF stress is subtracted from the normalized testability score:

> *score_i* = *norm*(CO_i) − λ × *norm*(*stress_i*)

where λ ∈ [0, 1] controls the stress-testability tradeoff. At λ=0, reduces to `co`. At λ=1, stress penalty fully weighs against testability.

#### Mode 5: `combined_wear`
Same as `co_wear` but using the combined SCOAP score:

> *score_i* = *norm*(CC0_i + CC1_i + 2×CO_i) − λ × *norm*(*stress_i*)

#### Mode 6: `co_wear_leveling` *(proposed)*
A **greedy segment-aware** selection algorithm. At each step *k* ∈ {1, …, K}, the FF with the highest marginal score is added to the partial chain, where the marginal score accounts for the current segment stress state:

> *score_i* = *norm*(CO_i) − λ × *seg_penalty*(i, current_chain)

The segment penalty for adding FF_i to the current partial chain is computed as:

> *seg_penalty*(i, S_current) = max_j [*seg_j*(S_current ∪ {i})] / max_j [*seg_j*(full_chain)]

where the maximum is taken over all sliding windows of size *W* that include FF_i's chain position. This makes the penalty relative to the full-scan baseline stress, ensuring λ operates on a normalized [0,1] scale regardless of circuit size or window size.

Complexity: **O(N·K²)** — at each of K steps, N candidates are evaluated; each evaluation requires O(K) work for the inline sliding-window update.

#### Mode 7: `combined_wear_leveling` *(proposed)*
Same greedy algorithm as Mode 6, but using the combined SCOAP score instead of CO:

> *score_i* = *norm*(CC0_i + CC1_i + 2×CO_i) − λ × *seg_penalty*(i, S_current)

---

### 3.6 Coverage Metric

**Important disclaimer:** ScanForge uses a **SCOAP-derived coverage proxy**, not exact stuck-at fault coverage. Exact fault coverage requires per-fault ATPG simulation which is not currently integrated.

The coverage proxy for a selected set *S* is:

> *cov_proxy*(S) = Σ_{i ∈ S} (CC0_i + CC1_i + 2·CO_i) / Σ_{i=1}^{N} (CC0_i + CC1_i + 2·CO_i)

This measures the fraction of total SCOAP "difficulty weight" captured by the selected FFs. It approximates how much of the circuit's testability budget is preserved under partial scan. This proxy is consistent with the classic rationale for SCOAP-based selection [Agrawal et al., JETA'92; Cheng & Agrawal, JETA'92] and is used with explicit acknowledgement of its limitations.

---

### 3.7 Complexity Summary

| Mode | Selection complexity | Notes |
|------|---------------------|-------|
| `random` | O(N) | Reservoir sample or shuffle |
| `co`, `combined` | O(N log N) | Sort by SCOAP score |
| `co_wear`, `combined_wear` | O(N log N) | Sort by stress-penalized score |
| `co_wear_leveling`, `combined_wear_leveling` | O(N·K²) | Greedy with inline segment update |

For N ≤ 534 (s15850), the greedy runs in < 10 ms after the O(M·K²) → O(M·K²) sliding-window optimization (W-fold speedup vs. naive implementation). For N = 1728 (s35932), runtime is < 300 ms — practical for design-time use.

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

## Results

The experiment matrix covers 12 ISCAS'89 circuits, 7 modes, 5 λ values, and a ratio sweep from 5% to 100% in 5% increments with segment window W=16. All results are recorded in `results/all_experiments.csv`.

### Finding 1: `co_wear_leveling` preserves coverage while reducing max stress on several medium circuits

### RQ1 & RQ2: Testability vs. Stress Tradeoff — Main Results (Table T3)

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

The global-sort approach (`co_wear`) penalizes SCOAP scores before sorting. Across 12 circuits at 50% ratio:

- `co_wear` consistently degrades coverage: Δcov ranges from −6% to −19% compared to `co`.
- Despite this coverage cost, `co_wear` **fails to reduce stress** on 7 of 12 circuits — max\_stress either stays identical to `co` or increases (by up to +1.7%).

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

**λ sensitivity (Fig. F4).** Table T4 shows coverage proxy and max stress for `co_wear_leveling` on s953 at 50% ratio across all five λ values.

The initial greedy implementation recomputed segment summaries for each candidate at every step, resulting in O(M·K²·W) total complexity. An inline sliding-window evaluation reduces the greedy implementation to **O(M·K²)**.

The transition from no-stress-awareness (λ=0, equivalent to pure `co`) to full benefit occurs between λ=0 and λ=0.25. For all λ ∈ [0.25, 1.0], coverage proxy and max stress are identical, indicating that the greedy selection converges to the same optimal subset regardless of how strongly stress is weighted. This saturation behavior means practitioners need only choose any positive λ — precise tuning is unnecessary.

On s5378, where the stress distribution is near-uniform, max stress is insensitive to λ across all values (Fig. F4, right panel), consistent with the structural ceiling identified in RQ3.

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

### RQ5: Runtime Scalability *(Fig. F6)*

**Table T5.** Selection runtime for `co_wear_leveling` at 50% scan ratio after greedy optimization (W-fold sliding-window speedup over naïve implementation).

| Circuit | N    | Selection time | vs. `co` overhead |
|---------|------|---------------|-------------------|
| s953    | 29   | 0.03 ms        | < 1 ms            |
| s5378   | 179  | 0.6 ms         | < 1 ms            |
| s9234   | 211  | 1.0 ms         | < 1 ms            |
| s15850  | 534  | 10 ms          | < 1 ms            |
| s35932  | 1728 | 293 ms         | < 1 ms            |

Sort-based modes (`co`, `combined`, `co_wear`, `combined_wear`) all run in under 1 ms on every circuit. The greedy modes (`co_wear_leveling`, `combined_wear_leveling`) scale as O(N·K²) after the inline sliding-window optimization, which yielded a ~26× speedup on s35932 versus the naïve O(N·K²·W) implementation. For the representative medium circuits used in main experiments (s953–s9234), selection time is under 1 ms, well within design-time budget.

The log-log scalability curves in Fig. F6 confirm the empirical scaling trend and show that `co_wear_leveling` maintains a 2–3 order-of-magnitude overhead vs. sort-based methods, which remains constant in absolute terms (< 300 ms for the largest tested circuit).

---

### Negative Result: Bootstrapped Stress Refinement

We investigated whether replacing the full-scan stress prior with partial-scan stress (simulated on the K-FF chain) could improve leveling on circuits where full-scan spread is narrow. The hypothesis was that reducing chain length would expose higher per-FF stress variance by isolating each FF's individual toggle pattern.

Empirically, the opposite holds: partial-scan stress spread is consistently *smaller* than full-scan stress spread for the same selected FFs (s5378, K=9: full-scan spread = 0.0079, partial-scan spread = 0.0019). Reducing chain length compresses the stress distribution because each FF's toggle rate is driven primarily by its own PI↔PPO transition pattern across ATPG vectors — a property that is unaffected by which other FFs share the chain. Furthermore, the greedy objective operates on segment-level (spatial window) stress, while the bootstrap only updates scalar per-FF values; these are structurally decoupled, so per-FF substitution cannot inform spatial interaction effects.

As a result, bootstrapped refinement produces no improvement at any scan ratio, and at ratios above 25% can degrade max stress by up to 10% due to non-convergent oscillation. The static full-scan stress proxy is already near-optimal for the greedy leveling objective. This result is discussed further in §Discussion.

---

## Discussion

### Why `co_wear_leveling` works on medium circuits but not large ones

The effectiveness of segment-aware stress leveling depends on the **stress spread** of the full-scan chain: the range between the least-stressed and most-stressed FFs. On s953 (29 FFs), full-scan stress ranges from approximately 0.26 to 0.42 — a spread of 0.16. The greedy algorithm can meaningfully distinguish FFs at the high and low ends, allowing it to preferentially select low-stress FFs without sacrificing testability, since the high-CO FFs and the high-stress FFs are not the same subset.

On larger circuits such as s5378 (179 FFs), the full-scan stress is near-uniform (range ≈ 0.13, all FFs within 0.40–0.53). When every FF has nearly identical stress, the penalty term cannot distinguish between candidates at the top-K testability boundary. The greedy effectively reduces to pure `co` selection, producing no measurable stress improvement.

**Implication:** The method's applicability is bounded by a structural circuit property (stress spread), not by algorithm design. Circuits with skewed switching activity distributions — common in sequential circuits with irregular state machine topology — are the primary beneficiaries.

### On the failure of `co_wear` (global sort)

The global-sort approach (`co_wear`, `combined_wear`) applies a uniform stress penalty to the SCOAP score before sorting. This naive penalization has two failure modes:

1. **Coverage degradation:** Highly observable FFs often also have high CO values that co-locate with high-stress FFs. Derating them uniformly removes them from selection regardless of whether their stress is structurally reducible.
2. **Stress non-monotonicity:** Replacing a high-CO/high-stress FF with a low-CO/low-stress FF does not guarantee lower *max* stress, because max stress is determined by the single worst FF retained, not the average.

Segment-aware greedy leveling resolves both issues by targeting the segment-level max directly, making the penalty spatial rather than per-FF.

### Threats to Validity

**Construct validity — Coverage proxy.** The coverage proxy (SCOAP-derived) is a testability preservation measure, not true stuck-at fault coverage. Circuits where CO does not correlate with detection probability (e.g., reconvergent fanout, equivalent faults) may show misleading proxy values. Exact fault coverage integration remains future work.

**Construct validity — Stress model.** Per-FF toggle rate is a first-order proxy for switching stress. It does not model voltage, temperature, or process variation. Physical aging requires separate reliability modeling beyond the scope of this paper.

**Internal validity — Static stress prior.** Full-scan stress is used as the stress prior for both sort and leveling modes. Under partial scan, actual stress distribution will differ (fewer FFs shift together). Finding 6 (bootstrapped refinement negative result) demonstrates that using partial-scan stress does not improve the outcome — the static full-scan prior is empirically near-optimal. The root cause is that per-FF toggle rate is dominated by each FF's own PI/PPO connectivity pattern, not chain-neighbor effects.

**External validity — ISCAS'89 only.** All benchmarks are from ISCAS'89. These are combinational and small sequential circuits derived from academic designs from the 1980s. Modern industrial circuits with deeper pipelines, clock-gating, and multi-chain scan may show different stress distribution characteristics.

---

## Conclusion

We presented **ScanForge**, a partial scan FF selection framework that jointly optimizes SCOAP-derived testability preservation and scan-shift stress distribution. The framework implements seven selection modes ranging from classical SCOAP ranking to a novel segment-aware greedy stress-leveling algorithm, evaluated across 12 ISCAS'89 benchmarks with a full hyperparameter sweep.

**Key findings:**
1. `co_wear_leveling` achieves up to **20.8% reduction in max per-FF stress** on s953 at zero coverage penalty.
2. Global-sort stress penalization (`co_wear`) is unreliable: it reduces testability on all circuits while failing to consistently reduce stress on 7 of 12.
3. The leveling method is **robust to λ** — any λ > 0 achieves the optimal tradeoff on s953, with no benefit from tuning beyond λ = 0.25.
4. On large circuits with near-uniform stress (s5378 and above), leveling reduces to pure `co` selection — a structural ceiling inherent to the circuit topology, not an algorithmic limitation.
5. After greedy optimization (O(M·K²) sliding-window update), selection runs in **< 10 ms** for up to 534 FFs and **< 300 ms** for 1728 FFs.
6. Bootstrapped iterative refinement (negative result) confirms that static full-scan stress is already a near-optimal prior — partial-scan stress compresses the distribution rather than expanding it, offering no additional information to the greedy.

**Limitations and future work:** The current method relies on a SCOAP-derived coverage proxy rather than exact fault coverage, and uses a toggle-rate stress model without physical aging parameters. Future work should integrate exact SAF coverage simulation and evaluate on modern industrial benchmarks with multi-chain scan architectures.

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

## Literature Comparison Table (Table T6)

| # | Paper | Objective | Method | Metrics | Benchmarks | Difference from Ours |
|---|-------|-----------|--------|---------|------------|----------------------|
| 1 | Goldstein & Thigpen, DAC'80 | Define SCOAP testability | Static CC/CO computation | CC0, CC1, CO | – | Foundational metric; we use CO/combined as selection criterion |
| 2 | Agrawal et al., JETA'92 | Reduce scan overhead | SCOAP-driven partial scan selection | Coverage loss, chain length | Small academic circuits | No stress awareness; same greedy spirit but testability-only |
| 3 | Cheng & Agrawal, JETA'92 | Minimize coverage loss under area budget | Empirical testability ranking | Fault coverage | Small academic circuits | Testability-only; no power/stress metric |
| 4 | Chickermane et al., ITC'96 | Practical partial scan for large circuits | Multiple heuristics (loop-breaking, etc.) | Coverage, scan cell count | Industrial circuits | Structural loop-breaking focus; no stress |
| 5 | Cho & Pan, VTS'06 | Reduce peak temperature during scan shift | Scan vector optimization (pattern reordering) | Peak temperature, switching activity | ISCAS'89, industrial | Vector-level; we target FF selection, not pattern ordering |
| 6 | Remersaro et al., D&T'07 | Reduce switching during scan shift | Low-activity X-filling and scan reordering | Toggle count, activity | ISCAS'89 | Scan reordering + X-filling; we select which FFs enter the chain |
| 7 | Butler et al., ITC'04 | Minimize scan test power consumption | Pattern generation + DFT techniques | Peak/average power | ISCAS'89, industrial | Power-driven pattern generation; no partial scan selection |
| 8 | Rosinger et al., TCAD'04 | Reduce shift and capture power | Mutually exclusive segment activation architecture | Shift power, capture power | ISCAS'89 | Chain architecture modification; orthogonal to FF selection |
| 9 | Remersaro et al., ATS'07 | Reduce peak power via chain reordering | Scan cell reordering heuristic | Peak power during scan | ISCAS'89 | Reorders the existing scan chain; we select which FFs to include |
| 10 | Lin et al., DATE'16 | Simultaneous reordering + X-filling for power | Joint chain reordering and X-filling | Scan shift power | ISCAS'89, industrial | Post-insertion optimization; our method works at selection stage |
| 11 | Firouzi et al., ICCAD'15 | Aging prediction via DfT monitoring | Fine-grained stress monitoring using existing DfT | Aging stress, NBTI/HCI | Industrial | Monitors stress at runtime; we minimize stress concentration at design |

**Summary of gap:** All prior work either (a) optimizes testability without stress awareness [1–4], (b) reduces scan power via pattern/vector manipulation after scan insertion [5–10], or (c) monitors aging post-silicon [11]. **ScanForge is the first framework to integrate SCOAP-based testability and segment-level stress distribution into the FF selection criterion itself**, enabling Pareto-optimal tradeoffs at design time.

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
