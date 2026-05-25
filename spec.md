# ScanForge Paper Spec

## 1. Scope

This document defines the target scope for turning **ScanForge** into a publishable paper project.

**Paper focus:** partial scan chain selection  
**Primary angle:** stress-aware partial scan selection with testability preservation  

The paper should not be written as a general "DFT toolbox" paper. It should be written as a focused method paper on **partial scan selection under testability-stress tradeoffs**.

---

## 2. Target Paper Claim

**Core claim**

> A stress-aware partial scan selection framework can preserve SCOAP-derived testability while reducing scan-shift stress on selected ISCAS'89 benchmarks, and segment-aware greedy selection can improve the stress-testability tradeoff over global stress-penalized ranking in representative cases.

**Important framing**

- Exact fault coverage is preferred when available.
- If exact fault coverage is not yet available, the paper must explicitly state that the current method uses a **SCOAP-derived coverage proxy**.
- Do **not** oversell the proxy as true fault coverage.

---

## 3. Why Stress Reduction Matters

Partial scan selection should not be evaluated only by testability preservation. During scan shifting, some flip-flops or local chain regions can experience disproportionately high switching activity. Even when overall testability remains good, concentrated scan activity can create undesirable operating conditions.

### Why this matters

1. High scan-shift activity increases unnecessary switching burden during test.
2. Uneven activity creates local hotspots, not just global average cost.
3. Repeated concentration of scan activity on the same cells or segments may increase long-term reliability risk.
4. Therefore, a useful partial-scan method should preserve testability **while also reducing or redistributing stress**.

### Terminology rule

- **Stress** = directly measured from scan-shift simulation
- **Wear** = long-term consequence inferred from stress history

Accordingly, the preferred framing is:

> We optimize stress-related metrics and interpret them as proxies for wear risk.

ScanForge reduces **stress**, **stress imbalance**, or **hotspot tendency** during scan shifting. It should not claim direct measurement of physical aging or lifetime unless additional reliability modeling is added.

---

## 4. Research Questions

### RQ1. Testability preservation
How well do different partial-scan selection strategies preserve testability as scan ratio decreases?

### RQ2. Stress reduction
How much scan-shift stress, stress variance, and segment hotspot behavior can be reduced by stress-aware selection?

### RQ3. Global-sort vs greedy segment-aware selection
When does segment-aware greedy stress-leveling outperform simple per-FF stress-aware ranking, and when does it not?

### RQ4. Robustness to hyperparameters
How sensitive are the conclusions to `lambda`, scan ratio, and segment window size?

### RQ5. Scalability
How does runtime scale with flip-flop count, pattern count, and selection mode?

---

## 5. Proposed Contributions

The paper should claim only contributions that are actually supported by implementation and experiments.

### Candidate contribution list

1. A standalone partial-scan analysis framework built on top of FAN_ATPG-exported scan data.
2. A unified selection framework covering:
   - SCOAP-CO
   - SCOAP-Combined
   - Random baseline
   - Per-FF stress-aware ranking
   - Segment-aware greedy stress-leveling
3. A scan-shift stress model with:
   - per-FF stress metrics
   - segment-level stress profiling
   - hotspot counting
4. A benchmark-driven comparison across ISCAS'89 circuits.
5. A reproducible evaluation flow using command-line scripts and CSV outputs.

### Contributions that need stronger evidence before claiming in the paper

1. "Improves fault coverage" if only proxy results are available.
2. "Reduces power" unless power is explicitly defined and validated beyond switching/stress metrics.
3. "Outperforms prior art" before implementing or reproducing meaningful baselines from literature.

---

## 6. Current Implemented Feature Inventory

This section is the implementation-side source of truth for the paper.

| Area | Current status | Notes for paper |
|---|---|---|
| `.sf` parser | Implemented | Reads FF names, SCOAP metrics, PPI/PPO patterns |
| Full-scan simulation | Implemented | Produces toggles and switching activity |
| Per-FF stress metrics | Implemented | `stress_score = toggle_rate`; CSV export supported |
| Segment stress profiling | Implemented | Sliding-window metrics and hotspot count |
| Partial scan selection: `co` | Implemented | Main classical baseline |
| Partial scan selection: `combined` | Implemented | Alternative SCOAP-based baseline |
| Partial scan selection: `random` | Implemented | Required baseline |
| Stress-aware ranking: `co_wear`, `combined_wear` | Implemented | Global sort with stress penalty |
| Stress-leveling: `co_wear_leveling`, `combined_wear_leveling` | Implemented | Greedy segment-aware selection |
| Sweep mode | Implemented | Ratio sweeps and CSV output |
| Coverage proxy | Implemented | SCOAP-derived proxy, not exact fault coverage |
| Pareto tags in sweep CSV | Implemented | Useful for paper figures |
| Runtime logging | Implemented | `selection_time_ms` and `simulation_time_ms` in sweep CSV and `--partial` stdout |
| Exact fault coverage for partial scan | Not implemented | Important publication gap; use proxy with explicit disclaimer |
| Literature-backed baseline reproduction | Not yet done | Needed for stronger submission |

For the progress report version, the implementation-status section should explicitly distinguish:
1. completed components already available in the codebase, and
2. remaining implementation work that is still under development or not yet integrated.

Prefer expressing both categories in a single status table when possible, so readers can see completed and unfinished implementation items in one unified view.

When an item is not yet part of the implemented evaluation flow, label it as **not implemented**, **planned**, or **not yet integrated** rather than wording that suggests partial completion without evidence.

Appendix settings in the progress report must match the experiment artifact actually used in the report. If the reported CSV only uses one segment window, list that single value instead of a broader planned sweep.

Reference formatting in the progress report should match the inline citation style. If the body uses bracketed citations such as `[1]`, the reference list should also use bracketed numbering.

---

## 7. Paper Scope Boundaries

### In scope

- Partial scan chain selection
- Testability-driven FF ranking
- Stress-aware scan selection
- Segment-aware stress-leveling
- Tradeoff analysis among coverage proxy, toggles, stress, and hotspots
- Benchmark evaluation on ISCAS'89 circuits

### Explicitly out of scope

- Scan-chain diagnosis *(removed from codebase; not in paper scope or experiments)*
- Fault localization
- Defect diagnosis metrics
- Multi-chain scan architecture
- Chain reordering optimization
- Physical-layout-aware routing cost
- Silicon measurement

### Optional stretch scope

- Exact partial-scan fault coverage evaluation
- ATPG regeneration after partial-scan selection
- Additional public benchmarks beyond ISCAS'89

### Progress-report emphasis

For the progress report stage, the document should not read like a finished paper. It should explicitly identify the remaining technical work required for the final submission, especially when current results still rely on proxy-based evaluation.

The future-work section of the progress report should highlight:

1. exact fault-coverage evaluation for selected partial-scan sets
2. ATPG regeneration or fault simulation after partial-scan selection
3. broader validation across additional benchmarks, scan ratios, and hyperparameters
4. literature-backed baseline comparison
5. figure/table refinement and tighter discussion of limitations
6. final report integration, presentation preparation, and reproducibility cleanup

---

## 8. Method Section Structure

The method section of the paper should be organized as follows.

### 8.1 Problem definition

Define:
- circuit with `N` flip-flops
- selected partial-scan set of size `K`
- scan ratio `r = K / N`
- objective: preserve testability while reducing stress-related cost

### 8.2 Data extraction pipeline

Describe:
- FAN_ATPG export
- SCOAP computation
- `.sf` file contents
- pattern information used by ScanForge

### 8.3 Scan-shift simulation

Describe:
- shift-in process
- capture
- toggle counting
- switching activity formula

### 8.4 Stress metrics

Two distinct metrics are used (no weighted composite):

**Per-FF stress** (point metric, used in global-sort wear modes):
```
stress_score_i = toggle_rate_i = toggle_count_i / total_shift_cycles
```
Directly maps to per-cell switching activity during scan shift — the standard metric in low-power scan literature (e.g., PEAKASO, VTS 2006).

Note: `bias_score` (duty cycle deviation) and `max_run_score` (longest run / cycles) are still computed and exported to the stress CSV as diagnostic data, but are **not** included in `stress_score`. Their physical motivation in the scan-shift context is insufficient to include in the primary metric.

**Segment stress** (spatial metric, used in greedy wear-leveling modes):
```
segment_stress_j = mean(stress_score_i for FF i in window j)
hotspot threshold: segment_stress_j > mean(all segments) + 1·stddev(all segments)
```
Captures spatial concentration of switching activity along the chain. Motivated by thermal hotspot analysis in PEAKASO (Cho & Pan, VTS 2006).

Define in paper:
- segment average stress
- segment variance
- hotspot count

### 8.5 Selection methods

Document each mode formally:

1. `co`
2. `combined`
3. `random`
4. `co_wear`
5. `combined_wear`
6. `co_wear_leveling`
7. `combined_wear_leveling`

### 8.6 Coverage metric

Two cases:

- **Current paper-safe version:** define this as a **coverage proxy**
- **Preferred upgraded version:** replace or complement with exact fault coverage

### 8.7 Complexity discussion

Add time complexity for:
- global-sort methods
- greedy stress-leveling
- sweep execution

---

## 9. Equations and Definitions Needed

The paper should include explicit equations for:

1. `combined_score = CC0 + CC1 + 2 * CO`
2. normalized stress-aware score
3. stress-leveling greedy score
4. switching activity
5. stress imbalance
6. segment stress summary
7. coverage proxy
8. tradeoff score, if used in paper

If the tradeoff score is heuristic only, label it clearly as a ranking aid rather than a scientific metric.

---

## 10. Comparison Matrix

The paper needs a precise comparison plan.

### 10.1 Baselines to include

| Baseline | Include? | Why |
|---|---|---|
| Random | Yes | Minimum credible baseline |
| SCOAP-CO | Yes | Classical and intuitive reference |
| SCOAP-Combined | Yes | Stronger testability baseline |
| Per-FF stress-aware ranking | Yes | Direct comparison to your main idea |
| Segment-aware stress-leveling | Yes | Main proposed method |

### 10.2 Comparisons to report

For each benchmark and scan ratio:

1. Coverage proxy or exact fault coverage
2. Coverage loss
3. Total toggles
4. Switching activity
5. Max per-FF stress
6. Stress variance
7. Stress imbalance
8. Max segment stress
9. Segment variance
10. Hotspot count
11. Runtime

### 10.3 Ablations to include

| Ablation | Purpose |
|---|---|
| `lambda = 0` | Confirm reduction to pure testability ranking |
| multiple `lambda` values | Show tradeoff sensitivity |
| multiple segment windows | Show locality sensitivity |
| `co` vs `combined` | Show effect of controllability terms |
| stress-aware vs stress-leveling | Separate global-sort and greedy effects |

---

## 11. Experiment Matrix

### Benchmarks

Primary benchmark pool:

- s27
- s208
- s510
- s953
- s1196
- s1238
- s5378
- s9234
- s15850
- s35932
- s38417
- s38584

### Ratios

Mandatory:
- 25%
- 50%
- 75%
- 100%

Preferred for final plots:
- 5% step fine sweep for selected representative circuits

### Modes

Mandatory:
- `random`
- `co`
- `combined`
- `co_wear`
- `combined_wear`
- `co_wear_leveling`
- `combined_wear_leveling`

### Hyperparameters

Mandatory:
- `lambda ∈ {0, 0.25, 0.5, 0.75, 1.0}`
- `segment_window ∈ {8, 16}`

Stretch:
- larger window study

### Representative circuit subsets for paper figures

At minimum choose:

- **small:** s27 or s208
- **medium:** s953 or s1238
- **large:** s5378 or s9234
- **very large:** s15850 / s35932 / s38417 / s38584

---

## 12. Tables Required in the Paper

### Table T1. Benchmark summary
- circuit
- FF count
- pattern count
- full-scan shift cycles

### Table T2. Method summary
- mode
- formula
- optimization target
- computational style (sort vs greedy)

### Table T3. Main benchmark results
- per circuit, per ratio, best mode(s)
- include coverage and stress metrics

### Table T4. Hyperparameter sensitivity
- selected circuits
- lambda / window effect

### Table T5. Runtime / scalability
- circuit
- mode
- runtime

### Table T6. Literature comparison table
- prior work
- objective
- metrics
- benchmark type
- whether open-source / reproducible
- difference from ScanForge

---

## 13. Figures Required in the Paper

### Figure F1. Overall framework
FAN_ATPG export -> `.sf` -> ScanForge selection -> simulation -> metrics

### Figure F2. Metric illustration
Example of per-FF and segment stress on a small chain

### Figure F3. Coverage-stress Pareto plot
Representative circuits, different modes on same plot

### Figure F4. Lambda sensitivity
Coverage proxy vs stress metric across `lambda`

### Figure F5. Window sensitivity
Segment-aware method under different segment windows

### Figure F6. Scalability trend
Runtime vs FF count

### Figure F7. Case study
One benchmark where stress-aware ranking helps, and one where stress-leveling changes the frontier

---

## 14. Literature Review Plan

The literature review should be structured by **problem family**, not by random paper order.

### Bucket A. Classical partial scan selection

Need papers on:
- SCOAP-driven partial scan
- testability-based scan FF selection
- partial scan under area/test cost constraints

Questions to answer:
- What metrics are traditionally used?
- Do they optimize coverage only, or also test time / overhead?
- What baselines are standard?

### Bucket B. Power-aware / toggle-aware scan

Need papers on:
- scan power reduction
- switching activity reduction during scan shift
- low-power DFT / low-power scan methodologies

Questions to answer:
- Are they minimizing peak power, average power, or toggles?
- Do they optimize chain ordering, pattern ordering, X-filling, or scan-cell selection?

### Bucket C. Stress-aware / reliability-aware DFT

Need papers on:
- aging-aware scan
- reliability-aware test
- stress balancing or hotspot mitigation during scan

Questions to answer:
- Is wear modeled at per-cell or segment level?
- Is there prior work on balancing stress spatially along a chain?
- What is genuinely novel in your segment-aware stress-leveling method?

### Bucket D. Multi-objective optimization in test

Need papers on:
- Pareto optimization in DFT
- multi-objective scan design
- heuristics balancing coverage and cost

Questions to answer:
- How do prior works present tradeoffs?
- What evaluation style is accepted by the venue?

### Deliverable from literature review

Create a comparison table with:

| Paper | Objective | Method | Metrics | Benchmarks | Limitation | Difference vs ours |
|---|---|---|---|---|---|---|

---

## 15. Claims That Must Be Supported by Evidence

If the paper says one of the following, the experiments must support it directly.

| Claim | Required evidence |
|---|---|
| preserves testability | coverage proxy or exact coverage table |
| reduces stress | max stress / variance / hotspot reduction |
| balances wear spatially | segment metrics and case study |
| scales to large circuits | runtime table on large ISCAS'89 |
| robust to parameters | lambda/window ablation |
| better than conventional methods | direct baseline comparison |

---

## 16. Current Gaps Before Writing the Paper

### High priority

1. ~~Cleanly define the paper contribution in one sentence.~~ **DONE** — see Section 2.
2. Decide whether the paper uses:
   - only coverage proxy, or
   - coverage proxy + exact fault coverage validation.
   → **Current decision: coverage proxy only, with explicit disclaimer.**
3. Run a complete experiment matrix for all required modes.
4. ~~Add runtime logging.~~ **DONE** — `selection_time_ms` / `simulation_time_ms` in sweep CSV.
5. Create publication-quality figures from CSV outputs.
6. Perform literature review and build the comparison table.

### Medium priority

1. ~~Refine stress metric explanation.~~ **DONE** — `stress_score = toggle_rate` only; bias/run retained as diagnostic CSV columns.
2. Verify that README/docs match the implementation exactly.
3. Add a reproducibility section and exact command lines.
4. Clarify where heuristic scores are used — `tradeoff_score` in sweep CSV is a ranking aid only, not a scientific metric.

### Low priority

1. Expand to more benchmark families.
2. Add extra sensitivity studies.
3. Package artifact for public release.

---

## 17. Risks and Threats to Validity

The paper should include a limitations / threats section.

### Construct validity

- Coverage may currently be estimated by a SCOAP proxy rather than exact stuck-at fault coverage.
- Stress score is a model-derived metric, not direct silicon degradation.
- **Stress reduction effectiveness is bounded by circuit stress spread.** For large circuits
  (e.g., s5378, N=179), all FFs have stress in a narrow range [0.40, 0.53]; no selection
  of K ≈ N/2 FFs can meaningfully avoid high-stress FFs. Alternative metrics (full-chain
  density windows) provide no significant improvement in this regime. This is a fundamental
  limitation of selection-based stress optimization, not an algorithmic deficiency.

### Internal validity

- Different modes may optimize different objectives; a method should not be judged only on metrics it was not designed to optimize.
- Segment-aware greedy selection uses a static full-scan stress profile as input.
- The leveling improvement is concentrated in small/medium circuits (N ≤ ~30) where stress
  variance is higher. For large circuits with near-uniform stress, the method degenerates
  to pure testability-based selection.

### External validity

- Results are currently limited to ISCAS'89 benchmark circuits.
- Real industrial scan architectures may include multiple chains and additional physical constraints.

---

## 18. Paper Outline

### 1. Introduction
- problem importance
- why partial scan still matters
- why stress-aware selection matters
- contributions

### 2. Related Work
- partial scan
- low-power scan
- reliability / stress-aware DFT
- gap statement

### 3. Preliminaries
- SCOAP
- scan-shift activity
- stress metrics

### 4. Proposed Framework
- data flow
- selection methods
- stress-aware and stress-leveling formulations

### 5. Experimental Setup
- benchmarks
- ratios
- hyperparameters
- baselines
- metrics

### 6. Results and Discussion
- overall comparison
- ablations
- case studies
- runtime

### 7. Threats to Validity

### 8. Conclusion

---

## 19. Publication Deliverables Checklist

### Writing deliverables

- [ ] title options
- [ ] abstract
- [ ] introduction
- [ ] related work
- [ ] method section
- [ ] experiment section
- [ ] results discussion
- [ ] threats to validity
- [ ] conclusion

### Experimental deliverables

- [ ] full benchmark result CSVs
- [ ] fine-sweep CSVs for representative circuits
- [ ] runtime measurements
- [ ] final tables
- [ ] final figures

### Literature deliverables

- [ ] paper collection
- [ ] comparison table
- [ ] citation database in IEEE format

### Artifact deliverables

- [ ] reproducibility commands
- [ ] script inventory
- [ ] versioned result files
- [ ] release checklist

---

## 20. Immediate Next Actions

1. Finalize the exact one-sentence contribution claim.
2. Decide whether exact fault coverage will be added before submission.
3. Complete literature review table for partial scan / low-power scan / stress-aware DFT.
4. Run the full mode × ratio × lambda × window experiment matrix.
5. Generate summary CSVs and plots for representative circuits.
6. Build the paper outline from this spec.

---

## 21. Spec Maintenance Rule

When the implementation or paper direction changes, update this file first so it remains the source of truth for:

- paper scope
- feature inventory
- experiment requirements
- literature review targets
- publication readiness
