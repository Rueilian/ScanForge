# Sequential ATPG with Progressive Residual Targeting on Timing-Constrained Partial-Scan Circuits

## Final Course Project Report

**Course:** EEE5001 VLSI Testing — Group 5
**Members:** 丁睿濂, 駱彥竹, 黃思維
**Date:** June 2026

---

## Abstract

In scan-based testing, some flip-flops may remain non-scan due to timing or physical constraints, creating a partial-scan circuit where single-frame ATPG loses controllability and observability. We implement a *progressive residual multi-frame ATPG* pipeline on FAN_ATPG: run T=1 on all faults, target only the residual set at T=2, then target the remaining residual at T=4, and report union coverage FC(T1∪T2∪T4) over the fixed T=1 fault denominator. **The primary evaluation question is how much each pipeline stage adds beyond T=1**, not how fault coverage varies across different non-scan exclusion ratios.

On the sanity case s27 (3 FFs, 67% non-scan), the pipeline recovers +43.9pp (37.9% → 81.8%), confirming correct sequential residual handling. On Tier A ITC'99 benchmarks with regenerated OpenSTA masks aligned to our gate-level netlists (June 2026 sweep), T=1 already achieves 87.6–96.5% FC at the canonical 20% timing-exclusion setting; **only b03 shows measurable pipeline gain (+2.16pp, entirely from T=2; T=4 adds 0)**. All other evaluated Tier A circuits show 0.00pp gain from T=2 and T=4 at every tested exclusion setting (5/10/15/20%). A **Tier B pilot** (b12/b14 @20%, June 2026) shows large T=2-driven gains (+35.4 pp and +13.0 pp) on larger partial-scan instances, while b15 T=1 exceeds a 2 h wall limit. We conclude that the progressive pipeline is a sound analysis framework whose practical benefit appears when T=1 partial-scan FC leaves a substantial residual gap.

---

## 1. Introduction

### 1.1 Motivation

Full-scan design grants ATPG direct controllability and observability over all flip-flops, enabling high single-frame stuck-at fault coverage. In practice, however, a subset of FFs may remain non-scan: converting them to scan cells would add multiplexer delay on timing-critical paths, pushing slack negative. Once these FFs are fixed as non-scan, the circuit becomes a *partial-scan* design, and single-frame ATPG loses coverage because non-scan FFs are not freely controllable nor directly observable.

### 1.2 Problem

Multi-frame sequential ATPG — unrolling the circuit across multiple time frames so that non-scan FF state propagates through functional clocking — can recover some of this lost coverage. However, deeper frames increase the search space and may not benefit every fault. Furthermore, naive deeper-frame ATPG on all faults can underperform T=1 if the larger search space causes abort explosions or if pattern storage/simulation fidelity is imperfect for multi-frame circuits.

### 1.3 Proposed Approach

We implement a *progressive residual multi-frame ATPG* flow that:

1. Runs T=1 on all original physical faults.
2. Constructs a residual fault list R1 = All − D1 (detected by T=1).
3. Runs T=2 **only** on R1.
4. Constructs R2 = R1 − D2.
5. Runs T=4 **only** on R2.
6. Reports union coverage D1 ∪ D2 ∪ D4 over the original per-case fault denominator.

This approach preserves T=1 detections, reduces the number of faults targeted at T=2/T=4, and enables a controlled analysis of which residual faults are recoverable by increasing time-frame depth.

### 1.4 Scope and Positioning

This work does **not** propose a new ATPG search algorithm, a new partial-scan selection method, or a new fault model. Timing-driven non-scan FF selection (OpenSTA minimum-path-slack ranking at fixed ratios 5/10/15/20%) is **experimental setup only**: it produces realistic partial-scan circuits. The **research focus** is:

1. **Does the progressive T=1→T=2→T=4 pipeline increase fault coverage beyond T=1 alone?**
2. **At which stage (T=2 vs T=4) are residual faults recovered, if at all?**
3. **What is the runtime cost of each stage relative to the coverage gain?**

Cross-ratio comparison of absolute partial-scan FC is **not** a research question; ratios are repeated experimental conditions for the same pipeline evaluation.

---

## 2. Background

### 2.1 Full Scan vs. Partial Scan

In full-scan design, every FF participates in the scan chain. ATPG can set any FF state arbitrarily in one cycle. In partial scan, some FFs (non-scan) are excluded from the chain. At T=1 with unknown (X) initial state, non-scan FFs are uncontrollable — their values cannot be set by scan loading.

### 2.2 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses partial-scan controllability by unrolling the circuit across T time frames. Each frame is a copy of the combinational portion of the circuit. Non-scan FF outputs (PPOs) at frame t connect to their inputs (PPIs) at frame t+1, while scan FF PPIs remain independently controllable at each frame. The initial state at frame 0 is typically X. T=1 is a single-frame no-recovery model; T>1 provides initialization cycles to justify non-scan FF state.

### 2.3 FAN_ATPG and PARTIAL_SEQUENTIAL Mode

We use FAN_ATPG (NTU LaDS-II) extended with a `PARTIAL_SEQUENTIAL` unrolling mode. Non-scan FFs propagate state across frames via BUF connections; scan FF PPIs are free at each frame. The `set_nonscan_ff` command designates non-scan FFs.

### 2.4 Fault Classes

After ATPG, each stuck-at fault is classified as:

- **DT** (detected): a test pattern was found.
- **AU** (atpg untestable): the ATPG engine determined no pattern exists.
- **AB** (abort): the engine reached its backtrack limit before finding a pattern.
- **UD** (undetected): the fault was not targeted.

Fault coverage FC = DT / (DT + AU + AB + UD).

### 2.5 Fault Dropping

FAN_ATPG performs *within-run* fault dropping: after generating a pattern, fault simulation identifies other faults also detected by that pattern and marks them DT. Detected faults are skipped in subsequent pattern generation. However, each `add_fault --all` call rebuilds the entire fault list from the circuit. There is no built-in mechanism to import detections from a T=1 run into a T=2 run. This motivates our custom residual fault-list loading.

---

## 3. Problem Formulation

Given a partial-scan circuit C with scan FF set S and non-scan FF set N (selected by timing prioritization), let F be the original physical fault set extracted at T=1 (the collapsed stuck-at fault list).

For time-frame depth T, let D_T be the set of faults in F detected by running ATPG at depth T.

Define:

- R1 = F − D1  (residual after T=1)
- R2 = F − D1 − D2  (residual after T=2)
- D_final = D1 ∪ D2 ∪ D4 (final union)
- FC_final = |D_final| / |F|

Our analysis questions are:

1. **RQ1 (pipeline gain):** For a fixed partial-scan circuit, how many percentage points does FC(T1∪T2∪T4) exceed FC(T1)?
2. **RQ2 (stage attribution):** How much of that gain comes from residual T=2 vs residual T=4?
3. **RQ3 (cost):** What are the T=1 / T=2 / T=4 runtimes, and is deeper staging justified by recovered fault count?

Secondary baselines (direct T=4 on residuals, naive T=4-all) support interpretation but are not the headline metric.

**Important:** For each (circuit, ratio) case, all comparisons use the same T=1 collapsed fault set F as denominator. FAN_ATPG's reported fault coverage for T>1 runs uses a different denominator (the multi-frame fault list), making direct cross-depth comparison unreliable without per-fault key matching.

**Full-scan baseline metric (2026-06-09):** We report **FC_scan** as the primary stuck-at coverage for `ratio=0` full-scan runs. Per commercial DFT practice (Cummings, SNUG 2002), async reset/control primary inputs are held inactive during scan ATPG and their stuck-at faults are classified as tied (TI), excluded from the scan-protocol denominator. Raw fault coverage (FC_raw), which treats reset as a free PI, is reported in the appendix only. Implementation: FAN applies scan protocol automatically after `add_fault --all` (overridable via `set_scan_protocol off`); see `docs/archive/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md`.

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

**Baselines for comparison:**

- **Naive T=4-all:** ATPG(T=4, target=F). Run T=4 on all original faults.
- **Union(T=1, T=4-all):** D1 ∪ D4_all. Tests whether multi-frame detection adds beyond T=1.
- **T=1→T=4 residual:** ATPG(T=4, target=R1). Skips T=2 to test whether T=2 is necessary.

### 4.1 Why Residual Targeting

Progressive residual targeting provides three benefits:

1. **Preserves T=1 detections.** Deeper frames never re-target already-detected faults.
2. **Reduces target count.** T=2 targets only R1 (≤|F|); T=4 targets only R2 (≤|R1|), reducing ATPG effort.
3. **Enables recoverability analysis.** By isolating which faults are recovered at each depth, we can characterize the residual fault profile.

### 4.2 Fixed-Denominator Union Accounting

FAN_ATPG's `report_statistics` for T>1 runs reports fault coverage against the multi-frame fault list, whose denominator may differ from the T=1 collapsed fault list. To ensure fair comparison, we:

1. Extract per-fault D1, D2, D4 sets using `report_fault` with stable (gateID, faultyLine, faultType) keys.
2. Compute union coverage |D1 ∪ D2 ∪ D4| / |F| using the T=1 fault count |F|.

This approach guarantees that **pipeline stage FC values are comparable within each (circuit, x) case**. Cross-ratio absolute FC is reported only as secondary replication; the headline metric is **total_gain_pp** at each x (canonical: 20%).

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
| `scripts/analyze_residual.py` | Per-fault overlap analysis and priority evaluation |
| `scripts/rank_residual_faults.py` | Netlist-based fault priority scoring (negative result, preserved) |
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

These are infrastructure fixes; they are not claimed as research contributions.

---

## 6. Experimental Setup

### 6.1 Benchmarks

| Circuit | Source | FFs | Role |
|---------|--------|-----|------|
| s27 | ISCAS'89 | 3 | Sanity / pipeline verification |
| b07 | ITC'99 | 45 | Stress case |
| b13 | ITC'99 | 65 | Stress case |

s27 has only 3 FFs and serves as a sanity check. b07 and b13 are the primary stress cases. ITC'99 circuits are synthesized to NanGate45 gate-level Verilog using Yosys.

### 6.2 Partial-Scan Setup (Not the Primary Variable)

OpenSTA ranks FFs by minimum-path-slack on our synthesized NanGate45 gate-level netlists. The top x% most timing-critical FFs are designated non-scan. Masks were **regenerated June 2026** (`scripts/gen_nonscan_masks.sh`, OpenSTA 3.1.0, `FAN_ATPG/mod_netlist/b*.v`).

We evaluate the **same T=1→T=2→T=4 pipeline** at x ∈ {5%, 10%, 15%, 20%} as repeated conditions. The **canonical reporting point** for cross-circuit comparison is **x = 20%** (largest non-scan set per circuit while keeping Tier A sweep manageable).

| Circuit | FF total (approx.) | Non-scan @20% | Mask source |
|---------|-------------------:|--------------:|-------------|
| b03 | 30 | 7 | `masks/b03_x20.mask` |
| b04 | 66 | 14 | `masks/b04_x20.mask` |
| b05 | 88 | 18 | `masks/b05_x20.mask` |
| b07 | 44 | 9 | `masks/b07_x20.mask` |
| b08 | 67 | 6 | `masks/b08_x20.mask` |
| b09 | 29 | 6 | `masks/b09_x20.mask` |
| b11 | 84 | 12 | `masks/b11_x20.mask` |
| b13 | 86 | 13 | `masks/b13_x20.mask` |
| b12 | 220 | 44 | `masks/b12_x20.mask` |
| b14 | 314 | 63 | `masks/b14_x20.mask` |
| b15 | 837 | 168 | `masks/b15_x20.mask` |

Tier B circuits (b12, b14, b15) use the same mask policy but were evaluated in a **separate pilot** (June 2026) after FAN_ATPG engine fixes; they are not part of the primary 32-run Tier A sweep.

### 6.3 ATPG Configuration

- Fault model: stuck-at (SAF)
- Pipeline depths: T=1 (all faults), T=2 (residual R1), T=4 (residual R2)
- Static/dynamic compression: off (progressive residual runner)
- Two-phase ATPG + state justification: **on by default** in FAN_ATPG (engine optimizations; not the measured independent variable)
- Wall timeout: 3600 s (Tier A); 7200 s for Tier B pilot (b15)
- Per-target timeout: 0 s (Tier A sweep); 30 s (Tier B pilot)
- Results file: `results/progressive_residual_summary.csv` (32 Tier A runs + 2 Tier B pilot rows @20%)

### 6.4 Metrics (Pipeline-Centric)

| Metric | Definition |
|--------|------------|
| **FC_T1** | \|D1\| / \|F\| — single-frame partial-scan baseline |
| **FC_T1_T2** | \|D1 ∪ D2\| / \|F\| — union after residual T=2 |
| **FC_T1_T2_T4** | \|D1 ∪ D2 ∪ D4\| / \|F\| — final pipeline union |
| **gain_T2_pp** | FC_T1_T2 − FC_T1 |
| **gain_T4_pp** | FC_T1_T2_T4 − FC_T1_T2 |
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 |
| **T1_rt / T2_rt / T4_rt** | Wall time per stage (seconds) |

Full-scan FC_scan baselines (ratio = 0%) are reported separately in `results/phase_d_fullscan_dataset.csv` for context only.

---

## 7. Results

### 7.1 Sanity Case: s27 (3 FFs, 67% non-scan)

s27 is treated as a sanity/toy case to verify that the pipeline correctly implements progressive residual targeting.

| Method | FC | Gain vs T=1 |
|--------|----:|-----------:|
| T=1 | 37.9% | baseline |
| T=1→T=4 residual | 81.8% | +43.9pp |
| T=1→T=2→T=4 | 81.8% | +43.9pp |

The +43.9pp gain demonstrates that the pipeline correctly recovers faults whose detection is limited by sequential controllability of non-scan FFs. T=2 and T=4 recover the same faults in the same order; T=1→T=4 (skipping T=2) achieves identical union coverage.

**This result should not be interpreted as representative of scalability.** s27 has only 3 FFs and its residual fault profile is favorable for sequential recovery.

### 7.2 Primary Result: T-Stage Pipeline Gain (@20% Non-Scan)

**Data source:** `results/progressive_residual_summary.csv`, first complete sweep after mask regeneration (June 2026). Denominator |F| is the T=1 collapsed fault count for each case.

| Circuit | Excl FFs | \|F\| | FC T=1 | FC T1∪T2 | FC T1∪T2∪T4 | ΔT2 (pp) | ΔT4 (pp) | **Total gain** | T1 (s) | T2 (s) | T4 (s) |
|---------|--------:|------:|-------:|---------:|-------------:|---------:|---------:|---------------:|-------:|-------:|-------:|
| b03 | 7 | 833 | 88.36% | 90.52% | 90.52% | +2.16 | 0.00 | **+2.16** | 0.01 | 0.01 | 0.01 |
| b04 | 14 | 2347 | 87.60% | 87.60% | 87.60% | 0.00 | 0.00 | 0.00 | 3.91 | 2.54 | 3.36 |
| b05 | 18 | 4562 | 92.81% | 92.81% | 92.81% | 0.00 | 0.00 | 0.00 | 0.68 | 0.77 | 1.09 |
| b07 | 9 | 1631 | 93.50% | 93.50% | 93.50% | 0.00 | 0.00 | 0.00 | 0.01 | 0.01 | 0.01 |
| b08 | 6 | 2290 | 92.75% | 92.75% | 92.75% | 0.00 | 0.00 | 0.00 | 0.04 | 0.01 | 0.01 |
| b09 | 6 | 954 | 87.63% | 87.63% | 87.63% | 0.00 | 0.00 | 0.00 | 0.02 | 0.02 | 0.02 |
| b11 | 12 | 6909 | 96.54% | 96.54% | 96.54% | 0.00 | 0.00 | 0.00 | 66.92 | 88.66 | 121.20 |
| b13 | 13 | 2079 | 87.59% | 87.59% | 87.59% | 0.00 | 0.00 | 0.00 | 0.02 | 0.01 | 0.01 |

![T-stage union coverage at 20% non-scan](figures/coverage_bar_chart.png)

*Figure 1: Primary metric — union fault coverage after each pipeline stage (20% timing-exclusion setting).*

![New detections at T=2 and T=4](figures/recovered_faults_chart.png)

*Figure 2: Count of newly detected faults at each residual stage (20% setting).*

#### Case study: b03 @20% (only positive pipeline gain)

| Stage | New DT | Union FC | Notes |
|-------|-------:|---------:|-------|
| T=1 | 736 | 88.36% | 97 residual targets |
| T=2 | **+18** | **90.52%** | entire +2.16pp gain |
| T=4 | +0 | 90.52% | no additional recovery |

### 7.3 Pipeline Gain vs Exclusion Ratio (Secondary)

The table below confirms that **pipeline gain is flat (0 pp) at 5/10/15% for all circuits**; only **b03 @20%** shows non-zero gain. This supports treating ratio as setup variation, not the main experimental axis.

| Circuit | 5% gain | 10% gain | 15% gain | 20% gain |
|---------|--------:|---------:|---------:|---------:|
| b03 | 0.00 | 0.00 | 0.00 | **+2.16** |
| b04 | 0.00 | 0.00 | 0.00 | 0.00 |
| b05 | 0.00 | 0.00 | 0.00 | 0.00 |
| b07 | 0.00 | 0.00 | 0.00 | 0.00 |
| b08 | 0.00 | 0.00 | 0.00 | 0.00 |
| b09 | 0.00 | 0.00 | 0.00 | 0.00 |
| b11 | 0.00 | 0.00 | 0.00 | 0.00 |
| b13 | 0.00 | 0.00 | 0.00 | 0.00 |

### 7.4 Tier B Pilot (@20% Non-Scan)

**Data source:** Manual progressive-residual runs (June 14, 2026) on deferred Tier B circuits after rebuilding FAN_ATPG (`make clean MODE=opt && make -j`). Configuration: `per_target_timeout=30 s`, two-phase ATPG + state justification on (engine default). Prior documented failures (segfault, 120 s timeout) were observed with a stale binary; a clean rebuild was required before these runs.

| Circuit | Excl FFs | \|F\| | FC T=1 | FC T1∪T2 | FC T1∪T2∪T4 | ΔT2 (pp) | ΔT4 (pp) | **Total gain** | T1 (s) | T2 (s) | T4 (s) | Status |
|---------|--------:|------:|-------:|---------:|-------------:|---------:|---------:|---------------:|-------:|-------:|-------:|--------|
| b12 | 44 | 7678 | 39.40% | 74.82% | 74.82% | +35.43 | 0.00 | **+35.43** | 0.15 | 911.4 | 771.0 | PASS |
| b14 | 63 | 16876 | 74.67% | 87.64% | 87.64% | +12.97 | 0.00 | **+12.97** | 390.9 | 299.0 | 294.7 | PASS |
| b15 | 168 | — | — | — | — | — | — | — | **>7200** | — | — | T=1 TIMEOUT |

**Full-scan T=1 baseline (pilot, same rebuild):** b14 completed in **417 s** with **94.64% FC_scan** (vs. **1721 s** in the June 2026 `phase_d_fullscan_dataset.csv` entry for the same netlist).

**Interpretation:** Unlike Tier A, b12 and b14 show **large pipeline gains** driven entirely by T=2 (+35.4 pp and +13.0 pp). T=4 adds no further detections on either circuit. Multi-frame runtime is **16–28 min** end-to-end — previously these circuits segfaulted or exceeded short timeouts. **b15** remains impractical: T=1 alone did not finish within a 2 h wall limit.

Reproduce:

```bash
cd FAN_ATPG && make clean MODE=opt && make -j$(nproc) && cd ..
python3 scripts/run_progressive_residual.py --circuit b12 --ratio 0.20 \
  --nonscan "$(tr '\n' ' ' < masks/b12_x20.mask)" --timeout 3600 --per-target-timeout 30
```

### 7.5 Key Observations

1. **T=1 dominates.** With aligned masks and current FAN_ATPG, partial-scan T=1 FC is already 87.6–96.5% at 20% exclusion — close to full-scan baselines in `phase_d_fullscan_dataset.csv` (91–97% FC_scan). The pipeline question becomes: *can T=2/T=4 recover the remaining gap?*

2. **Pipeline gain is rare on Tier A.** Only **b03 @20%** benefits (+2.16pp, all from T=2). Every other (circuit, ratio) pair shows **0.00pp** total gain.

3. **T=4 does not help at current depth.** Even when T=2/T=4 runtimes are large (b11: 67s + 89s + 121s), **T4_new_DT = 0** everywhere in the sweep.

4. **High T=1 FC does not imply low runtime.** b11 T=1 FC is 96.54% but T=1 alone takes ~67s due to fault count (~6909) and search cost; pipeline stages add ~210s with zero coverage return.

5. **Prior draft results superseded.** Earlier report tables showing b07/b13 T=1 FC in the 40–66% range and +8–12pp pipeline gain used **stale non-scan masks** (wrong FF instance names after netlist rebuild). After OpenSTA mask regeneration on our gate-level netlists, b07/b13 T=1 FC recovers to ~93%/88% with **0 pp pipeline gain**.

6. **Tier B behaves differently from Tier A.** b12/b14 have lower partial-scan T=1 FC and substantial T=2 recovery (+35.4 pp / +13.0 pp @20%), but at **16–28 min** wall time per case. b15 did not complete T=1 within 2 h. Tier B is suitable for pipeline **case studies**, not batch sweeps, until b15 runtime is addressed.

### 7.6 Denominator and Coverage Accounting

FAN_ATPG's `report_statistics` for multi-frame circuits reports fault counts against a fault list that may differ from the T=1 collapsed list. We observed that the T=4-all reported fault total sometimes exceeds the T=1 total (more gates → more faults), making direct FC comparison unreliable across depths.

Our union coverage is computed externally using stable fault keys (gateID, faultyLine, faultType) extracted from `report_fault` output, always normalized to the T=1 collapsed fault count as denominator. This ensures:

- Within each (circuit, ratio) case, all stage-wise FC values are comparable.
- Cross-ratio and cross-circuit comparisons should be interpreted with care, as denominators and fault profiles differ.

---

## 8. Discussion

### 8.1 When the T=1→T=2→T=4 Pipeline Helps

The s27 sanity case (+43.9pp) and b03 @20% (+2.16pp) show the intended behavior: residual faults undetectable at T=1 because non-scan state is not freely controllable, but detectable after 2-frame sequential justification. **The measured variable is pipeline gain (ΔFC), not absolute partial-scan FC at different ratios.**

### 8.2 When the Pipeline Does Not Help (Current Tier A)

For b04–b13 (except b03 @20%), total pipeline gain is **0.00pp** at all tested ratios. With regenerated masks, T=1 partial-scan FC is already within a few points of full-scan FC_scan. Residual faults at T=2/T=4 are predominantly re-classified as AU without new DT — consistent with structurally hard or engine-untestable faults, not with “T=1 was artificially low.”

**b11** is the extreme runtime case: ~277s total pipeline time @20% with 0 pp gain. Deep multi-frame search on ~239 residual faults is expensive even when coverage is flat.

### 8.3 Tier B: Large Gain at Higher Cost

The June 2026 Tier B pilot shows the pipeline working as designed on larger partial-scan instances where T=1 FC is materially below full-scan: **b12** (39.4% → 74.8%, +35.4 pp) and **b14** (74.7% → 87.6%, +13.0 pp), with all recovery at T=2. This contrasts with Tier A, where T=1 FC is already near full-scan and pipeline headroom is small. Cost is non-trivial (multi-frame stages ~10–28 min) but far below prior crash/timeout behavior. **b15** (168 non-scan FFs @20%) remains blocked by T=1 runtime.

### 8.4 Full-Scan FC Context

Full-scan FC_scan remains 91–97% on Tier A (`phase_d_fullscan_dataset.csv`). Partial-scan T=1 at 20% exclusion is not dramatically lower on most circuits; therefore **the headroom for pipeline recovery is small**. Improving absolute full-scan FC (reducing AU/UD) is a separate engine/netlist-quality topic, not the progressive pipeline metric.

### 8.5 T=2 vs T=4

Where gain occurs (b03, b12, b14 @20%), **all recovery is at T=2**; T=4 adds nothing. For deployment, T=1→T=4 residual may suffice when T=2 gain is zero across a pilot sweep.

### 8.6 Priority Scoring (Negative Result)

Static fault priority scoring (observability/controllability distance, cone size, fanout) showed **no lift over random ordering** for predicting T=2/T=4 recovery. Abandoned.

---

## 9. Related Work

### 9.1 Sequential ATPG and Time-Frame Expansion

Sequential ATPG addresses the problem of generating tests for sequential circuits where internal state is not directly controllable. The standard approach is time-frame expansion: the circuit is unrolled across T clock cycles, and combinational ATPG is applied to the unrolled model [1][2]. The FAN algorithm [1] with backtrack-based search is the foundation of FAN_ATPG. Deeper frames can increase fault detectability by providing more initialization cycles, but also increase search space, memory, and runtime [3].

Our work applies time-frame expansion specifically to partial-scan circuits where non-scan FFs create sequential behavior, and evaluates the incremental benefit of deeper frames through progressive residual targeting.

### 9.2 Partial Scan Design

Partial scan reduces area and timing overhead by scanning only a subset of FFs. Classical methods select scan FFs based on testability metrics (SCOAP), structural loop-breaking, or sequential depth reduction [4][5][6]. More recent work considers timing and power constraints in scan FF selection [7][8][9].

We do *not* propose a new scan selection method. Our non-scan FF set is determined by a fixed timing-prioritized ranking (top x% by minimum-path-slack). The partial-scan circuit is the constrained input to our sequential ATPG evaluation.

### 9.3 Fault Dropping and Residual Targeting

In standard ATPG flows, detected faults are dropped from the target list to avoid redundant pattern generation [10]. Fault dropping is typically within a single ATPG run and not exported across runs. Test compaction techniques further reduce pattern count by targeting multiple faults per pattern [11].

Our progressive residual list extends fault dropping across multiple time-frame depths: faults detected at T=1 are excluded from T=2/T=4, and faults detected by residual T=2 are excluded from residual T=4. This is conceptually fault dropping staged across sequential depth, not a new dropping algorithm.

### 9.4 Timing-Constrained Scan

Scan insertion adds multiplexer delay on functional paths, which can make critical paths fail timing closure. FFs on these paths may be excluded from scan [12][13]. The resulting partial-scan circuit has a fixed set of non-scan FFs determined by timing, not by testability optimization.

Our timing-prioritized non-scan selection approximates this scenario using OpenSTA minimum-path-slack ranking. We do not claim to perform full timing-closure-aware scan synthesis including scan-mux delay modeling.

### 9.5 Low-Power Scan and Test Power

Test power during scan shift is an active research area [7][14][15]. Scan-chain reordering, X-filling, and segmented activation are used to reduce shift power. This work does *not* address test power; non-scan FF selection is timing-driven, not power-driven.

---

## 10. Limitations and Threats to Validity

1. **Benchmark set.** Tier A: 8 ITC'99 circuits × 4 ratios (primary sweep). Tier B: b12/b14/b15 pilot @20% only (2 PASS, 1 T=1 timeout).
2. **Primary metric scope.** Report emphasizes **pipeline gain (ΔFC)**, not cross-ratio absolute FC trends.
3. **Canonical point.** Cross-circuit comparison uses **20% exclusion** unless noted.
4. **s27 is toy-scale.** +43.9pp is pipeline verification only.
5. **Shallow depth.** T=8 not evaluated; T=4 adds 0 gain in Tier A sweep and in Tier B pilot (b12/b14).
6. **Mask/netlist alignment.** Results supersede prior drafts that used stale masks (wrong FF names → artificially low T=1 FC on b07/b13).
7. **Full-scan ceiling.** Partial-scan T=1 already near full-scan on most Tier A circuits, limiting observable pipeline headroom.
8. **AU semantics.** FAN AU is operational (search failure), not formal untestability proof.
9. **Single ATPG backend.** Cross-tool validation not performed.

---

## 11. Conclusion

We implemented a reproducible progressive residual T=1→T=2→T=4 ATPG pipeline with fixed-denominator union accounting on FAN_ATPG. **The evaluation targets pipeline coverage gain over T=1**, not partial-scan FC as a function of exclusion ratio.

On regenerated OpenSTA masks aligned to our gate-level netlists (June 2026), Tier A partial-scan T=1 FC is already high (87.6–96.5% @20% exclusion). **Only b03 @20% shows non-zero pipeline benefit (+2.16pp, entirely from T=2).** All other Tier A (circuit, ratio) pairs show 0.00pp gain through T=4 despite non-trivial runtime on large circuits (notably b11).

A **Tier B pilot** (b12/b14/b15 @20%, June 2026) shows the opposite pattern on larger instances: **b12 +35.4 pp** and **b14 +13.0 pp** (all from T=2), with multi-frame runs completing in 16–28 min after engine rebuild; **b15** T=1 exceeded a 2 h wall limit.

The pipeline is validated (s27, b03, b12, b14) and should be applied selectively when T=1 partial-scan FC leaves a measurable residual gap. On current Tier A instances, deeper staging is mostly a cost without coverage return; Tier B demonstrates substantial recovery when T=1 FC is lower, at higher runtime cost.

---

## Appendix

### A. Result Files

| File | Content |
|------|---------|
| `results/progressive_residual_summary.csv` | Tier A pipeline (32 runs) + Tier B pilot rows (b12, b14 @20%) |
| `results/atpg_speed_log.csv` | Full-scan and Tier B pilot wall-time log |
| `results/phase_d_fullscan_dataset.csv` | Full-scan FC_scan baselines (ratio = 0%) |
| `results/residual_faults/` | Per-stage residual fault list files |
| `masks/*_slack.csv`, `masks/*_x*.mask` | OpenSTA slack ranking + non-scan masks (regenerated June 2026) |
| `results/archive/` | Superseded CSVs (legacy T=8 sweep, two-phase A/B, ISCAS timing) |

### B. Engineering Fixes

| Issue | Resolution |
|-------|-----------|
| Floating nets rejected by FAN_ATPG | ERROR→WARN |
| `_const0_` as free module port | LOGIC0/LOGIC1 tie cells |
| Level-indexed array OOB crashes | `maxGateLevel+1` sizing |
| Stale masks after re-synthesis | `gen_nonscan_masks.sh` |
| `report_fault` prints nothing | Fix inverted logic |
| DFF faults lack instance names | Print cell name |

### C. Open Follow-ups

| Item | Status |
|------|--------|
| Full-scan FC headroom (AU/UD) | Ongoing engine/netlist quality work; see `phase_d_fullscan_dataset.csv` |
| Tier B (b12/b14/b15) | **Pilot @20%:** b12/b14 PASS (+35.4 / +13.0 pp); b15 T=1 TIMEOUT (>2 h). Not in batch sweep. |
| b15 runtime | T=1 alone >7200 s @20%; needs longer wall or engine optimizations (COI, etc.) |
| T=8 pipeline depth | Not evaluated; T=4 adds 0 pp on current Tier A sweep |
| Archived legacy CSVs | `results/archive/` — do not cite for current report |

---

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
