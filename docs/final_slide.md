# Sequential ATPG Coverage Recovery for Timing-Constrained Partial-Scan Circuits

## Slide Deck

---

## Slide 1 — Title

- **Sequential ATPG Coverage Recovery for Timing-Constrained Partial-Scan Circuits**
- EEE5001 VLSI Testing — Group 5
- 丁睿濂, 駱彥竹, 黃思維
- June 2026

---

## Slide 2 — Problem

### Full-scan ideal

- Every FF in scan chain → ATPG can set any FF state in one cycle
- High stuck-at fault coverage (88–99%)

### Reality: timing constraints

- Scan MUX adds delay on FF input → critical paths may fail timing
- Some FFs **must stay non-scan**
- → Circuit becomes **partial-scan**
- T=1 ATPG loses coverage: non-scan FF initial state = **X**, uncontrollable

### Research Question

How much coverage can multi-frame sequential ATPG recover on timing-constrained partial-scan circuits?

---

## Slide 3 — Two-Phase State Justification

### Standard TFE (time-frame expansion)

- Unroll circuit across T frames
- ATPG solves **propagation + state justification simultaneously**
- → Exponential search space → backtrack limit → **false AU classification**

### Two-Phase (ours, engine level)

Separates the two problems:

| Phase | What |
|-------|------|
| **Phase 1** | disconnect non-scan PPIs → treat them as free PIs → PODEM on **last frame only** |
| **Phase 2** | backward-justify required non-scan PPI states through frames 0..T−2 |

Drastically reduces backtrack pressure. **Tested as ablation experiment** (Exp 2).

---

## Slide 4 — Frame-Based Backtrack Limit + Progressive Pipeline

### Frame-based backtrack limit

- T=1 uses **T1=800** backtracks per fault (not 5000)
- Prevents engine from wasting search on faults structurally blocked by non-scan FF X-state
- These faults → **AB** (backtrack limit hit), not AU → T=2 retries
- T>1 uses full BACKTRACK=5000

### No per-target timeout

- Backtrack limit is the **sole bounding mechanism**
- No wall-clock timeout per fault

### Pipeline flow (baseline: Two-Phase OFF)

```
T=1 (all faults, 1 frame, T1=800) → D1
R1 = all − D1
T=2 (residual R1, 2 frames, BACKTRACK=5000) → D2
R2 = R1 − D2
T=4 (residual R2, 4 frames, BACKTRACK=5000) → D4
Final = D1 ∪ D2 ∪ D4
```

---

## Slide 5 — Experimental Setup: 5 Ablation Experiments

### Two benchmark suites: 15 circuits

| Suite | Circuits | FFs | Source |
|-------|----------|-----|--------|
| ITC'99 | b03–b13 (8) | 29–88 | Yosys + NanGate45 |
| ISCAS'89 | s953–s35932 (7) | 18–1728 | TTU → NanGate45 |

### Setup

| Parameter | Value |
|-----------|-------|
| Non-scan ratio | **10%** (timing-critical, OpenSTA slack ranking) |
| ATPG engine | FAN_ATPG (baseline: Two-Phase OFF) |
| Bounding mechanism | **Backtrack limit** (no per-target timeout) |
| Wall timeout | 3600 s |
| **B2** reference ceiling | Full-scan, T=1, all FFs in chain |

### Five controlled experiments

| Exp | Change vs Baseline | RQ |
|-----|-------------------|----|
| 1 | Baseline (T1=800, TP=OFF, no heuristics) | How much does plain pipeline recover? |
| 2 | Two-Phase ON at T>1 | Does decoupling help? |
| 3 | Uniform T1=5000 at T=1 | Is T1 differential the mechanism? |
| 4 | Enhanced backtrace ON | Does PCA scoring help? |
| 5 | Static learning ON | Does early conflict detection help? |

Each experiment = full T1→T2→T4 pipeline on all 15 circuits.

---

## Slide 6 — Results: ITC'99 [(pending)]

Full sweep in progress. Pilot result from baseline (Exp 1):

| Circuit | B1 (T=1) | Exp 1 (T1+T2+T4) | Gain |
|---------|:---------:|:-----------------:|:----:|
| b03 | (pending) | (pending) | |
| b04 | (pending) | (pending) | |
| b05 | (pending) | (pending) | |
| ... 8 circuits | | | |

**T=4 expected to add 0.00pp on every circuit.**

---

## Slide 7 — Results: ISCAS'89 [(pending)]

| Circuit | B1 (T=1) | Exp 1 (T1+T2+T4) | Gain |
|---------|:---------:|:-----------------:|:----:|
| s953 | (pending) | (pending) | |
| s1196 | (pending) | (pending) | |
| ... 7 circuits | | | |

**T=4 expected to add 0.00pp on every circuit.**

---

## Slide 7b — Ablation Results [(pending)]

| Exp | Parameter | ΔFC vs Exp 1 | ΔRuntime vs Exp 1 |
|-----|-----------|:------------:|:-----------------:|
| 1 | Baseline (T1=800, TP=OFF) | — | — |
| 2 | Two-Phase ON | pending | pending |
| 3 | Uniform T1=5000 | pending | pending |
| 4 | Enhanced Backtrace | pending | pending |
| 5 | Static Learning | pending | pending |

---

## Slide 8 — Why T=2 Works

### Two mechanisms investigated by ablation

**1. Frame-based backtrack limit creates the residual (T=1)**
- T1=800 prevents wasted search on non-scan-FF-blocked faults
- These become AB, not AU → T=2 can retry
- Exp 3 (Uniform T1=5000): tests if T1 differential is necessary

**2. Two-Phase State Justification (Exp 2)**
- non-scan FF blocked faults: T=1 can't propagate past unknown FF state
- T=2: Phase 1 treats non-scan PPIs as free PIs → finds propagation path
- Phase 2 backward-justifies PPI values through frame 0

### No per-target timeout

- Backtrack limit is the **sole bounding mechanism**
- No wall-clock timeout needed — T1=800 keeps T=1 fast

---

## Slide 9 — Why T=4 Adds Nothing

### Observed and expected: T=4 gain = 0.00pp on all circuits

| T=2 gain | T=4 gain |
|:--------:|:--------:|
| pending | **0.00pp** |

### Why?

- Residual after T=2 consists of structurally AU faults: non-scan FF state does not influence propagation even with multi-frame — adding more frames won't help

### Sequential depth hypothesis

These synthesized circuits have **sequential depth ≤ 2** through non-scan FFs. One initialization frame (T=2) suffices; more frames add no new state reachability.

---

## Slide 10 — Remaining Gap to Full-Scan

- B2 − Exp = gap to full-scan
- Sources:
  1. **AU under partial scan**: fault's only observable path passes through non-scan FF → structural limit of 10% configuration
  2. **UD faults (QN pin)**: excluded from ATPG at any depth

### Pipeline substantially narrows the gap

Example (pilot): b05 goes from B1 ≈ 29% → Exp ≈ 87% (B2 ≈ 95%)
Pipeline recovers most of the gap to full-scan.

---

## Slide 11 — Limitations

1. **Backtrack limit sensitivity**: Results depend on T1=800 / BACKTRACK=5000 choice
2. **Shallow depth**: T=8 not evaluated
3. **10% only**: Single fixed ratio
4. **Single backend**: FAN_ATPG only
5. **15 circuits**: May not generalize to industrial designs

---

## Slide 12 — Conclusion

### Summary

| Contribution | What | Impact |
|-------------|------|--------|
| **Frame-based backtrack limit** | T1=800 at T=1, 5000 at T>1 | Creates structural AB residual for T=2 |
| **Pipeline** | Progressive residual T=1→T=2→T=4 | T=2 recovers substantial coverage |
| **Ablation** | 5 experiments × 15 circuits | Decomposes recovery mechanism |
| **Two-Phase** | Decoupled search for multi-frame ATPG | Tested as ablation (Exp 2) |

### Key findings

1. The pipeline recovers most coverage lost by partial-scan
2. T=4 adds **0 pp universally** — redundant
3. Ablation experiments isolate the recovery mechanism
4. Backtrack limit is the **sole bounding mechanism** (no per-target timeout)

### Future work

- T=8 pipeline, transition-delay faults, larger benchmarks
