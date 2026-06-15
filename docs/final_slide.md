# Sequential ATPG Coverage Recovery for Timing-Constrained Partial-Scan Circuits

## Slide Deck

---

## Slide 1 — Title

- **Sequential ATPG Coverage Recovery for Timing-Constrained Partial-Scan Circuits**
- EEE5001 VLSI Testing — Group 5
- 丁睿濂, 駱彥竹, 黃思維
- June 2026

---

## Slide 2 — Motivation: Timing Constraints Force Partial Scan

### What is scan?
- **Scan chain:** flip-flops (FFs) are daisy-chained so test vectors can be shifted in/out
- **Full-scan:** every FF is in the chain → ATPG can set any FF state in one cycle
- **Result:** high stuck-at fault coverage (88–99% on our benchmarks)

### The problem: scan MUX adds delay
- A scan FF = regular FF + a 2-to-1 MUX on its data input
- This MUX adds **∆delay** on the FF's data path
- On **timing-critical paths** (smallest slack), this extra delay can violate setup timing

### Our response
- OpenSTA ranks FFs by minimum-path-slack on gate-level netlists
- **Top 10% of FFs** (by minimum-path-slack) are designated **non-scan**
- 10% chosen empirically: excludes enough FFs to relieve timing-critical paths while keeping most FFs in scan
- These FFs are NOT in the scan chain → ATPG cannot directly control them

### Research Question
How much stuck-at fault coverage can we recover on these timing-constrained partial-scan circuits?

---

## Slide 3 — Background: Scan Design 101

### How scan testing works
1. **Shift:** test vector shifted into scan chain (multiple clock cycles)
2. **Capture:** one functional clock cycle — circuit responds to the vector
3. **Shift-out:** circuit response shifted out, compared to expected values

### Full-scan vs partial-scan

| | Full-scan | Partial-scan |
|---|---|---|
| **Scan FFs** | All FFs in chain | Subset of FFs in chain |
| **Non-scan FFs** | None | Remain as regular FFs |
| **ATPG control** | Any FF state set in 1 cycle | Scan FFs: 1 cycle; Non-scan FFs: must be functionally justified |
| **Hardware overhead** | Higher (MUX per FF) | Lower (fewer MUXes) |
| **Timing impact** | Affects all FF paths | Spares critical paths |

### Why not make all FFs scan?
- Each scan FF adds a MUX (2-4 gate equivalents) → area + delay
- Critical paths cannot afford this extra delay
- Trade-off: fewer scan FFs → less timing impact → but harder ATPG

---

## Slide 4 — Background: The X-State Problem

### T=1 (single frame) ATPG
At T=1, the ATPG sees the circuit as **combinational** (one clock cycle):

- **Scan FF outputs:** freely controllable (set by scan-in) — treated as **pseudo-primary inputs (PPIs)**
- **Non-scan FF outputs:** unknown at startup — treated as **X** (unknown value)
- Any fault whose propagation path goes through a non-scan FF output (PPO — pseudo-primary output) cannot be detected

### Illustration
```
Fault → ... → non-scan FF (value=X) → observable output?
              ↑
        propagation blocked (X blocks fault effect from propagating)
```

### Consequence
- Faults blocked by non-scan FF X-state are **structurally untestable at T=1**
- Classified as **AU** (ATPG-untestable) or **AB** (abort — backtrack limit hit)
- **Goal:** recover these faults by using multiple time frames

### Key terms
- **FC (Fault Coverage)** = DT / (DT + AU + AB + UD) — percentage of detected faults
- **DT** = detected (test pattern found)
- **AU** = ATPG-untestable (no pattern exists within search limits)
- **AB** = abort (search exhausted before finding pattern)
- **UD** = undetected (not targeted)
- **B1** = baseline T=1 partial-scan FC; **B2** = full-scan FC ceiling

---

## Slide 5 — Step 1: Measure the T=1 Gap to Full-Scan

We first establish the coverage loss: T=1 (partial-scan, B1) vs full-scan (B2).

### Full-scan reference (B2)

| Circuit | B2 |
|---------|:--:|
| b03 | 91.62% |
| b04 | 93.46% |
| b05 | 95.34% |
| b07 | 93.46% |
| b08 | 94.03% |
| b09 | 93.44% |
| s953 | 96.91% |
| s1196 | 98.27% |
| s1238 | 95.14% |
| s5378 | 94.74% |

### T=1 partial-scan (B1) vs B2

| Circuit | B1 (T=1) | B2 (full-scan) | **Gap** |
|---------|:--------:|:--------------:|:-------:|
| b03 | 44.50% | 91.62% | **47.12pp** |
| b04 | 75.21% | 93.46% | **18.25pp** |
| b05 | 29.10% | 95.34% | **66.24pp** |
| b07 | 56.13% | 93.46% | **37.33pp** |
| b08 | 72.96% | 94.03% | **21.07pp** |
| b09 | 76.34% | 93.44% | **17.10pp** |
| s953 | 36.75% | 96.91% | **60.16pp** |
| s1196 | 86.13% | 98.27% | **12.14pp** |
| s1238 | 82.42% | 95.14% | **12.72pp** |
| s5378 | 74.25% | 94.74% | **20.49pp** |

**Average gap: 31.26pp.** Non-scan FF X-state blocks propagation, making faults structurally untestable at T=1. The gap varies with topology (12.14pp to 66.24pp).

---

## Slide 6 — Background: Time-Frame Expansion (Multi-Frame ATPG)

### How sequential ATPG works
Instead of one time frame, unroll the circuit across **T clock cycles**:

```
Scan PPIs (independent per frame):
Frame 0 ──→ [combinational] ──→ scan out    Frame 1 ──→ [combinational] ──→ scan out    Frame T−1 ──→ [combinational] ──→ obs out
                ↕                                     ↕                                              ↕
            non-scan FF                            non-scan FF                                     non-scan FF
            (starts X)                             (justified by Frame 0)                          (justified by Frame T−2)
            state ──→ Frame 1                      state ──→ Frame 2                               (last frame)
```

- **Non-scan FF** outputs at frame t become inputs at frame t+1
- Frame 0 non-scan FF starts as X, but can be **justified** by frames 0..t
- **Scan FF** PPIs are independently controllable at every frame

### Depth terminology
| Depth | Meaning |
|-------|---------|
| **T=1** | Single combinational frame. Non-scan FF outputs = X. |
| **T=2** | Two frames. Frame 0 initializes non-scan FFs; Frame 1 detects faults. |
| **T=4** | Four frames. More initialization cycles for deeper justification. |

### Backtrack limit
- ATPG searches by making decisions and **backtracking** when contradictions arise
- **Backtrack limit** = maximum number of backtracks per fault before giving up (AB)
- T=1: **800** (prevents wasting time on structurally unrecoverable faults)
- T>1: **5000** (full budget for sequential recovery)
- This differential (lower at T=1, higher at T>1) bounds wasteful search at T=1 while preserving full budget for sequential recovery at T>1

---

## Slide 7 — Step 2: Baseline Multi-Frame Recovery (T=2, T=4)

### Pipeline
1. T=1 (all faults, T1=800 backtracks) → residual R1 = undetected faults
2. T=2 (residual R1 only, 5000 backtracks) → residual R2
3. T=4 (residual R2 only, 5000 backtracks)
4. Final FC = |D1 ∪ D2 ∪ D4| / |F| (union of all detections)

### Results (baseline: Two-Phase OFF)

| Circuit | T1 FC | T1→T2→T4 FC | Gain T2 | Gain T4 | Total gain |
|---------|:----:|:-----------:|:-------:|:-------:|:----------:|
| b03 | 44.50% | 44.50% | +0.00pp | +0.00pp | +0.00pp |
| b04 | 75.21% | 85.42% | +4.88pp | +5.33pp | +10.21pp |
| b05 | 29.10% | 45.94% | +0.16pp | +16.69pp | +16.84pp |
| b07 | 56.13% | 57.64% | +0.00pp | +1.51pp | +1.51pp |
| b08 | 72.96% | 91.99% | +14.86pp | +4.17pp | +19.02pp |
| b09 | 76.34% | 86.56% | +10.22pp | +0.00pp | +10.22pp |
| s953 | 36.75% | 37.40% | +0.65pp | +0.00pp | +0.65pp |
| s1196 | 86.13% | 98.40% | +12.27pp | +0.00pp | +12.27pp |
| s1238 | 82.42% | 95.12% | +12.71pp | +0.00pp | +12.71pp |
| s5378 | 74.25% | 91.86% | +14.93pp | +2.68pp | +17.61pp |

**Average: 73.48% FC, +10.10pp total gain.**

### Key observation — inconsistent stage attribution
- b05 gains almost nothing at T=2 (+0.16pp), but **+16.69pp at T=4**
- s1196 gains everything at T=2 (+12.27pp), nothing at T=4
- b03 and s953 show almost no recovery at any depth
- **Why?** If the recovery were purely from more backtracks (800→5000), T=2 should capture all recoverable faults uniformly. It doesn't.

---

## Slide 8 — Background: Two-Phase State Justification

### The standard TFE problem
In standard multi-frame ATPG, propagation (in the last frame) and state justification (in earlier frames) are **interleaved in one search**:

```
Search tree combines:
  - D-drive decisions (propagation path in frame T−1)
  - Line-justification decisions (non-scan FF values in frames 0..T−2)
```
→ Backtrack budget exhausted on propagation → **never reaches justification**
→ Fault falsely classified as **AU** (when it might be testable with a better search strategy)

### Two-Phase decoupling
**Phase 1 — Propagation (last frame only):**
- Temporarily **disconnect** non-scan PPIs from their driving frame
- Treat them as **free primary inputs** (can assign any value)
- Run ATPG (PODEM algorithm) on the last frame's logic cone only
- Find a propagation path + set of PPI assignments

**Phase 2 — State Justification (earlier frames):**
- Reconnect the PPIs
- Backward-justify each required PPI value through frames T−2 .. 0
- Fresh backtrack budget for justification

### Why this helps
- Phase 1 is not blocked by non-scan FF X-state (PPIs are free)
- Phase 2 concentrates the budget on only the justification subproblem
- **This is the mechanism we investigate** — is it responsible for the recovery?

---

## Slide 9 — Step 3: Why Does T=2 Work? Two Hypotheses

### Observation
The baseline pipeline shows **inconsistent** T=2 recovery. Some circuits gain at T=2, others only at T=4. This tells us something structural is at play.

### Hypothesis A: The backtrack limit differential
- T=1: 800 backtracks (low budget → many faults abort → large residual R1)
- T=2: 5000 backtracks (full budget → retry aborted faults)
- If this is the mechanism: **the residual exists only because T=1 is capped**
- Test: **Exp 3 — Uniform T1=5000** (give T=1 the same budget as T=2)

### Hypothesis B: Two-Phase State Justification
- Standard TFE interleaves propagation + justification → exhausts budget on propagation
- Two-Phase decouples them → finds propagation path first, then justifies
- If the bottleneck is **search structure** (not search budget), circuits where T=2 fails under unified search should recover when Two-Phase is enabled
- Prediction: **s953** (T=2 gain +0.65pp under unified search) should show large T=2 gain with Two-Phase
- Test: **Exp 2 — Two-Phase ON at T>1**

### Two more control experiments
- **Exp 4 — Enhanced Backtrace:** better backtrace selection (composite score)
- **Exp 5 — Static Learning:** early conflict detection (fanout implications)
- These test whether search heuristics, rather than search structure, drive recovery

---

## Slide 10 — Background: Ablation Experiment Design

### What is ablation?
- Start with a **baseline** configuration (Exp 1)
- Change **exactly one parameter** per experiment
- Measure the effect on the output (final FC)
- If a parameter change causes a large ΔFC → that parameter is the mechanism

### Our five experiments

| Exp | Name | Parameter | Question it answers |
|-----|------|-----------|-------------------|
| 1 | Baseline | T1=800, TP=OFF | How much does the plain pipeline recover? |
| 2 | **Two-Phase ON** | TP enabled at T>1 | Does decoupling propagation from justification help? |
| 3 | Uniform T1 | T1=5000 (same as T>1) | Is the T1 differential the mechanism? |
| 4 | Enhanced Backtrace | Composite-score heuristic ON | Does better backtrace selection help? |
| 5 | Static Learning | Fanout-implication ON | Does early conflict detection help? |

### All experiments
- Run the **full T1→T2→T4 pipeline**
- On the **same 10 circuits**
- Same backtrack limits (T1=800, T>1=5000 except Exp 3)
- No per-target timeout — backtrack limit is the sole bounding mechanism

---

## Slide 11 — Ablation Results: ITC'99 Circuits

**B2 reference (full-scan):** b03=91.62%, b04=93.46%, b05=95.34%, b07=93.46%, b08=94.03%, b09=93.44%

| Circuit | Exp 1 (Baseline) | **Exp 2 (Two-Phase)** | Exp 3 (Uni T1) | Exp 4 (EnBtr) | Exp 5 (StLrn) |
|---------|:----------------:|:---------------------:|:--------------:|:-------------:|:-------------:|
| b03 | 44.50% | **85.41%** | 44.50% | 41.66% | 44.50% |
| b04 | 85.42% | 84.46% | 85.42% | 89.57% | 85.42% |
| **b05** | 45.94% | **87.68%** | 46.10% | 48.86% | 45.92% |
| b07 | 57.64% | **87.93%** | 57.64% | 57.57% | 57.64% |
| b08 | 91.99% | 91.09% | 91.99% | 91.99% | 91.99% |
| b09 | 86.56% | **87.85%** | 86.56% | 86.56% | 86.56% |

### Observations
- **Exp 2 (Two-Phase ON)** dominates — b05 jumps from 45.94% to **87.68%** (+41.74pp); b03 jumps from 44.50% to **85.41%** (+40.91pp)
- Exp 3, 4, 5 are nearly identical to Exp 1 across most circuits
- Two exceptions: b04 (−0.96pp) and b08 (−0.90pp) **slightly regress** with Two-Phase — likely because Phase 2 over-constrains justification in some topologies
- Exp 4 helps b04 (+4.15pp vs baseline) but **hurts** b03 (−2.84pp) — inconsistent, reinforcing that search heuristics don't reliably improve coverage

---

## Slide 12 — Ablation Results: ISCAS'89 Circuits

**B2 reference (full-scan):** s953=96.91%, s1196=98.27%, s1238=95.14%, s5378=94.74%

| Circuit | Exp 1 (Baseline) | **Exp 2 (Two-Phase)** | Exp 3 (Uni T1) | Exp 4 (EnBtr) | Exp 5 (StLrn) |
|---------|:----------------:|:---------------------:|:--------------:|:-------------:|:-------------:|
| **s953** | 37.40% | **91.26%** | 37.40% | 37.94% | 37.40% |
| s1196 | 98.40% | **98.40%** | 98.40% | 98.40% | 98.40% |
| s1238 | 95.12% | **95.12%** | 95.12% | 95.12% | 95.12% |
| s5378 | 91.86% | **94.97%** | 91.86% | 91.83% | 91.86% |

### s953 — the story in one circuit
- **Exp 1 (baseline):** gain = +0.65pp (T=1: 36.75%, T=4: 37.40%)
- **Exp 2 (Two-Phase ON):** gain = +54.51pp (T=1: 36.75%, T=4: **91.26%**)
- Without Two-Phase, T=2 recovers almost nothing. With Two-Phase, it recovers almost everything.

### ISCAS'89 takeaway
- s1196, s1238 already achieve high FC even without Two-Phase (their non-scan topology is favorable)
- s5378 improves from 91.86% → 94.97%, exceeding full-scan B2 (94.74%)

---

## Slide 13 — Ablation Summary

| Exp | Parameter | Avg FC | Avg Gain | **ΔFC vs Exp 1** |
|-----|-----------|:------:|:--------:|:---------------:|
| 1 | Baseline (T1=800, TP=OFF) | 73.48% | 10.10pp | — |
| 2 | **Two-Phase ON** | **90.42%** | **27.03pp** | **+16.94pp** |
| 3 | Uniform T1=5000 | 73.50% | 10.11pp | +0.02pp |
| 4 | Enhanced Backtrace | 73.95% | 10.32pp | +0.47pp |
| 5 | Static Learning | 73.48% | 10.09pp | +0.00pp |

### Only one experiment matters
- **Two-Phase State Justification: +16.94pp average improvement**
- The **T1 differential is NOT the mechanism** — uniform T1 changes FC by +0.02pp
- **Heuristics don't help** — enhanced backtrace (+0.47pp) and static learning (+0.00pp) are negligible

### What this means
The recovery is driven by **search structure** (Two-Phase decoupling), not search budget (backtrack limit) or search heuristics (backtrace selection, conflict detection).

---

## Slide 14 — Why Two-Phase Works

### The core insight
Two-Phase works because it **separates two fundamentally different search problems**:

| | Propagation (Phase 1) | Justification (Phase 2) |
|---|---|---|
| **Where** | Last frame (frame T−1) | Earlier frames (0..T−2) |
| **What** | Drive D-frontier to observable output | Assign non-scan FF values backward |
| **Blocked by** | Nothing (PPIs are free PIs) | Structural dependencies + backtrack budget |
| **Budget risk** | Low (just propagation) | Controlled (fresh budget per PPI) |

### Concrete example: s953
- s953 has 29 FFs, 3 non-scan at 10%
- At T=1, many fault propagation paths must pass through these 3 non-scan FFs → X blocks them → AU/AB
- **Standard TFE at T=2:** ATPG tries to simultaneously find a propagation path AND justify non-scan FF values → budget exhausted on propagation → AB
- **Two-Phase at T=2:**
  - Phase 1: treats non-scan FF PPIs as free → finds propagation path easily
  - Phase 2: backward-justifies the 3 required PPI values through frame 0 → succeeds
  - Result: fault is DT

### Why this fails at T=1
At T=1, there is **no earlier frame** to justify values from. The non-scan FF output is X and cannot be changed. Two-Phase needs T≥2 to work.

---

## Slide 15 — Why T=4 Adds Nothing

### With Two-Phase ON (Exp 2): T=4 gain = 0.00pp on every circuit
- T=2 with Two-Phase already recovers **all** recoverable faults
- The residual after T=2 consists of faults that are **structurally AU at any depth**
  - Example: fault's only observable path goes through a non-scan FF output
  - No amount of initialization cycles changes this structural fact

### Without Two-Phase (Exp 1, 3, 4, 5): T=4 adds modest gain
- b05: +16.69pp at T=4 (vs +0.16pp at T=2)
- b04: +5.33pp at T=4
- s5378: +2.68pp at T=4

This is NOT because these faults need 4 frames. It's because the **unified search at T=2 is inefficient** — it exhausts budget on propagation and leaves faults that a T=4 search happens to catch (more total budget across frames). With Two-Phase ON, these same faults are already caught at T=2.

### Takeaway
```
Without Two-Phase: T=2 inefficient → leftover faults → T=4 recovers some
With Two-Phase:    T=2 efficient → all recoverable faults caught → T=4 adds 0pp
```

**Frame depth is not the bottleneck — search structure is.**

---

## Slide 16 — Gap to Full-Scan

### With Two-Phase ON, the gap narrows dramatically

| Circuit | B1 (T=1) | B2 (full-scan) | Exp 2 | **Gap B2−Exp 2** |
|---------|:--------:|:--------------:|:-----:|:----------------:|
| b03 | 44.50% | 91.62% | 85.41% | **6.21pp** |
| b04 | 75.21% | 93.46% | 84.46% | **9.00pp** |
| b05 | 29.10% | 95.34% | 87.68% | **7.66pp** |
| b07 | 56.13% | 93.46% | 87.93% | **5.53pp** |
| b08 | 72.96% | 94.03% | 91.09% | **2.94pp** |
| b09 | 76.34% | 93.44% | 87.85% | **5.59pp** |
| s953 | 36.75% | 96.91% | 91.26% | **5.65pp** |
| s1196 | 86.13% | 98.27% | 98.40% | **−0.13pp** |
| s1238 | 82.42% | 95.14% | 95.12% | **0.02pp** |
| s5378 | 74.25% | 94.74% | 94.97% | **−0.23pp** |

**Average gap: 31.26pp (T=1) → 4.24pp (Two-Phase ON)**

### Why some circuits exceed full-scan
s1196 (−0.13pp) and s5378 (−0.23pp) exceed B2. Counter-intuitive: having **fewer** scan FFs with **more** time frames creates more propagation opportunities than all FFs scan at a single frame. The extra time frames compensate for the reduced controllability.

### Two sources of the remaining gap
1. **AU faults:** fault's only observable path passes through a non-scan FF — no sequential depth can fix this
2. **UD faults (Q pin — complementary/inverted output of scan FF):** stuck-at faults on the inverted output are excluded from ATPG at any depth

---

## Slide 17 — Limitations

1. **Backtrack limit sensitivity:** Results depend on the specific T1=800 / BACKTRACK=5000 choice. Different limits may change the residual profile.

2. **Single non-scan ratio (10%):** Only one exclusion ratio is evaluated. Results may differ at higher/lower ratios.

3. **Shallow depth:** T=8 not evaluated. However, T=4 adds 0pp with Two-Phase ON — deeper depth is unlikely to help.

4. **Single ATPG backend (FAN_ATPG):** Two-Phase effectiveness should be validated on other ATPG engines.

5. **10 benchmark circuits:** Results may not generalize to larger industrial designs. 5 more circuits (b11, b13, s9234, s15850, s35932) are pending due to runner/timeout issues.

6. **s27 sanity case** (smallest ISCAS'89 benchmark, 3 FFs): shows +43.9pp gain with the pipeline, confirming the residual targeting logic works. Not representative of scalable circuits — included as a smoke test only.

---

## Slide 18 — Conclusion

### Discovery narrative

| Step | Finding |
|------|---------|
| 1. T=1 (combinational) vs full-scan | **Average gap 31.26pp** — non-scan FF X-state kills coverage |
| 2. Try T=2, T=4 (sequential) | Baseline recovers 10.10pp, but **inconsistently** |
| 3. Ablation experiments | 5 experiments × 10 circuits to decompose the mechanism |
| 4. **Two-Phase is the mechanism** | +16.94pp vs baseline; uniform T1, heuristics all **negligible** |
| 5. Why T=4 is useless | Two-Phase at T=2 already exhausts all recoverable faults |
| 6. Gap to full-scan | Narrows from 31.26pp → **4.24pp** |

### Key numbers
| Metric | Value |
|--------|:-----:|
| Baseline (Exp 1) avg FC | 73.48% |
| **Two-Phase ON (Exp 2) avg FC** | **90.42%** |
| Average improvement vs baseline | **+16.94pp** |
| T=4 contribution (Two-Phase ON) | **0.00pp** |
| Remaining gap to full-scan | **4.24pp** |
| Best circuit (b05 T=2 gain) | **+58.49pp** |

### Summary
**Two-Phase State Justification** — decoupling propagation from justification — is the dominant recovery mechanism for sequential ATPG on timing-constrained partial-scan circuits. Neither the backtrack limit differential, enhanced backtrace, nor static learning produces meaningful improvement.

### Future work
- Complete remaining 5 circuits (background sweep, 600s timeout)
- Evaluate T=8 on select circuits
- Transition-delay fault model
- Industrial-scale benchmark evaluation
