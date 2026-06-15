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

### Two benchmark suites: 15 circuits (10 complete)

| Suite | Circuits | FFs | Source |
|-------|----------|-----|--------|
| ITC'99 | b03–b13 (8) | 29–88 | Yosys + NanGate45 |
| ISCAS'89 | s953–s35932 (7) | 18–1728 | TTU → NanGate45 |

**Report focus: 10 circuits with full data** (6 ITC'99 + 4 ISCAS'89; b11, b13, s9234, s15850, s35932 pending).

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

## Slide 6 — Results: ITC'99 (10 common circuits)

**B2 reference:** b03=91.62%, b04=93.46%, b05=95.34%, b07=93.46%, b08=94.03%, b09=93.44%

| Circuit | B1 (T=1) | Exp 1 (Baseline) | **Exp 2 (Two-Phase)** | Exp 3 (Uni T1) | Exp 4 (EnBtr) | Exp 5 (StLrn) |
|---------|:--------:|:----------------:|:---------------------:|:--------------:|:-------------:|:-------------:|
| b03 | 44.50% | 44.50% | **85.41%** | 44.50% | 41.66% | 44.50% |
| b04 | 75.21% | 85.42% | **84.46%** | 85.42% | 89.57% | 85.42% |
| **b05** | 29.10% | 45.94% | **87.68%** | 46.10% | 48.86% | 45.92% |
| b07 | 56.13% | 57.64% | **87.93%** | 57.64% | 57.57% | 57.64% |
| b08 | 72.96% | 91.99% | **91.09%** | 91.99% | 91.99% | 91.99% |
| b09 | 76.34% | 86.56% | **87.85%** | 86.56% | 86.56% | 86.56% |

**T=4 added 0.00pp on every circuit in Exp 2 (Two-Phase ON).** T=4 gain only seen in non-Two-Phase exps (e.g., b05 +16.69pp in Exp 1).

---

## Slide 7 — Results: ISCAS'89 (10 common circuits)

**B2 reference:** s953=96.91%, s1196=98.27%, s1238=95.14%, s5378=94.74%

| Circuit | B1 (T=1) | Exp 1 (Baseline) | **Exp 2 (Two-Phase)** | Exp 3 (Uni T1) | Exp 4 (EnBtr) | Exp 5 (StLrn) |
|---------|:--------:|:----------------:|:---------------------:|:--------------:|:-------------:|:-------------:|
| s953 | 36.75% | 37.40% | **91.26%** | 37.40% | 37.94% | 37.40% |
| s1196 | 86.13% | 98.40% | **98.40%** | 98.40% | 98.40% | 98.40% |
| s1238 | 82.42% | 95.12% | **95.12%** | 95.12% | 95.12% | 95.12% |
| s5378 | 74.25% | 91.86% | **94.97%** | 91.86% | 91.83% | 91.86% |

**s953 highlighted:** baseline gain = +0.65pp, **Two-Phase gain = +54.51pp** — Two-Phase is the recovery mechanism.

**T=4 added 0.00pp on every circuit in Exp 2.**

---

## Slide 7b — Ablation Results (10 common circuits)

| Exp | Parameter | Avg FC | Avg Gain | **ΔFC vs Exp 1** | ΔRuntime |
|-----|-----------|:------:|:--------:|:---------------:|:--------:|
| 1 | Baseline (T1=800, TP=OFF) | 73.48% | 10.10pp | — | 5.72s |
| 2 | **Two-Phase ON** | **90.42%** | **27.03pp** | **+16.94pp** | 7.30s |
| 3 | Uniform T1=5000 | 73.50% | 10.11pp | +0.02pp | 4.08s |
| 4 | Enhanced Backtrace | 73.95% | 10.32pp | +0.47pp | 12.86s |
| 5 | Static Learning | 73.48% | 10.09pp | +0.00pp | 4.64s |

**Key takeaway:** Only Two-Phase ON produces meaningful improvement (+16.94pp). Uniform T1, enhanced backtrace, and static learning are all negligible (±0.5pp).

---

## Slide 8 — Why T=2 Works

### Two mechanisms investigated by ablation

**1. Frame-based backtrack limit (Exp 3: Uniform T1=5000)**
- T1=800 prevents wasted search on non-scan-FF-blocked faults
- Exp 3 shows **raising T1 to 5000 has no effect** (+0.02pp)
- → The T1 differential does **NOT** create the residual; non-scan FF X-state blocking does

**2. Two-Phase State Justification (Exp 2) ← THE MECHANISM**
- Non-scan FF blocked faults: T=1 can't propagate past unknown FF state
- T=2: Phase 1 treats non-scan PPIs as free PIs → finds propagation path
- Phase 2 backward-justifies PPI values through frame 0
- **Result: avg FC jumps from 73.48% to 90.42% (+16.94pp)**

### No per-target timeout

- Backtrack limit is the **sole bounding mechanism**
- No wall-clock timeout needed — T1=800 keeps T=1 fast

---

## Slide 9 — Why T=4 Adds Nothing

### Confirmed: T=4 gain = 0.00pp on all circuits with Two-Phase ON (Exp 2)

| T=2 gain (Exp 2) | T=4 gain (Exp 2) |
|:----------------:|:----------------:|
| avg 24.16pp | **0.00pp** |

Without Two-Phase (Exp 1/3/4/5), T=4 adds modest gain (b05 +16.69pp in Exp 1) because the **unified search at T=2 is inefficient** — it leaves recoverable faults for T=4.

### Why?

- Residual after T=2 with Two-Phase: structurally AU faults at any depth
- Sequential depth ≤ 2 through non-scan FFs in synthesized circuits
- One initialization frame (T=2) suffices when propagation and justification are decoupled

---

## Slide 10 — Remaining Gap to Full-Scan

- B2 − Exp = gap to full-scan
- **Exp 2 average gap: 4.24pp** (three circuits match or exceed B2)
- Sources:
  1. **AU under partial scan**: fault's only observable path passes through non-scan FF → structural limit of 10% configuration
  2. **UD faults (QN pin)**: excluded from ATPG at any depth

### Two-Phase ON pipeline substantially narrows the gap

| Circuit | B1 (T=1) | B2 (full-scan) | Exp 2 | Gap B2−Exp 2 |
|---------|:--------:|:--------------:|:-----:|:------------:|
| b05 | 29.10% | 95.34% | 87.68% | **7.66pp** |
| s953 | 36.75% | 96.91% | 91.26% | **5.65pp** |
| b07 | 56.13% | 93.46% | 87.93% | **5.53pp** |

Average gap reduced from **26.47pp (T=1)** to **4.24pp (Exp 2)**.

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
| **Frame-based backtrack limit** | T1=800 at T=1, 5000 at T>1 | Prevents wasted search, but does NOT create the residual (Exp 3 confirmed) |
| **Pipeline** | Progressive residual T=1→T=2→T=4 | Baseline recovers 10.10pp; with Two-Phase recovers **27.03pp avg** |
| **Ablation** | 5 experiments × 10 circuits | **Two-Phase is the only effective mechanism** (+16.94pp vs baseline) |
| **Two-Phase** | Decoupled search for multi-frame ATPG | **Dominant recovery engine** — T=2 gains up to 58.49pp |

### Key findings

1. **Two-Phase ON is the dominant mechanism** — uniform T1 (+0.02pp), enhanced backtrace (+0.47pp), and static learning (+0.00pp) are negligible
2. **T=4 adds 0 pp with Two-Phase** — T=2 exhausts all recoverable faults
3. **Gap to full-scan** narrows from 26.47pp (T=1) to **4.24pp (Exp 2)**
4. **Backtrack limit** is the sole bounding mechanism (no per-target timeout)

### Future work

- Complete remaining 5 circuits, T=8 pipeline, transition-delay faults, larger benchmarks
