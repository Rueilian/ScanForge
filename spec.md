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

The ITC'99 benchmark circuits are synthesized to gate-level netlists using Yosys with the NanGate45 library. Static timing analysis (OpenSTA) is then run on each netlist using NanGate45 timing data. Each FF is assigned a criticality score equal to the minimum path slack on any timing path passing through it. FFs are sorted by ascending slack (most timing-critical first), and the top `x%` are marked as non-scan. The output of this stage is a non-scan mask — a list of FF cell names — for each `(circuit, x)` pair.

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

5. **Monotonic depth expectation**
   - For a fixed partial-scan circuit and fault model, increasing sequential depth should not reduce the reachable state space available to ATPG.
   - Therefore, `coverage(T_large)` is expected to be at least as good as `coverage(T_small)` for the same partial-scan configuration, barring tool bugs.

6. **Full-scan dominance expectation**
   - For the same circuit and fault model, a correct partial-scan ATPG model should not provide more controllability than the corresponding full-scan model.
   - Therefore, `coverage(full_scan)` is expected to be at least as good as `coverage(partial_scan, T)` for the same benchmark and ratio setup, barring measurement or implementation error.

7. **Implementation-independence of criteria**
   - These criteria define the intended semantics even if the current FAN_ATPG implementation does not yet satisfy them.
   - Any implementation result that violates these criteria should be treated as evidence of a modeling or engine issue, not as a new definition.

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

11 ITC'99 sequential benchmark circuits synthesized to NanGate45 gate-level Verilog using Yosys. Synthesized netlists are stored in `FAN_ATPG/mod_netlist/b*.v` and serve as the shared benchmark source for all tasks.

| Circuit | FFs | Source RTL |
|---|---|---|
| b03 | 31 | `itc99_rtl/b03.v` |
| b04 | 67 | `itc99_rtl/b04.v` |
| b05 | 88 | `itc99_rtl/b05.v` |
| b07 | 45 | `itc99_rtl/b07.v` |
| b08 | 28 | `itc99_rtl/b08.v` |
| b09 | 30 | `itc99_rtl/b09.v` |
| b11 | 58 | `itc99_rtl/b11.v` |
| b12 | 192 | `itc99_rtl/b12.v` |
| b13 | 65 | `itc99_rtl/b13.v` |
| b14 | 219 | `itc99_rtl/b14.v` |
| b15 | 839 | `itc99_rtl/b15.v` |

All circuits have ≥20 FFs, ensuring at least one non-scan FF at x=5%.

### Parameter sweep

| Parameter | Values |
|---|---|
| Non-scan ratio `x` | 0% (full-scan baseline), 5%, 10%, 15%, 20% |
| Sequential ATPG depth | T=8 (fixed; T=1 for x=0% baseline) |

Total runs: 11 circuits × 5 ratios = **55 runs**.

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
| A | Yosys synthesis + OpenSTA timing, non-scan mask generation | swear01 | Pending |
| B | `PARTIAL_SEQUENTIAL` mode in FAN_ATPG | swear01 | **Done** |
| C | `set_nonscan_ff` command, script integration | swear01 | **Done** |
| D | Python experiment runner, CSV logging | swear01 | Pending |
| E | Full experiment run + analysis | swear01 | Pending |

**Verified pilot results (FAN_ATPG, s27, NanGate45):**

| Circuit | Mode | x | T | Fault coverage |
|---|---|---|---|---|
| s27 | Full scan | 0% | 1 | 94.55% |
| s27 | Partial scan | 67% | 8 | 79.25% |
| s208 | Full scan | 0% | 1 | 97.43% |

The s27 partial-scan result (AU=16, UD=6) reflects the realistic sequential constraint: 16 faults require non-scan FF states that cannot be reached through 8 cycles of circuit initialization.

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
