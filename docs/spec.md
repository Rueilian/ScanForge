# ScanForge Project Specification

## 1. Motivation

**Working title:** Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits

Modern industrial testing flows aim to insert scan on as many flip-flops (FFs) as possible. In practice, however, a subset of FFs may remain non-scan because converting them to scan FFs can worsen timing or violate implementation constraints. Once this happens, scan-based ATPG loses full controllability and observability over circuit state, and stuck-at fault coverage may drop accordingly.

This project focuses on that practical setting. Rather than studying generic scan selection, the project investigates how much fault coverage is lost when timing-critical FFs are excluded from scan, and how much of that loss can be recovered through a sequential ATPG flow designed for partial-scan circuits.

## 2. Problem Statement

> Given a sequential circuit in which a timing-critical subset of FFs cannot be converted to scan FFs, construct a partial-scan test model and develop a sequential ATPG flow that recovers as much stuck-at fault coverage as possible.

The project assumes:

- gate-level ITC'99 benchmark circuits synthesized with NanGate45
- stuck-at fault model (SAF)
- NanGate45 open-source technology library for both synthesis and timing analysis
- user-defined scan-exclusion ratio `x%`

To emulate timing-driven scan exclusion, FFs are ranked by timing criticality using static timing analysis. The top `x%` most timing-critical FFs are treated as non-scan FFs. This is a practical timing-sensitivity proxy rather than a claim of full post-layout accuracy.

All remaining FFs are treated as scan-capable and connected into a single scan chain. The research objective is sequential test generation under constrained scan access, not scan-chain architecture exploration.

## 3. Research Questions

### RQ1. Coverage loss under timing-driven scan exclusion

How much stuck-at fault coverage is lost when the top `x%` timing-critical FFs are left as non-scan FFs, compared to the full-scan baseline?

### RQ2. Coverage recovery by sequential ATPG

How much of that lost coverage can be recovered by a sequential ATPG flow (T=8 time frames) for the resulting partial-scan circuit?

### RQ3. Scalability across circuit sizes

Do the coverage loss and recovery trends from RQ1–RQ2 hold consistently across circuits of different sizes and sequential complexities?

## 4. Proposed Method

### 4.1 Timing-driven non-scan FF identification

The ITC'99 benchmark circuits are synthesized to gate-level netlists using Yosys with a **base-gate NanGate45 liberty** (`NangateOpenCellLibrary_base.lib`). Allowed combinational cells: INV/AND/OR/NAND/NOR/XOR and **MUX2**; **OAI*/AOI* compound cells are forbidden** and expanded to primitives by ABC. Sequential cells use `DFFR_X1` (converted to `SDFFR_X1` + scan chain by `fixup_verilog.py --full-scan`).

Netlists are produced by the reproducible pipeline (`scripts/build_itc99_netlists.sh`): RTL prep → Yosys → fixup → validate. See [`docs/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md`](./superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md).

Static timing analysis (OpenSTA) uses the **full** `NangateOpenCellLibrary_typical.lib` for timing. Each FF is assigned a criticality score equal to the minimum path slack on any timing path passing through it. FFs are sorted by ascending slack (most timing-critical first), and the top `x%` are marked as non-scan.

**Owner: swear01**

### 4.2 Partial-scan circuit modeling

Non-scan FF state is modeled across T=8 time frames using a `PARTIAL_SEQUENTIAL` unrolling mode implemented in FAN_ATPG. In this mode:

- **Non-scan FFs**: each frame's PPI is driven by the previous frame's PPO (state carries across frames via a BUF connection)
- **Scan FFs**: each frame's PPI is free (independently controlled, equivalent to a primary input)

The initial state of non-scan FFs at frame 0 is treated as **unknown (X)**, following standard sequential ATPG convention. The ATPG engine uses the T−1 preceding frames as initialization cycles to drive non-scan FF state toward the values needed to sensitize faults, with the fault observed in the final frame. T=8 is chosen as a fixed depth sufficient for the sequential complexity of the benchmark circuits.

In the unmodified FAN_ATPG engine, `T = 1` is not yet a valid partial-scan model: with a single frame, non-scan FF PPIs still behave like free inputs and ATPG can assign them any value, artificially reproducing full-scan coverage regardless of the non-scan constraint.

For the evaluation cases in this project:

- `partial_scan_no_recovery` is defined as `T = 1`
- the initial state of non-scan FFs remains `X`
- no extra initialization cycles are allowed outside the modeled time frames

This means the no-recovery case must treat non-scan FFs as unknown and uncontrollable at the single modeled frame. Any behavior that lets ATPG freely justify those FFs back to `0/1` is considered an invalid implementation of the no-recovery case.

The current implementation audit has already identified one major source of invalid behavior: even after frame-0 non-scan PPIs are converted to `TIEX`, the ATPG-to-pattern and pattern-to-simulation interfaces still treat all `PPI` bits as scan-controllable unless they are explicitly split by non-scan membership.

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

### 4.3 Sequential ATPG flow

FAN_ATPG performs stuck-at ATPG on the T=8-frame unrolled partial-scan circuit. The flow is:

```
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/<circuit>.v
set_nonscan_ff <ff1> <ff2> ...
build_circuit --frame 8
set_fault_type saf
add_fault --all
set_static_compression on
set_dynamic_compression on
run_atpg
report_statistics > rpt/<circuit>_x<x>.rpt
exit
```

**Owner: swear01 — DONE**

### 4.4 Experiment automation

A Python runner iterates all `(circuit, x)` combinations, generates a FAN_ATPG script per combination using the non-scan mask from Task A, invokes the FAN binary, parses the `report_statistics` output, and appends one row per run to a CSV log.

**CSV schema:**
```
circuit, nonscan_ratio, fault_coverage, test_coverage, DT, AU, AB, UD, patterns, runtime_s
```

**Owner: swear01 — Pending**

## 5. Experimental Plan

### Benchmarks

ITC'99 sequential benchmarks synthesized to NanGate45 gate-level Verilog using Yosys. Netlists live in `FAN_ATPG/mod_netlist/b*.v`. Scope is tiered — see [`docs/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md`](./superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md) and `scripts/itc99_benchmark_scope.sh`.

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

| Parameter | Values |
|---|---|
| Non-scan ratio `x` | 0% (full-scan baseline), 5%, 10%, 15%, 20% |
| Sequential ATPG depth | T=8 (fixed; T=1 for x=0% baseline) |
| Fault model | **SAF only** (`set_fault_type saf`); TDF supported by FAN but not used |

Total runs (default): **8 active circuits × 5 ratios = 40 runs**.

Optional: `ITC_INCLUDE_DEFERRED=1` adds Tier B → 55 runs (not recommended until engine plan S2/S3 lands).

### Baselines

| Baseline | Description |
|---|---|
| Full-scan | All FFs scan, x=0, standard 1-frame ATPG — ceiling coverage |
| Partial-scan without recovery | Non-scan FFs present, T=1, non-scan initial state remains X |
| Partial-scan + sequential ATPG | Non-scan FFs present, T=8 |

### Evaluation metrics

| Metric | Purpose |
|---|---|
| Fault coverage | Primary success metric |
| Test coverage | Secondary coverage view |
| Undetected / aborted faults | Remaining ATPG gap |
| Pattern count | Test-cost proxy |
| ATPG runtime | Practicality of the method |

The core comparison measures how coverage drops as `x` increases (RQ1) and how much of that gap remains after sequential ATPG recovery (RQ2). RQ3 checks whether the trend holds across all benchmark circuits.

## 6. Expected Contributions

1. A timing-driven scan-exclusion setup using NanGate45 STA on ITC'99 benchmarks
2. A `PARTIAL_SEQUENTIAL` multi-frame unrolling mode in FAN_ATPG enabling sequential ATPG for partial-scan circuits
3. An experimental study of fault coverage loss and recovery as a function of timing-driven scan exclusion ratio

## 7. Implementation Status

| Task | Description | Owner | Status |
|---|---|---|---|
| A | Yosys synthesis + OpenSTA timing, non-scan mask generation | swear01 | **Done** |
| B | `PARTIAL_SEQUENTIAL` mode in FAN_ATPG | swear01 | **Done** |
| C | `set_nonscan_ff` command, script integration | swear01 | **Done** |
| D | Python experiment runner, CSV logging | swear01 | Pending |
| E | Full experiment run + analysis | swear01 | Pending |

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
- Full-scan baseline uses **FC_scan** (scan-protocol auto-TI on `add_fault --all`); see `docs/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md`
- Known netlist blockers (pre-pipeline): b05/b08–b15 undriven or syntax errors — addressed by prep + validate gate, not hand edits

**Multi-frame SAF correctness note** (resolved in FAN_ATPG commit `f927b34`):

Pattern `PIFrames_` now stores all PI frames. `writeAtpgValToPatternPI()` writes all frames. Simulator replays all frames. SAF faults are mapped to the final observation frame consistently across ATPG, fault injection, and fault simulation.

## 8. Scope

In scope:
- timing-driven scan exclusion (NanGate45 STA, minimum path slack metric)
- single-chain partial-scan modeling
- stuck-at fault coverage recovery through sequential ATPG (T=8 fixed depth)

Out of scope:
- random or optimization-driven scan-exclusion baselines
- multi-chain architecture comparison
- scan-power optimization
- diagnosis-oriented scan placement
- test compression and physical scan routing

## 9. Decision Tracking

Any important project decision must be recorded in both:

- `spec.md`, if the decision changes method definition, experiment design, scope, assumptions, or success criteria
- `checklist.md`, if the decision affects implementation order, task status, validation flow, or the current execution plan

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
- Plan: [`docs/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md`](./superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md)
- Multi-frame head-line justification note:
  - In `PARTIAL_SEQUENTIAL` ATPG, a head line whose value has already been fixed by
    fault activation or propagation must still be eligible for upstream
    justification.
  - `findFinalObjective()` must not silently discard non-`X` head lines if they
    still need justification; otherwise a valid multi-frame sequence can be
    misclassified as `AU` before any real search occurs.
