# ScanForge Project Specification

## 1. Motivation

**Working title:** Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits

Modern industrial testing flows aim to insert scan on as many flip-flops (FFs) as possible. In practice, however, a subset of FFs may remain non-scan because converting them to scan FFs can worsen timing or violate implementation constraints. Once this happens, scan-based ATPG loses full controllability and observability over circuit state, and stuck-at fault coverage may drop accordingly.

This project focuses on partial-scan sequential ATPG under timing-driven non-scan constraints. The **primary research question** is whether a **progressive T=1→T=2→T=4 residual pipeline** improves stuck-at fault coverage **beyond T=1 alone** on the same partial-scan circuit.

Timing-driven non-scan FF selection (top x% by OpenSTA slack) is **experimental setup** that produces realistic partial-scan instances. **Cross-ratio FC comparison is not a research goal**; ratios 5/10/15/20% repeat the same pipeline evaluation under different exclusion sizes.

## 2. Problem Statement

> Given a timing-constrained partial-scan circuit, measure how much stuck-at fault coverage a **progressive residual multi-frame ATPG pipeline (T=1 → T=2 → T=4)** adds over **T=1 alone**, using a fixed T=1 fault denominator.

The project assumes:

- gate-level ITC'99 benchmark circuits synthesized with NanGate45
- stuck-at fault model (SAF)
- NanGate45 open-source technology library for both synthesis and timing analysis
- user-defined scan-exclusion ratio `x%`

To emulate timing-driven scan exclusion, FFs are ranked by timing criticality using static timing analysis. The top `x%` most timing-critical FFs are treated as non-scan FFs. This is a practical timing-sensitivity proxy rather than a claim of full post-layout accuracy.

All remaining FFs are treated as scan-capable and connected into a single scan chain. The research objective is sequential test generation under constrained scan access, not scan-chain architecture exploration.

## 3. Research Questions

### RQ1. Pipeline gain over T=1

For each partial-scan benchmark instance, how much does union coverage FC(T1∪T2∪T4) exceed FC(T1)?

### RQ2. Stage attribution

How much of that gain comes from residual **T=2** vs residual **T=4** (gain_T2_pp, gain_T4_pp)?

### RQ3. Cost vs benefit

What are T=1 / T=2 / T=4 runtimes, and is deeper staging justified by newly detected fault count?

### Setup parameters (not primary RQs)

- **Non-scan ratio x ∈ {5%, 10%, 15%, 20%}:** repeated conditions; canonical cross-circuit point = **20%**.
- **Full-scan baseline (x=0%):** context only (`phase_d_fullscan_dataset.csv`); not the pipeline comparison baseline for RQ1–RQ3.

## 4. Proposed Method

### 4.1 Timing-driven non-scan FF identification

The ITC'99 benchmark circuits are synthesized to gate-level netlists using Yosys with a **base-gate NanGate45 liberty** (`NangateOpenCellLibrary_base.lib`). Allowed combinational cells: INV/AND/OR/NAND/NOR/XOR and **MUX2**; **OAI*/AOI* compound cells are forbidden** and expanded to primitives by ABC. Sequential cells use `DFFR_X1` (converted to `SDFFR_X1` + scan chain by `fixup_verilog.py --full-scan`).

Netlists are produced by the reproducible pipeline (`scripts/build_itc99_netlists.sh`): RTL prep → Yosys → fixup → validate. See [`docs/archive/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md`](./archive/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md).

Static timing analysis (OpenSTA) uses the **full** `NangateOpenCellLibrary_typical.lib` for timing. Each FF is assigned a criticality score equal to the minimum path slack on any timing path passing through it. FFs are sorted by ascending slack (most timing-critical first), and the top `x%` are marked as non-scan.

**Owner: swear01**

### 4.2 Partial-scan circuit modeling

FAN_ATPG `PARTIAL_SEQUENTIAL` mode unrolls the circuit across multiple time frames:

- **Non-scan FFs:** frame *t* PPI driven by frame *t−1* PPO (state carries across frames)
- **Scan FFs:** each frame PPI is independently controllable (scan load)

The engine supports arbitrary depth; **primary evaluation uses T=1, T=2, and T=4** (§4.3). Legacy `scripts/archive/run_atpg_sweep.py` used T=8 and is archived.

At T=1 with correct partial-scan semantics, non-scan FF initial state is **X** and PPIs are not freely assigned — this yields pipeline baseline **FC_T1**.

**Owner: swear01 — DONE**

### 4.2a Correctness Criteria for Partial-Scan Sequential ATPG

The project uses the following correctness criteria to judge whether the partial-scan sequential ATPG model is implemented correctly. These are semantic requirements, not expected final numbers.

1. **Scan/non-scan controllability separation**
   - Scan FFs may be assigned freely at the modeled frame.
   - Non-scan FFs may not be assigned freely unless their state is justified through modeled sequential transitions.

2. **Time-frame semantics**
   - `T = 1` means there is exactly one modeled frame. No extra initialization cycles exist outside that frame.
   - `T > 1` means the first `T-1` frames are available for state justification, and the final frame is used for fault activation / propagation / observation.

3. **Initial-state semantics**
   - At frame 0, non-scan FF state is unknown (`X`) unless an explicit reset model is introduced in the spec.
   - Unknown initial state alone must not be silently converted into a freely controllable scan-like input.

4. **Sequential justification requirement**
   - For partial-scan circuits, a required non-scan FF value at the observation frame is valid only if the ATPG model can justify it through the modeled preceding frames.
   - If the required state cannot be justified within the modeled depth, the fault may remain undetected or ATPG-untestable.

5. **Scan/non-scan observability separation**
   - Scan FF `PPO`s may be used as direct scan-observation endpoints.
   - Non-scan FF `PPO`s must not be treated as direct scan-observation endpoints at `T = 1`.
   - The same non-scan `PPO` may still participate as a structural pseudo-output of the FF data input and, for `T > 1`, as the state source that feeds the next modeled frame.
   - Therefore, implementation checks must distinguish between:
     - `PPO` used as an observation endpoint
     - `PPO` used as a structural single-input gate inside the unrolled circuit

6. **Monotonic depth expectation**
   - For a fixed partial-scan circuit and fault model, increasing sequential depth should not reduce the reachable state space available to ATPG.
   - Therefore, `coverage(T_large)` is expected to be at least as good as `coverage(T_small)` for the same partial-scan configuration, barring tool bugs.

7. **Full-scan dominance expectation**
   - For the same circuit and fault model, a correct partial-scan ATPG model should not provide more controllability than the corresponding full-scan model.
   - Therefore, `coverage(full_scan)` is expected to be at least as good as `coverage(partial_scan, T)` for the same benchmark and ratio setup, barring measurement or implementation error.

8. **Implementation-independence of criteria**
   - These criteria define the intended semantics even if the current FAN_ATPG implementation does not yet satisfy them.
   - Any implementation result that violates these criteria should be treated as evidence of a modeling or engine issue, not as a new definition.

9. **Multi-frame stuck-at fault placement**
   - For `SA0/SA1` ATPG on a multi-frame unrolled circuit, the target stuck-at fault must be modeled on the final observation frame, not on frame 0.
   - The same final-frame mapping must be used consistently in:
     - ATPG target generation
     - DTC activation / objective setup
     - fault-simulation activation and injection
   - Otherwise the ATPG core, pattern replay, and fault classification can disagree about whether a multi-frame SAF pattern is valid.

### 4.3 Progressive residual ATPG pipeline (primary method)

The **evaluation flow** is implemented in `scripts/run_progressive_residual.py`:

```
Phase 1: ATPG at T=1 on all faults F           → D1, FC_T1
Phase 2: ATPG at T=2 on residual R1 = F − D1   → new D2, FC_T1_T2
Phase 3: ATPG at T=4 on residual R2 = F − D1 − D2 → new D4, FC_T1_T2_T4
Report:  total_gain_pp = FC_T1_T2_T4 − FC_T1
```

FAN script pattern per stage:

```
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/<circuit>.v
set_nonscan_ff <ff1> <ff2> ...
build_circuit --frame {1|2|4}
set_fault_type saf
add_fault --all          # T=1 only
add_fault -f <residual>  # T=2 / T=4
run_atpg
report_statistics
```

**Owner: swear01 — DONE** (32/32 Tier A sweep in `results/progressive_residual_summary.csv`)

### 4.4 Legacy single-depth sweep (secondary)

`scripts/archive/run_atpg_sweep.py` ran fixed **T=8** per ratio (archived). It is **not** the primary RQ1–RQ3 metric. Use `results/progressive_residual_summary.csv`.

## 5. Experimental Plan

### Benchmarks

ITC'99 sequential benchmarks synthesized to NanGate45 gate-level Verilog using Yosys. Netlists live in `FAN_ATPG/mod_netlist/b*.v`. Scope is tiered — see [`docs/archive/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md`](./archive/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md) and `scripts/archive/itc99_benchmark_scope.sh`.

#### Tier A — Active (8 circuits, ATPG sweeps)

| Circuit | RTL FFs | FC_scan (full-scan, 2026-06-10) | ATPG runtime |
|---|---:|---:|---|
| b03 | 31 | 90.59% | < 0.01 s |
| b04 | 67 | 94.62% | < 1 s |
| b05 | 88 | 95.47% | < 0.2 s |
| b07 | 45 | 92.98% | < 0.01 s |
| b08 | 28 | 95.47% | < 2 s |
| b09 | 29 | 94.58% | < 0.01 s |
| b11 | 84 | 97.80% | < 0.2 s |
| b13 | 86 | 91.54% | < 0.01 s |

#### Tier B — Deferred (netlist built; ATPG excluded until engine speed fix)

| Circuit | RTL FFs | Status |
|---|---:|---|
| b12 | 192 | FAN SAF timeout / MUX backtrace crash |
| b14 | 219 | FAN SAF segfault or > 10 min |
| b15 | 839 | FAN SAF hours-scale runtime |

#### Tier C — Out of scope (not in pipeline)

`b17`, `b18`, `b20`, `b21`, `b22` and mega-ISCAS (`s35932`, `s38417`, `s38584`). Deferred until FAN SAF engine matures on Tier B.

All **Tier A** circuits have ≥20 FFs, ensuring at least one non-scan FF at x=5%.

### Parameter sweep

| Parameter | Values | Role |
|---|---|---|
| Circuits (Tier A) | b03, b04, b05, b07, b08, b09, b11, b13 | Benchmarks |
| Non-scan ratio `x` | 5%, 10%, 15%, 20% | **Setup replication** (not primary axis) |
| Pipeline depths | T=1, T=2, T=4 | **Primary measured axis** |
| Canonical reporting point | **x = 20%** | Cross-circuit comparison |
| Fault model | SAF | Fixed |

Total progressive pipeline runs: **8 × 4 = 32** (`run_progressive_residual_sweep.py`).

### Baselines

| Baseline | Description |
|---|---|
| **FC_T1** | Partial-scan, single frame — pipeline baseline |
| **FC_T1_T2 / FC_T1_T2_T4** | Progressive union after each stage |
| **Full-scan FC_scan** | x=0%, separate dataset — context only |

### Evaluation metrics (primary)

| Metric | Purpose |
|---|---|
| **total_gain_pp** | FC_T1_T2_T4 − FC_T1 — **headline result** |
| gain_T2_pp, gain_T4_pp | Stage attribution |
| T2_new_DT, T4_new_DT | Recovered fault count |
| T1_rt, T2_rt, T4_rt | Cost |

Do **not** headline cross-ratio absolute FC trends; report pipeline gain per (circuit, x), summarize @20%.

## 6. Expected Contributions

1. A reproducible **progressive residual T=1→T=2→T=4** analysis pipeline with fixed-denominator union FC on FAN_ATPG
2. Timing-driven partial-scan **setup** (OpenSTA masks on NanGate45 ITC'99 netlists)
3. Empirical answer to **how much each pipeline stage adds over T=1** on Tier A benchmarks (June 2026 sweep)

## 7. Implementation Status

| Task | Description | Owner | Status |
|---|---|---|---|
| A | Yosys synthesis + OpenSTA timing, non-scan mask generation | swear01 | **Done** |
| B | `PARTIAL_SEQUENTIAL` mode in FAN_ATPG | swear01 | **Done** |
| C | `set_nonscan_ff` command, script integration | swear01 | **Done** |
| D | Progressive residual runner + CSV (`run_progressive_residual.py`) | swear01 | **Done** |
| E | Tier A pipeline sweep + report update | swear01 | **Done** (32/32 PASS, June 2026) |

**Verified results (FAN_ATPG, s27, NanGate45, T=1):**

| Circuit | Mode | x | T | Fault coverage | DT | AU |
|---|---|---|---|---|---|---|
| s27 | Full scan | 0% | 1 | 94.55% | 104 | 0 |
| s27 | Partial scan no recovery | 67% | 1 | 39.36% | 37 | 55 |

The T=1 `partial_scan_no_recovery` case now correctly separates from `full_scan` (94.55% vs 39.36%), confirming non-scan FFs are not treated as scan-controllable. Pattern traces confirm non-scan PPIs are `X` and non-scan PPOs are not observable.

**Verified results (FAN_ATPG, s27, NanGate45, T=4):**

| Circuit | Mode | x | T | Fault coverage |
|---|---|---|---|---|
| s27 | Partial scan with recovery | 67% | 4 | 88.68% |

**ITC'99 pipeline status (2026-06-09):**

- **In progress:** base-gate netlist pipeline (`build_itc99_netlists.sh`) — targets undriven=0, OAI/AOI-free netlists, all 11 ITC loadable in FAN
- **Working (Phase D):** b03 FC_scan **93%**, b07 **94%** (with current compound atomic gates + partial netlists)
- **Planned migration:** keep FAN **`Gate::MUX`** (D1); revert OAI/AOI atomic gates (D3.2/D3.3); rely on synthesis to expand OAI/AOI
- Non-scan masks: 55/55 mask files exist; **regenerate after netlist rebuild** if FF instance names change
- Full-scan baseline uses **FC_scan** (scan-protocol auto-TI on `add_fault --all`); see `docs/archive/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md`
- Known netlist blockers (pre-pipeline): b05/b08–b15 undriven or syntax errors — addressed by prep + validate gate, not hand edits

**Multi-frame SAF correctness note** (resolved in FAN_ATPG commit `f927b34`):

Pattern `PIFrames_` now stores all PI frames. `writeAtpgValToPatternPI()` writes all frames. Simulator replays all frames. SAF faults are mapped to the final observation frame consistently across ATPG, fault injection, and fault simulation.

## 8. Scope

In scope:
- timing-driven non-scan setup (OpenSTA, fixed ratios as replication)
- progressive residual **T=1→T=2→T=4** pipeline evaluation
- union FC gain over T=1 (fixed denominator)

Out of scope (not primary research axes):
- comparing absolute partial-scan FC across exclusion ratios
- random or optimization-driven scan-exclusion baselines
- multi-chain architecture comparison
- scan-power optimization
- diagnosis-oriented scan placement
- test compression and physical scan routing

## 9. Decision Tracking

Any important project decision must be recorded in both:

- `docs/spec.md`, if the decision changes method definition, experiment design, scope, assumptions, or success criteria
- `docs/archive/checklist.md`, if the decision affects historical implementation tracking

Important decisions include, but are not limited to:

- benchmark selection
- ATPG model definition
- time-frame interpretation
- initial-state assumptions
- evaluation-case definition
- comparison metrics
- scope changes and fallback choices

No important decision should remain only in chat history.

### 2026-06-09 — Base-gate netlist + partial atomic-gate revert

- **MUX2** is treated as a **base gate** (allowed in synthesis netlist; FAN keeps `Gate::MUX` atomic modeling from Phase D1).
- **OAI*/AOI*** compound cells are **forbidden** in synthesis output; ABC maps them to INV/AND/OR/NAND/NOR primitives.
- FAN **reverts D3.2/D3.3** OAI/AOI atomic gates once base-gate pipeline is validated; D1 MUX and Phase C fixes remain.
- ITC netlists must pass `validate_netlist.py` (undriven=0, no OAI/AOI) before ATPG sweeps.
- Plan: [`docs/archive/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md`](./archive/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md)
- Multi-frame head-line justification note:
  - In `PARTIAL_SEQUENTIAL` ATPG, a head line whose value has already been fixed by
    fault activation or propagation must still be eligible for upstream
    justification.
  - `findFinalObjective()` must not silently discard non-`X` head lines if they
    still need justification; otherwise a valid multi-frame sequence can be
    misclassified as `AU` before any real search occurs.
