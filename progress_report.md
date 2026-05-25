# Progress Report
## Course: [COURSE NAME / NUMBER]
## Date: 2026-05-26

---

## Group Information

| Item | Info |
|------|------|
| Group Number | [GROUP NUMBER] |
| Topic | 3. Self-Defined — Stress-Aware Partial Scan Selection |
| Members | [MEMBER 1 NAME / ID], [MEMBER 2 NAME / ID], [MEMBER 3 NAME / ID] |

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
| Multi-mode sweep script | 🔲 Pending |
| Full experiment matrix (12 circuits) | 🔲 Pending |
| Publication-quality figures | 🔲 Pending |
| Literature comparison table | 🔲 Pending |
| Exact fault coverage | 🔲 Out of scope (proxy used with disclaimer) |

**Backend:** Built on FAN_ATPG (NTU LaDS-II) for SCOAP export via `.sf` format.
**Benchmarks:** ISCAS'89 (s27–s38584, 12 circuits, 3–1728 FFs).

---

## Job Partition

| Member | Responsibilities |
|--------|----------------|
| [MEMBER 1] | [e.g., FAN_ATPG integration, .sf parser, simulation engine] |
| [MEMBER 2] | [e.g., partial scan selection algorithms, stress metrics] |
| [MEMBER 3] | [e.g., experiments, figures, report writing] |

---

## Schedule

| Date | Milestone |
|------|-----------|
| 2026-05-26 | Progress report submission |
| 2026-05-27–05-31 | Run full experiment matrix (12 circuits × 7 modes × 4 ratios) |
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

6. [TO BE ADDED — ETD partial scan paper]

7. [TO BE ADDED — low-power scan survey paper]

---

## AI Usage Declaration

This project made use of Claude (Anthropic) as an AI coding and research assistant for:
- Code implementation and debugging (C++ source)
- Literature search and summarization
- Metric definition review and comparison with published work
- Report and specification drafting

All key design decisions, algorithm logic, and experimental analysis were reviewed and confirmed by team members. The AI was used as a productivity tool; all claims in this report are understood and verified by the team.

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
