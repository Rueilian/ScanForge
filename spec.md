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

**Owner: Rueilian**

### 4.2 Partial-scan circuit modeling

Non-scan FF state is modeled across T=8 time frames using a `PARTIAL_SEQUENTIAL` unrolling mode implemented in FAN_ATPG. In this mode:

- **Non-scan FFs**: each frame's PPI is driven by the previous frame's PPO (state carries across frames via a BUF connection)
- **Scan FFs**: each frame's PPI is free (independently controlled, equivalent to a primary input)

The initial state of non-scan FFs at frame 0 is treated as **unknown (X)**, following standard sequential ATPG convention. The ATPG engine uses the T−1 preceding frames as initialization cycles to drive non-scan FF state toward the values needed to sensitize faults, with the fault observed in the final frame. T=8 is chosen as a fixed depth sufficient for the sequential complexity of the benchmark circuits.

T=1 is not a valid partial-scan model: with a single frame, non-scan FF PPIs are free inputs and the ATPG can assign them any value, artificially reproducing full-scan coverage regardless of the non-scan constraint.

**Owner: swear01 — DONE**

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

ITC'99 sequential benchmark circuits synthesized with NanGate45. Specific circuits are selected after synthesis, filtered to those with at least 20 FFs (to ensure at least one non-scan FF at x=5%).

### Parameter sweep

| Parameter | Values |
|---|---|
| Non-scan ratio `x` | 5%, 10%, 15%, 20% |
| Sequential ATPG depth | T=8 (fixed) |

Total runs: `|circuits| × 4`. Approximately 28–40 runs depending on final circuit selection.

### Baselines

| Baseline | Description |
|---|---|
| Full-scan | All FFs scan, x=0, standard 1-frame ATPG — ceiling coverage |
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
| A | Yosys synthesis + OpenSTA timing, non-scan mask generation | Rueilian | In progress |
| B | `PARTIAL_SEQUENTIAL` mode in FAN_ATPG | swear01 | **Done** |
| C | `set_nonscan_ff` command, script integration | swear01 | **Done** |
| D | Python experiment runner, CSV logging | swear01 | Pending |
| E | Full experiment run + analysis | Both | Pending |

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
