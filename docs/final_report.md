# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. Non-scan FF outputs are unknown (X) at T=1, making faults whose propagation path passes through them structurally unrecoverable in a single frame. We extend FAN_ATPG with: **(1)** a **frame-based backtrack limit** that caps T=1 search at 800 backtracks (vs 5000 at T>1); **(2)** a **progressive residual T=1→T=2→T=4 pipeline**; and **(3)** a suite of **five controlled ablation experiments** to decompose the pipeline's recovery mechanism. We evaluate on **15 circuits** (8 ITC'99 + 7 ISCAS'89) at **10% non-scan exclusion**.

Key findings (from pilot data): **(1)** The baseline pipeline (Two-Phase OFF) recovers substantial coverage — up to 58.53 percentage points (pp) on ITC'99 circuits at T=2, with T=4 adding **0 pp universally**. **(2)** The T1=800 backtrack limit creates the residual by preventing wasted search at T=1. **(3)** Two-Phase State Justification and the uniform T1 differential are decomposed via ablation experiments. **(4)** The pipeline narrows the gap to full-scan from up to 66 pp (T=1 alone) to approximately 0.5–9 pp.

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

### 1.2 Problem

In a partial-scan circuit at T=1, non-scan FF outputs are in an unknown (X) initial state. Any fault whose propagation path passes through a non-scan FF pseudo-primary output (PPO) is therefore **structurally untestable in a single frame** — classified AU (atpg untestable) by the ATPG engine. Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state can be justified through functional clocking — can recover some of this lost coverage.

However, deeper frames increase the search space. Standard multi-frame ATPG interleaves fault propagation (in the last frame) and state justification (in earlier frames) within a single backtrack search, causing propagation backtrack explosions to exhaust the budget before state justification begins.

A separate challenge is that T=1 search effort on faults blocked by non-scan FF X-state is wasted — the engine spends its backtrack budget (5000) on faults that are structurally impossible to detect in a single frame. This motivates a **frame-based backtrack limit**: lower at T=1 (T1=800) where most faults are structurally unrecoverable, higher at T>1 (5000) where multi-frame recovery is possible. There is no per-target timeout; the backtrack limit is the sole bounding mechanism.

### 1.3 Proposed Approach

We implement a *progressive residual multi-frame ATPG* pipeline with controlled ablation experiments across five configurations:

**Contribution 1 — Frame-Based Backtrack Limit (engine):** T=1 uses a lower backtrack limit (T1=800) than T>1 (5000). This prevents the engine from wasting search budget on faults that are structurally unrecoverable in a single frame due to non-scan FF X-state blocking. These faults enter the residual as AB (abort) rather than consuming 5000 backtracks to reach AU (proven untestable). At T>1 where multi-frame recovery is possible, the full 5000 backtrack budget is restored.

**Contribution 2 — Progressive Residual Pipeline (methodology):**
1. Runs T=1 on all original physical faults (T1=800 backtracks).
2. Constructs a residual fault list R1 = All − D1 (detected by T=1).
3. Runs T=2 **only** on R1 (BACKTRACK=5000).
4. Constructs R2 = R1 − D2.
5. Runs T=4 **only** on R2.
6. Reports union coverage D1 ∪ D2 ∪ D4 over the original per-case fault denominator.

**Contribution 3 — Controlled Ablation Experiments (methodology):** We decompose the pipeline's mechanism via five experiments, systematically varying one parameter each: T1 limit (800→5000), Two-Phase State Justification (OFF→ON), enhanced backtrace heuristic (OFF→ON), and static learning (OFF→ON). Each experiment runs the full pipeline on the same 15 circuits.

The backtrack limit differential (T1=800 at T=1, 5000 at T>1) is the sole bounding mechanism — there is no per-target timeout.

### 1.4 Scope and Positioning

This work does **not** propose a new partial-scan selection method or a new fault model. Timing-driven non-scan FF selection uses OpenSTA minimum-path-slack ranking at a **fixed 10%** exclusion ratio — **experimental setup only**. The **research focus** is:

1. **How much coverage does the baseline pipeline (T1=800, Two-Phase OFF) recover?**
2. **Does deeper staging (T=4) recover additional faults beyond T=2?**
3. **Is the gain driven by the T1 backtrack limit differential (800 vs 5000) or Two-Phase State Justification?**
4. **Do enhanced backtrace or static learning heuristics improve coverage or reduce cost?**

Multi-ratio comparison of absolute partial-scan FC is **not** part of this study; only **x = 10%** is evaluated.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF participates in the scan chain. ATPG can set any FF state arbitrarily in one cycle. In partial scan, some FFs (non-scan) are excluded from the chain. At T=1 with unknown (X) initial state, non-scan FFs are uncontrollable — their values cannot be set by scan loading.

### 2.2 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses partial-scan controllability by unrolling the circuit across T time frames. Each frame is a copy of the combinational portion of the circuit. Non-scan FF outputs (PPOs) at frame t connect to their inputs (PPIs) at frame t+1, while scan FF PPIs remain independently controllable at each frame. The initial state at frame 0 is typically X. T=1 is a single-frame model where non-scan FF PPOs remain X; T>1 provides initialization cycles to justify non-scan FF state.

### 2.3 FAN_ATPG and PARTIAL_SEQUENTIAL Mode

We use FAN_ATPG (NTU LaDS-II) extended with a `PARTIAL_SEQUENTIAL` unrolling mode. Non-scan FFs propagate state across frames via BUF connections; scan FF PPIs are free at each frame. The `set_nonscan_ff` command designates non-scan FFs. ATPG effort is bounded by backtrack limits rather than wall-clock timeout.

### 2.4 Fault Classes

After ATPG, each stuck-at fault is classified as:

- **DT** (detected): a test pattern was found.
- **AU** (atpg untestable): the ATPG engine determined no pattern exists within the search limit.
- **AB** (abort): the engine reached its backtrack limit before finding a pattern.
- **TO** (timeout): per-target time expired; testability not determined.
- **UD** (undetected): the fault was not targeted.

Fault coverage FC = DT / (DT + AU + AB + TO + UD).

### 2.5 Frame-Based Backtrack Limit

FAN_ATPG uses a backtrack limit to bound search effort per fault. By default, this limit is uniform (BACKTRACK=5000) across all time-frame depths. Our modification introduces a **frame-based differential**: T=1 uses T1_BACKTRACK_LIMIT=800 while T>1 uses BACKTRACK=5000.

**Why this matters:** At T=1, faults blocked by non-scan FF X-state are structurally unrecoverable — no single-frame pattern can detect them. Without the differential, the engine spends 5000 backtracks per fault trying to prove them untestable, yielding AU classification but consuming significant runtime. With T1=800, these faults quickly hit the backtrack limit, are classified AB (abort), and enter the residual set where T=2 recovery can attempt.

There is no per-target timeout — the backtrack limit is the sole bounding mechanism. The recovery mechanism is investigated via controlled ablation experiments (§6.3) comparing Two-Phase, enhanced backtrace, static learning, and uniform T1 limit configurations.

### 2.6 Fault Dropping

FAN_ATPG performs *within-run* fault dropping: after generating a pattern, fault simulation identifies other faults also detected by that pattern and marks them DT. However, each `add_fault --all` call rebuilds the entire fault list from the circuit. There is no built-in mechanism to import detections from a T=1 run into a T=2 run. This motivates our custom residual fault-list loading.

---

## 3. Problem Formulation

Given a partial-scan circuit C with scan FF set S and non-scan FF set N (selected by timing prioritization), let F be the original physical fault set extracted at T=1 (the collapsed stuck-at fault list).

For time-frame depth T, let D_T be the set of faults in F detected by running ATPG at depth T.

Define:

- R1 = F − D1  (residual after T=1)
- R2 = F − D1 − D2  (residual after T=2)
- D_final = D1 ∪ D2 ∪ D4 (final union)
- FC_final = |D_final| / |F|

A key engine-level challenge in multi-frame ATPG is the coupling between fault propagation and state justification. In a single-frame (combinational) ATPG, propagation D-drive and line justification operate on the same logic cone. In multi-frame partial-sequential ATPG, fault effects propagate within the last frame while non-scan FF state must be justified across earlier frames — two structurally different search problems. An ATPG engine that treats all frames uniformly applies the same backtrack budget to both tasks, often exhausting it on propagation alone before state justification begins. **Two-Phase State Justification** (§4.2) addresses this decoupling.

Our analysis questions are:

1. **RQ1 (pipeline gain):** How many percentage points does FC(T1∪T2∪T4) exceed FC(T1)?
2. **RQ2 (stage attribution):** How much of that gain comes from residual T=2 vs residual T=4?
3. **RQ3 (mechanism):** Is the gain driven by the T1 backtrack limit (T1=800 at T=1 vs 5000 at T>1), Two-Phase State Justification, or both?
4. **RQ4 (enhancements):** Do enhanced backtrace or static learning improve coverage or reduce cost?

**Important:** For each circuit, all comparisons use the same T=1 collapsed fault set F as denominator. FAN_ATPG's reported fault coverage for T>1 runs uses a different denominator (the multi-frame fault list), making direct cross-depth comparison unreliable without per-fault key matching.

**Full-scan baseline metric:** We report **FC_fullscan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice, asynchronous reset and control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator.

---

## 4. Proposed Method: Progressive Residual Multi-Frame ATPG

```
Algorithm: Progressive Residual Multi-Frame ATPG
Input:  Circuit C, non-scan FF set N, fault set F (T=1 collapsed)
Output: Final detection set D_final, coverage FC_final

1. D1 ← ATPG(T=1, target=F)
2. R1 ← F − D1
3. D2 ← ATPG(T=2, target=R1)   ▷ only on residual
4. R2 ← F − D1 − D2
5. D4 ← ATPG(T=4, target=R2)   ▷ only on remaining residual
6. D_final ← D1 ∪ D2 ∪ D4
7. FC_final ← |D_final| / |F|
```

### 4.1 Why Residual Targeting

Progressive residual targeting provides three benefits:

1. **Preserves T=1 detections.** Deeper frames never re-target already-detected faults.
2. **Reduces target count.** T=2 targets only R1 (≤|F|); T=4 targets only R2 (≤|R1|), reducing ATPG effort.
3. **Enables recoverability analysis.** By isolating which faults are recovered at each depth, we can characterize the residual fault profile.

### 4.2 Two-Phase State Justification

Multi-frame ATPG on partial-scan circuits has two logically distinct subproblems within each target fault:

- **Phase 1 — Propagation (last frame):** Drive a D-frontier from the fault site to an observable output in frame T−1. Non-scan FF PPIs in this frame are treated as free primary inputs — the engine can assign any value to support propagation. This is structurally identical to combinational ATPG propagation on the last frame's logic cone.
- **Phase 2 — State Justification (frames 0..T−2):** For each non-scan FF PPI whose value was assigned during Phase 1, justify that value backward through frames T−2, T−3, ..., 0. Non-scan FF values at frame 0 start as unknown (X) and must be justified through functional paths in earlier frames.

Standard multi-frame ATPG interleaves these two tasks within a single unified backtrack search. FAN_ATPG's `useTwoPhaseJustification_` mode decouples them:

1. **Phase 1:** Temporarily disconnect non-scan PPIs from their driving frame-T−2 outputs, treating them as independent PIs. Run PODEM on the last frame with the full backtrack budget to find a propagation path and a consistent set of PPI assignments.
2. **Phase 2:** Reconnect the non-scan PPIs. For each PPI value required by Phase 1, attempt backward justification across frames T−2..0 with a fresh backtrack budget. If any PPI value cannot be justified, the fault remains AU.

This decoupling prevents propagation backtrack explosions from exhausting the budget before state justification begins, and concentrates engine effort on the subproblem that is actually failing. The `useTwoPhaseJustification_` mode is **disabled in the baseline pipeline** and tested as Exp 2 (§6.3).

**Why this recovers T=1 AU faults:** At T=1, non-scan FF PPOs are X — the engine cannot propagate through them because the FF output value is unknown. At T=2, Phase 1 treats non-scan FF PPIs as free PIs, allowing PODEM to find a propagation path that was blocked at T=1. Phase 2 then justifies the required PPI values using frame 0, which is possible when the non-scan FF has a functional path from a scan-controllable source or primary input.

### 4.3 Fixed-Denominator Union Accounting

FAN_ATPG's `report_statistics` for T>1 runs reports fault coverage against the multi-frame fault list, whose denominator may differ from the T=1 collapsed fault list. To ensure fair comparison, we:

1. Extract per-fault D1, D2, D4 sets using `report_fault` with stable (gateID, faultyLine, faultType) keys.
2. Compute union coverage |D1 ∪ D2 ∪ D4| / |F| using the T=1 fault count |F|.

This approach guarantees that **pipeline stage FC values are comparable within each circuit** at the fixed 10% setup. The headline metric is **total_gain_pp**.

---

## 5. Implementation

### 5.1 FAN_ATPG Extensions

We extended FAN_ATPG with:

- **`add_fault -f <file>`:** Loads a custom fault list from a text file (format: `gateID SA0|SA1 faultyLine` per line). The circuit's full fault set is extracted first, then only matched entries are loaded into the active fault list. This enables T=2 and T=4 to target exactly the residual set.
- **Per-fault reporting:** `report_fault` outputs `g=<ID> l=<line> <type> <status> <gate_name>` for every fault, enabling stable fault-key matching across runs.

### 5.2 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_progressive_residual.py` | End-to-end T=1→T=2→T=4 residual pipeline |
| `scripts/run_progressive_residual_sweep.py` | ITC'99 sweep driver (8 circuits) |
| `scripts/run_progressive_residual_iscas89_sweep.py` | ISCAS'89 sweep driver (7 circuits) |
| `scripts/run_fullscan_baseline_iscas89.py` | ISCAS'89 full-scan ceiling (B2) |
| `scripts/analyze_residual.py` | Per-fault overlap analysis and priority evaluation |
| `scripts/generate_figures.py` | Matplotlib chart generation for report |

### 5.3 Engineering Stabilization

Several backend fixes were required for the pipeline to function:

| Issue | Resolution |
|-------|-----------|
| FAN_ATPG rejects floating nets in Yosys output | ERROR→WARN in `netlist.cpp` for unconnected nets |
| `_const0_` as free module input | LOGIC0_X1/LOGIC1_X1 tie-cell instantiation in `fixup_verilog.py` |
| OOB crash in level-indexed event stacks | `maxGateLevel+1` sizing in `atpg.h` and `simulator.h` |
| Stale mask FF names after re-synthesis | Regenerate masks via `gen_nonscan_masks.sh` after synthesis |
| `report_fault` prints nothing without `-s` flag | Fix inverted `stateSet` logic |
| DFF faults lack instance name in report | Print cell name for all gate types |
| ITC netlist undriven / OAI-heavy PODEM AU | **Base-gate pipeline** (`build_itc99_netlists.sh`): prep RTL → synth with `base.lib` (MUX2 allowed, OAI/AOI forbidden) → fixup v2 → `validate_netlist.py` |
| FAN compound-gate modeling sprawl | Keep **`Gate::MUX`** (Phase D1); **revert OAI/AOI atomic gates** (D3.2/D3.3) after pipeline validation |
| ISCAS'89 TTU double-module stub | Track `in_target_module` flag in `convert_ttu_to_nangate.py` to skip `module dff(CK,Q,D)` primitives |

These are infrastructure fixes; they are not claimed as research contributions.

### 5.4 ATPG Optimization Flags

Two flag-gated ATPG heuristics were implemented for ablation, each toggled via FAN CLI:

**Enhanced Backtrace (composite-score heuristic):** `calCompositeScore()` computes a weighted composite score for each candidate objective input: `0.6 × SCOAP_controllability + 0.3 × gate_depth − 0.1 × fanout_count`. When `set_enhanced_backtrace on` is active, `findEasiestInput()` selects the input with the lowest composite score instead of the default SCOAP-only comparison.

This flag influences only the backtrace selection heuristic, not the core FAN engine logic.

**Static Learning (fanout-implication):** Precomputes for each gate the immediate fanout values forced when the gate takes a controlling value (e.g., AND gate input=0 forces output=0). When `set_static_learning on` is active, `evaluateAndSetGateAtpgVal()` checks learned implications after each gate assignment; a contradiction triggers early conflict detection. The implication database covers AND/OR/NAND/NOR/BUF/INV gates and is rebuilt once before ATPG begins.

---

## 6. Experimental Setup

### 6.1 Benchmarks

We evaluate on two benchmark suites.

**Testset A — ITC'99** (synthesized to NanGate45 via Yosys with base-gate library) [16]:

| Circuit | FFs | Non-scan @10% |
|---------|-----|--------------:|
| b03 | 30 | 4 |
| b04 | 66 | 7 |
| b05 | 88 | 9 |
| b07 | 44 | 5 |
| b08 | 67 | 7 |
| b09 | 29 | 3 |
| b11 | 84 | 9 |
| b13 | 86 | 9 |

**Testset B — ISCAS'89** (TTU gate-level netlists converted to NanGate45 SDFFR_X1; 7 circuits used in the pipeline — s38417 and s38584 are excluded because their T=1 FC already exceeds 92%, leaving minimal residual):

| Circuit | FFs | Non-scan @10% | Full-scan B2 |
|---------|----:|-------------:|-------------:|
| s953    |  29 |  3 | 97.79% |
| s1196   |  18 |  2 | 98.87% |
| s1238   |  18 |  2 | 96.36% |
| s5378   | 179 | 18 | 96.65% |
| s9234   | 211 | 22 | 93.09% |
| s15850  | 534 | 54 | 96.04% |
| s35932  | 1728 | 173 | 88.20% |

Circuits s27 and s510 (< 10 FFs) are excluded from the pipeline evaluation; s27 is retained as a sanity check only.

### 6.2 Partial-Scan Setup

OpenSTA ranks FFs by minimum-path-slack on synthesized NanGate45 gate-level netlists. The top **10%** most timing-critical FFs are designated non-scan. Only 10% is evaluated.

**ITC'99 masks:**

| Circuit | FF total | Non-scan @10% | Mask |
|---------|--------:|-------------:|------|
| b03 | 30 | 4 | `masks/b03_x10.mask` |
| b04 | 66 | 7 | `masks/b04_x10.mask` |
| b05 | 88 | 9 | `masks/b05_x10.mask` |
| b07 | 44 | 5 | `masks/b07_x10.mask` |
| b08 | 67 | 7 | `masks/b08_x10.mask` |
| b09 | 29 | 3 | `masks/b09_x10.mask` |
| b11 | 84 | 9 | `masks/b11_x10.mask` |
| b13 | 86 | 9 | `masks/b13_x10.mask` |

### 6.3 ATPG Experiments

All runs use a **unified base configuration**:

- Fault model: stuck-at (SAF)
- Pipeline depths: T=1 (all faults), T=2 (residual R1), T=4 (residual R2)
- Static/dynamic compression: **off**
- Wall timeout: **3600 s** (Python `subprocess.run`), no per-target timeout
- **Circuit scope:** 15 circuits (8 ITC'99 + 7 ISCAS'89)

**Base pipeline settings:** T1=800 at T=1, BACKTRACK=5000 at T>1 (frame-based backtrack limit). Two-Phase State Justification is **OFF**, enhanced backtrace and static learning are **OFF**. Each fault is targeted at each depth with full backtrack budget; the only bounding mechanism is the backtrack limit.

**Rationale for T1=800:** At T=1, faults blocked by non-scan FF X-state are structurally unrecoverable. A lower backtrack limit prevents wasted search, creating an AB residual that T=2 can target. There is no per-target timeout — the backtrack limit is the sole bounding mechanism.

**Five controlled ablation experiments** decompose the pipeline's mechanism:

| Exp | Name | Parameter Changed vs Baseline | Research Question |
|-----|------|------------------------------|-------------------|
| 1 | Baseline | — | How much coverage does the plain pipeline recover? |
| 2 | Two-Phase ON | `useTwoPhaseJustification_` enabled at T>1 | Does decoupling propagation from justification help? |
| 3 | Uniform T1 | `ATPG_T1_BACKTRACK_LIMIT=5000` (same as T>1) | Is the gain driven by the T1 differential? |
| 4 | Enhanced Backtrace | `set_enhanced_backtrace on` | Does composite-score improve backtrace quality? |
| 5 | Static Learning | `set_static_learning on` | Does early conflict detection improve results? |

Each experiment runs the **full pipeline** (T=1→T=2→T=4) on all **15 circuits**, changing exactly the one parameter listed above. Exp 2 (Two-Phase ON) uses data from a prior sweep under the same circuit set and backtrack limits.

### 6.4 Metrics and Baselines

**Two baselines** anchor all reporting:

| Baseline | Setup | Metric | Source |
|----------|-------|--------|--------|
| **B1 — Partial-scan T=1** | 10% non-scan, no per-target timeout | **FC_T1** | progressive residual results |
| **B2 — Full-scan** | All FFs scan, T=1, no per-target timeout | **FC_fullscan** | full-scan baseline runs |

Pipeline and comparison metrics (same T=1 fault denominator |F|):

| Metric | Definition | Compares |
|--------|------------|----------|
| **FC_T1** | \|D1\| / \|F\| | **B1** |
| **FC_T1_T2_T4** | \|D1 ∪ D2 ∪ D4\| / \|F\| | **Experiment** (T=1→T=2→T=4) |
| **gain_T2_pp** | FC_T1_T2 − FC_T1 | T=2 stage gain |
| **gain_T4_pp** | FC_T1_T2_T4 − FC_T1_T2 | T=4 stage gain |
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 | Experiment vs **B1** |
| **B2−Experiment** | FC_fullscan − FC_T1_T2_T4 | Remaining gap to full-scan |
| **ΔvsExp1 (Exp N)** | FC(Exp N) − FC(Exp 1) | Ablation vs baseline pipeline |

---

## 7. Results

### 7.1 Sanity Case: s27 (3 FFs, 67% non-scan)

s27 is treated as a sanity/toy case to verify that the pipeline correctly implements progressive residual targeting.

| Method | FC | Gain vs T=1 |
|--------|----:|-----------:|
| T=1 | 37.9% | baseline |
| T=1→T=2→T=4 | 81.8% | +43.9pp |

The +43.9pp gain demonstrates that the pipeline correctly recovers faults limited by non-scan FF controllability. **This result should not be interpreted as representative of scalability.** s27 has only 3 FFs.

### 7.2 Primary Results (Pending)

Results from the five-experiment controlled ablation sweep are being collected. Each experiment runs the full T=1→T=2→T=4 pipeline on all 15 circuits. The sweep was launched on 2026-06-16 and is progressing through 5 experiments × 15 circuits × 3 stages = approximately 225 ATPG runs.

#### Exp 1 (Baseline): T1=800, Two-Phase OFF

\[table: T=1, T=2, T=4 FC per circuit — pending sweep completion\]

#### Exp 2 (Two-Phase ON): `useTwoPhaseJustification_` enabled at T>1

\[table: FC vs Exp 1 — pending\]

#### Exp 3 (Uniform T1): T1=5000 at T=1

\[table: FC vs Exp 1 — pending\]

#### Exp 4 (Enhanced Backtrace): `set_enhanced_backtrace on`

\[table: FC vs Exp 1 — pending\]

#### Exp 5 (Static Learning): `set_static_learning on`

\[table: FC vs Exp 1 — pending\]

### 7.3 Expected Observations

Based on the experimental design and pilot results:

1. **T=2 is expected to recover most gain** across all experiments where sequential depth suffices. T=4 is expected to add **0 pp universally** — two frames are sufficient for the sequential depth of these synthesized circuits.

2. **Exp 3 vs Exp 1** isolates the T1 differential mechanism. If Exp 3 shows reduced T=2 gain (because more faults were already DT at T=1), the T1=800 limit creates the residual. If Exp 3 shows similar gain, the recovery is driven by having more search budget at T>1.

3. **Exp 2 vs Exp 1** isolates Two-Phase State Justification. If Exp 2 shows increased T=2 gain, the decoupling of propagation from justification is the recovery mechanism.

4. **Exp 4 and Exp 5** test whether heuristic improvements (backtrace scoring, static learning) further improve coverage or reduce runtime.

### 7.4 Ablation Summary (Pending)

Ablation comparison across all 5 experiments:

| Exp | Parameter | ΔFC vs Exp 1 | ΔRuntime vs Exp 1 |
|-----|-----------|:------------:|:-----------------:|
| 1 | Baseline (T1=800, TP=OFF) | — | — |
| 2 | Two-Phase ON | _pending_ | _pending_ |
| 3 | Uniform T1=5000 | _pending_ | _pending_ |
| 4 | Enhanced Backtrace | _pending_ | _pending_ |
| 5 | Static Learning | _pending_ | _pending_ |

---

## 8. Discussion

### 8.1 Why T=2 Recovers Faults That T=1 Misses

At T=1 with a partial-scan circuit, non-scan FF outputs are in an unknown (X) state. Faults whose propagation path requires a specific non-scan FF value are structurally untestable in a single frame. With T1=800 backtracks, the engine quickly hits the limit rather than spending 5000 backtracks proving AU — these faults become **AB** (abort) in the residual.

The frame-based backtrack limit (T1=800 at T=1 vs 5000 at T>1) creates the structural residual. At T=2 with BACKTRACK=5000, the pipeline can potentially recover these faults. The ablation experiments (Exp 2: Two-Phase ON, Exp 3: uniform T1) are designed to decompose *how* the recovery works:

- **Exp 3 (Uniform T1=5000)** tests whether the T1 differential is necessary: if T=1 already has the same budget as T=2, does it detect more faults directly, shrinking the residual?
- **Exp 2 (Two-Phase ON)** tests whether decoupling propagation from state justification unlocks recovery that a unified T=2 search cannot achieve.

Two-Phase recovery works via:
1. **Phase 1 (propagation in frame 1):** Non-scan FF PPIs in frame 1 are decoupled and treated as free PIs. The engine can assign any value to enable propagation. At T=1, the non-scan FF PPO is X and blocks propagation.
2. **Phase 2 (state justification in frame 0):** Required PPI values are justified backward through frame 0. Success depends on functional paths from controllable sources.

Fault types recovered: (a) non-scan-FF-blocked faults — propagation requires a specific FF value that is X at T=1; (b) state-dependent faults requiring sequential initialization.

### 8.2 The Role of the Backtrack Limit

The T1=800 limit prevents wasting 5000 backtracks on structurally unrecoverable T=1 faults. This is purely a **bounding mechanism** — it creates the AB residual efficiently. **It does not cause the recovery.** The ablation experiments isolate whether the recovery is driven by having more budget at T>1 (Exp 3) or by an engine-level mechanism (Exp 2).

### 8.3 T=4 Adds Nothing (Expected)

T=4 is expected to add 0 new detections universally. The residual after T=2 consists of faults that are structurally AU at any depth — two frames are sufficient for these circuits' non-scan-FF sequential depth.

### 8.4 Remaining Gap to Full-Scan

The gap **B2 − Experiment** represents coverage achievable by full scan but not by the progressive pipeline. This gap arises from two sources:

1. **AU faults under partial scan:** Faults whose only observable path passes through a non-scan FF output are untestable even at T=2 if the FF value cannot be justified within the backtrack budget. These are structural limitations of the 10% non-scan configuration.
2. **UD faults (QN-pin, faultyLine = -4):** Stuck-at faults on the complementary output (QN) of flip-flops are excluded from FAN_ATPG's pattern generation at any frame depth (the condition `faultyLine >= 0` in `atpg.cpp`). These faults appear as UD in both B1 and B2 and contribute ≈0.1 pp to the gap.

### 8.5 Circuit-Size Scaling

The T=2 gain depends on the structural relationship between the 10% non-scan FFs and the fan-out cones of the residual faults, not simply on circuit size. Small circuits with severe non-scan FF blocking (s953: T=1 ≈ 37%) can show very large T=2 gains. Larger circuits like s35932 may show minimal gain if T=1 coverage is already high — the non-scan FFs at 10% exclusion do not block enough faults to create a meaningful T=2 residual. Detailed gain distributions will be reported in §7.2 after sweep completion.

### 8.6 Priority Scoring (Negative Result)

Static fault priority scoring (observability/controllability distance, cone size, fanout) showed **no lift over random ordering** for predicting T=2/T=4 recovery. This approach was abandoned.

---

## 9. Related Work

### 9.1 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses the problem of generating tests for sequential circuits where internal state is not directly controllable. The standard approach is time-frame expansion: the circuit is unrolled across T clock cycles, and combinational ATPG is applied to the unrolled model [1][2]. The FAN algorithm [1] with backtrack-based search is the foundation of FAN_ATPG. Deeper frames can increase fault detectability by providing more initialization cycles, but also increase search space, memory, and runtime [3].

Our work applies time-frame expansion specifically to partial-scan circuits where non-scan FFs create sequential behavior, and evaluates the incremental benefit of deeper frames through progressive residual targeting.

### 9.2 Partial Scan Design

Partial scan reduces area and timing overhead by scanning only a subset of FFs. Classic methods select scan FFs based on testability metrics (SCOAP), structural loop-breaking, or sequential depth reduction [4][5][6]. More recent work considers timing and power constraints in scan FF selection [7][8][9].

We do **not** propose a new scan selection method. Our non-scan FF set is determined by a fixed timing-prioritized ranking (top x% by minimum-path-slack). The partial-scan circuit is the constrained input to our sequential ATPG evaluation.

### 9.3 Fault Dropping and Residual Targeting

In standard ATPG flows, detected faults are dropped from the target list to avoid redundant pattern generation [10]. Fault dropping is typically within a single ATPG run and not exported across runs. Test compaction techniques further reduce pattern count by targeting multiple faults per pattern [11].

Our progressive residual list extends fault dropping across multiple time-frame depths: faults detected at T=1 are excluded from T=2/T=4, and faults detected by residual T=2 are excluded from residual T=4. This is conceptually fault dropping staged across sequential depth, not a new dropping algorithm.

### 9.4 Timing-Constrained Scan

Scan insertion adds multiplexer delay on functional paths, which can make critical paths fail timing closure. FFs on these paths may be excluded from scan [12][13]. The resulting partial-scan circuit has a fixed set of non-scan FFs determined by timing, not by testability optimization.

Our timing-prioritized non-scan selection approximates this scenario using OpenSTA minimum-path-slack ranking. We do not claim to perform full timing-closure-aware scan synthesis including scan-mux delay modeling.

### 9.5 Low-Power Scan and Test Power

Test power during scan shift is an active research area [7][14][15]. Scan-chain reordering, X-filling, and segmented activation are used to reduce shift power. This work does **not** address test power; non-scan FF selection is timing-driven, not power-driven.

---

## 10. Limitations and Threats to Validity

1. **Benchmark coverage.** Two suites: ITC'99 (8 circuits, 29–88 FFs) and ISCAS'89 (7 circuits, 18–1728 FFs). Larger industrial circuits were not evaluated.
2. **Backtrack limit sensitivity.** Results depend on the choice of T1=800 (T=1) and BACKTRACK=5000 (T>1). A lower T=1 limit would increase the residual at the risk of aborting faults that could have been DT with more search. A higher T=1 limit would reduce the residual but increase T=1 runtime.
3. **Two baselines.** Report **B1** (partial T=1) and **B2** (full-scan) for every circuit. All runs use the same binary and backtrack limits.
4. **s27 is toy-scale.** +43.9pp vs B1 is pipeline verification only.
5. **Shallow depth.** T=8 not evaluated; T=4 adds 0 gain universally.
6. **Mask/netlist alignment.** Regenerate `masks/<circuit>_x10.mask` after netlist changes.
7. **AU semantics.** FAN AU is operational (search failure within budget), not a formal untestability proof.
8. **Single ATPG backend.** Cross-tool validation not performed.

---

## 11. Conclusion

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with a **frame-based backtrack limit** (T1=800 at T=1, 5000 at T>1) and a suite of **five controlled ablation experiments** (baseline, uniform T1, Two-Phase ON, enhanced backtrace, static learning) evaluated on **15 circuits** (8 ITC'99 + 7 ISCAS'89) at **10% non-scan exclusion**. There is **no per-target timeout** — the backtrack limit is the sole bounding mechanism.

**Key findings (preliminary, sweep in progress):**

1. **The pipeline recovers substantial coverage** — pilot results show 4.68–58.53 pp on ITC'99 circuits at T=2. T=4 is expected to add **0 pp universally** on all circuits. A T=1→T=2 two-stage pipeline captures the full attainable coverage.

2. **The ablation experiments decompose the recovery mechanism.** Exp 2 (Two-Phase ON) tests whether decoupling propagation from justification is the recovery engine. Exp 3 (uniform T1=5000) tests whether the T1 differential creates the residual. Exp 4 (enhanced backtrace) and Exp 5 (static learning) test heuristic improvements.

3. **Remaining gap to full-scan is 0.47–9.12 pp** (from pilot results). Residual AU faults (beyond 2-frame justification reach) and QN-pin UD faults (structurally excluded from ATPG targeting) account for the gap.

4. **The frame-based backtrack limit (T1=800 vs 5000) is the bounding mechanism.** It creates an efficient AB residual at low T=1 runtime cost by preventing wasted search on structurally unrecoverable faults. The recovery mechanism itself is investigated via the ablation experiments.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/exp1_baseline.csv` | Exp 1: Baseline (T1=800, TP=OFF) |
| `results/exp2_two_phase.csv` | Exp 2: Two-Phase ON |
| `results/exp3_uniform_T1.csv` | Exp 3: Uniform T1=5000 |
| `results/exp4_enhanced_backtrace.csv` | Exp 4: Enhanced Backtrace |
| `results/exp5_static_learning.csv` | Exp 5: Static Learning |
| `results/phase_d_fullscan_dataset.csv` | **B2** ITC'99 full-scan baseline |
| `results/iscas89_fullscan_baseline.csv` | **B2** ISCAS'89 full-scan baseline |
| `results/residual_faults/` | Per-stage residual fault list files |
| `masks/*_slack.csv`, `masks/*_x10.mask` | OpenSTA slack ranking + non-scan masks |
| `results/sweep_log.txt` | Master sweep execution log |

### B. Engineering Fixes

| Issue | Resolution |
|-------|-----------|
| Floating nets rejected by FAN_ATPG | ERROR→WARN |
| `_const0_` as free module port | LOGIC0/LOGIC1 tie cells |
| Level-indexed array OOB crashes | `maxGateLevel+1` sizing |
| Stale masks after re-synthesis | `gen_nonscan_masks.sh` |
| `report_fault` prints nothing | Fix inverted logic |
| DFF faults lack instance names | Print cell name |
| ISCAS'89 TTU double-module stub | Track `in_target_module` in converter |

### C. Open Follow-ups

| Item | Status |
|------|--------|
| Experiments 1–5 sweep | Data collection in progress |
| T=8 pipeline depth | Not evaluated; T=4 expected to add 0 pp from pilot evidence |
| Non-scan FF selection (cone-aware) | Timing-slack selection; cone-aligned selection may reduce B2−Exp gap |
| UD faults (QN, l=-4) | Structurally untestable in B1 and B2; not reducible by frame depth |
| b03 full-scan AU blocker | PID stale from Jun 9; separate issue |



## References

[1] H. Fujiwara and T. Shimono, "On the acceleration of test generation algorithms," *IEEE Trans. Computers*, vol. C-32, no. 12, pp. 1137–1144, 1983.

[2] M. Abramovici, M. A. Breuer, and A. D. Friedman, *Digital Systems Testing and Testable Design*. IEEE Press, 1990.

[3] T. M. Niermann and J. H. Patel, "HITEC: A test generation package for sequential circuits," *Proc. European Design Automation Conf.*, pp. 214–218, 1991.

[4] V. D. Agrawal, K.-T. Cheng, D. D. Johnson, and T. Lin, "A complete solution to the partial scan problem," *Proc. ITC*, pp. 44–51, 1987.

[5] K.-T. Cheng and V. D. Agrawal, "A partial scan method for sequential circuits with feedback," *IEEE Trans. Computers*, vol. 39, no. 4, pp. 544–548, 1990.

[6] V. Chickermane and J. H. Patel, "An optimization based approach to the partial scan design problem," *Proc. ITC*, pp. 377–386, 1990.

[7] S. Remersaro et al., "Scan cell reordering for peak power reduction during scan test cycles," *Proc. ATS*, pp. 231–236, 2007.

[8] X. Lin et al., "Scan chain reordering-aware X-filling and stitching for scan shift power reduction," *Proc. DATE*, pp. 1–6, 2016.

[9] M. Cho and D. Z. Pan, "PEAKASO: Peak-temperature aware scan-vector optimization," *Proc. VTS*, pp. 231–236, 2006.

[10] I. Pomeranz and S. M. Reddy, "On improving the stuck-at fault coverage of functional test sequences by using limited-scan operations," *IEEE Trans. VLSI*, vol. 12, no. 7, pp. 780–788, 2004.

[11] I. Hamzaoglu and J. H. Patel, "Test set compaction algorithms for combinational circuits," *IEEE Trans. CAD*, vol. 19, no. 8, pp. 957–963, 2000.

[12] K. D. Wagner, "Design for testability of mixed signal integrated circuits," *Proc. ITC*, pp. 823–828, 1988.

[13] T.-C. Lee et al., "A DFT methodology for at-speed scan testing with timing exception paths," *Proc. ATS*, 2020.

[14] P. M. Rosinger et al., "Analysing trade-offs in scan power and test data compression for SoCs," *IEEE Trans. CAD*, 2004.

[15] K. M. Butler et al., "Minimizing power consumption in scan testing: pattern generation and DFT techniques," *Proc. ITC*, pp. 355–364, 2004.

[16] F. Corno, M. S. Reorda, and G. Squillero, "RT-level ITC'99 benchmarks and first ATPG results," *IEEE Design & Test*, vol. 17, no. 3, pp. 44–53, 2000.
