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

## Slide 3 — Technique 1: Two-Phase State Justification

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

- Drastically reduces backtrack pressure
- ON by default in FAN_ATPG multi-frame mode

---

## Slide 4 — Technique 2: Frame-Based Backtrack Limit + Progressive Pipeline

### Frame-based backtrack limit

- T=1 uses **FAST=800** backtracks per fault (not 5000)
- Prevents engine from wasting search on faults structurally blocked by non-scan FF X-state
- These faults → **AB** (backtrack limit hit), not AU → T=2 retries
- T>1 uses full BACKTRACK=5000

### Per-target timeout (ptt=5s) safety net

- Wall-clock bound for very large circuits
- no_ptt ablation: results **identical** to baseline on 8/8 circuits → backtrack limit is the real mechanism

### Pipeline flow

```
T=1 (all faults, single frame, FAST=800) → D1
R1 = all − D1
T=2 (residual R1, two-frame + Two-Phase, BACKTRACK=5000) → D2
R2 = R1 − D2
T=4 (residual R2, four-frame + Two-Phase, BACKTRACK=5000) → D4
Final = D1 ∪ D2 ∪ D4
```

---

## Slide 5 — Experimental Setup

### Two benchmark suites

| Suite | Circuits | FFs | Source |
|-------|----------|-----|--------|
| ITC'99 | b03–b13 (8) | 29–88 | Yosys + NanGate45 |
| ISCAS'89 | s953–s38584 (9) | 18–1728 | TTU → NanGate45 |

### Setup

| Parameter | Value |
|-----------|-------|
| Non-scan ratio | **10%** (timing-critical, OpenSTA slack ranking) |
| ATPG engine | FAN_ATPG with Two-Phase (ON) |
| Per-target timeout | **5 s** (uniform) |
| Wall timeout | 3600 s |
| Total runs | 17 circuits × 1 ratio = **17** |

---

## Slide 6 — Results: ITC'99 (@10%, ptt=5s)

| Circuit | FFs | B1 (T=1) | Exp (T1+T2+T4) | B2 (full-scan) | Exp−B1 | B2−Exp |
|---------|----:|---------:|---------------:|---------------:|-------:|-------:|
| b03 | 30 | 44.50% | 85.41% | 91.62% | **+40.91** | +6.21 |
| b04 | 66 | 75.21% | 84.46% | 93.46% | **+9.25** | +9.00 |
| b05 | 88 | 29.20% | 87.68% | 95.34% | **+58.49** | +7.66 |
| b07 | 44 | 56.13% | 87.93% | 93.46% | **+31.80** | +5.53 |
| b08 | 67 | 72.96% | 91.09% | 94.03% | **+18.13** | +2.94 |
| b09 | 29 | 76.34% | 87.85% | 93.44% | **+11.51** | +5.59 |
| b11 | 84 | 66.21% | 94.34% | 97.43% | **+28.13** | +3.09 |
| b13 | 86 | 77.33% | 82.01% | 91.13% | **+4.68** | +9.12 |

**T=4 adds 0.00pp on every circuit.**

---

## Slide 7 — Results: ISCAS'89 (@10%, ptt=5s)

| Circuit | FFs | B1 (T=1) | Exp (T1+T2+T4) | B2 (full-scan) | Exp−B1 | B2−Exp |
|---------|----:|---------:|---------------:|---------------:|-------:|-------:|
| s953 | 29 | 36.75% | 91.26% | 97.79% | **+54.51** | +6.53 |
| s1196 | 18 | 86.13% | 98.40% | 98.87% | **+12.27** | +0.47 |
| s1238 | 18 | 82.42% | 95.12% | 96.36% | **+12.71** | +1.24 |
| s5378 | 179 | 74.25% | 94.94% | 96.65% | **+20.69** | +1.71 |
| s9234 | 211 | 72.79% | 88.13% | 93.09% | **+15.34** | +4.96 |
| s15850 | 534 | 66.04% | 90.13% | 96.04% | **+24.09** | +5.91 |
| s35932 | 1728 | 77.10% | 83.79% | 88.20% | **+6.70** | +4.41 |
| s38417 | 1636 | 85.41% | 91.10% | 97.10% | **+5.69** | +6.00 |
| s38584 | 1426 | 71.67% | 87.16% | 93.58% | **+15.49** | +6.42 |

**T=4 adds 0.00pp on every circuit.**

---

## Slide 8 — Why T=2 Works

### Two mechanisms, one recovery engine

**1. Frame-based backtrack limit creates the residual (T=1)**
- FAST=800 prevents wasted search on non-scan-FF-blocked faults
- These become AB, not AU → T=2 can retry

**2. Two-Phase State Justification recovers (T=2)**
- non-scan FF blocked faults: T=1 can't propagate past unknown FF state
- T=2: Phase 1 treats non-scan PPIs as free PIs → finds propagation path
- Phase 2 backward-justifies PPI values through frame 0

### ptt is a safety net, not the mechanism

- no_ptt ablation: identical results on 8/8 circuits
- Backtrack limit bounds search before ptt fires
- ptt=5s only matters for very large circuits (s38417: 1636 FFs)

---

## Slide 9 — Why T=4 Adds Nothing

### Consistent across ALL 17 circuits

| T=2 gain | T=4 gain |
|:--------:|:--------:|
| +4.68–58.49pp | **0.00pp** |

### Why?

- Residual after T=2 consists of:
  1. **Structurally AU**: non-scan FF state does not influence propagation even with multi-frame — adding more frames won't help
  2. **TO at T=2**: also TO at T=4 (equally time-limited)

### Sequential depth hypothesis

These synthesized circuits have **sequential depth ≤ 2** through non-scan FFs. One initialization frame (T=2) suffices; more frames add no new state reachability.

---

## Slide 10 — Remaining Gap to Full-Scan

- B2 − Exp = **0.47–9.12 pp**
- Sources:
  1. **AU under partial scan**: fault's only observable path passes through non-scan FF → structural limit of 10% configuration
  2. **UD faults (QN pin)**: excluded from ATPG at any depth

### Pipeline substantially narrows the gap

Example: b05 goes from B1 = 29.20% → Exp = 87.68% (B2 = 95.34%)
Pipeline recovers 58.49 of the 66.14pp gap to full-scan.

---

## Slide 11 — Limitations

1. **Backtrack limit sensitivity**: Results depend on FAST=800 / BACKTRACK=5000 choice
2. **Shallow depth**: T=8 not evaluated
3. **10% only**: Single fixed ratio
4. **Single backend**: FAN_ATPG only
5. **17 circuits**: May not generalize to industrial designs

---

## Slide 12 — Conclusion

### Summary

| Contribution | What | Impact |
|-------------|------|--------|
| **Two-Phase** | Decoupled search for multi-frame ATPG | Makes multi-frame practical |
| **Fast backtrack limit** | FAST=800 at T=1, 5000 at T>1 | Creates structural AB residual for T=2 |
| **Pipeline** | Progressive residual T=1→T=2→T=4 | T=2 recovers +4.68–58.49pp |
| **Evaluation** | 17 circuits, 2 suites, unified setup | Consistent T=2 gain, T=4 = 0 |

### Key findings

1. T=2 recovers coverage on **14/17 circuits** (backtrack limit + Two-Phase)
2. T=4 adds **0 pp universally** — redundant
3. Two-Phase + fast backtrack limit: **practical methodology** for partial-scan coverage recovery

### Future work

- T=8 pipeline, transition-delay faults, larger benchmarks
