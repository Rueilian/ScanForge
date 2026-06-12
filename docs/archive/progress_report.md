# Progress Report

> **Archived draft.** Current report: [`../final_report.md`](../final_report.md). Primary data: `results/progressive_residual_summary.csv`.

## Course: EEE5001 VLSI Testing
## Date: 2026-05-29

---

## Group Information

| Item | Info |
|------|------|
| Group Number | Group 5 |
| Topic | Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits |
| Members | 丁睿濂, 駱彥竹, 黃思維 |

---

## Introduction

Scan-based testing is the dominant design-for-testability (DFT) strategy in modern digital circuits. In full-scan design, every flip-flop (FF) is connected into a single scan chain, granting full controllability and observability over all internal state. In practice, however, a subset of FFs may remain non-scan because converting them to scan FFs would violate timing constraints — their paths are already critical and the extra scan multiplexer would push slack negative.

Once this happens, standard scan-based ATPG loses direct access to those FFs. Stuck-at faults whose detection depends on controlling or observing non-scan FF state can no longer be handled by a single-cycle pattern. Sequential ATPG — generating multi-cycle test sequences that propagate state through the non-scan FFs over multiple clock cycles — can potentially recover this coverage, but it is significantly more complex than full-scan ATPG.

This project studies that recovery problem concretely. Given the ITC'99 benchmark circuits synthesized to NanGate45 gate-level netlists, we exclude the top `x%` most timing-critical FFs from scan (ranked by OpenSTA minimum path slack), model the resulting partial-scan circuit with a T=8 multi-frame unrolling, and run sequential ATPG to measure how much stuck-at fault coverage is lost and how much can be recovered.

---

## Topic Description

**Title:** Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits

**One-sentence contribution:**
> This work quantifies the stuck-at fault coverage loss caused by timing-driven scan exclusion on ITC'99 benchmarks and evaluates how much of that loss can be recovered by a multi-frame sequential ATPG flow implemented in FAN_ATPG.

**Problem:**
Given a synthesized sequential circuit, mark the top `x%` most timing-critical FFs (by OpenSTA minimum path slack) as non-scan, model the result as a partial-scan circuit, and measure (a) how much stuck-at fault coverage is lost compared to full-scan and (b) how much is recovered by sequential ATPG over T=8 time frames.

---

## Research Questions

### RQ1. Coverage loss under timing-driven scan exclusion

How much stuck-at fault coverage is lost when the top `x%` timing-critical FFs are left as non-scan FFs, compared to the full-scan baseline?

### RQ2. Coverage recovery by sequential ATPG

How much of that lost coverage can be recovered by a sequential ATPG flow (T=8 time frames) for the resulting partial-scan circuit?

### RQ3. Scalability across circuit sizes

Do the coverage loss and recovery trends from RQ1–RQ2 hold consistently across circuits of different sizes and sequential complexities?

---

## Proposed Technique

### Timing-driven non-scan FF identification

The ITC'99 benchmark circuits are synthesized to gate-level netlists using Yosys with the NanGate45 library. Static timing analysis (OpenSTA) is then run using NanGate45 timing data. Each FF is assigned a criticality score equal to the minimum path slack on any timing path passing through it. FFs are sorted by ascending slack and the top `x%` are marked as non-scan.

### Partial-scan circuit modeling (T=8 frames, PARTIAL_SEQUENTIAL)

Non-scan FF state is modeled across T=8 time frames using a `PARTIAL_SEQUENTIAL` unrolling mode implemented in FAN_ATPG:

- **Non-scan FFs**: each frame's PPI is driven by the previous frame's PPO (state carries across frames via BUF connection)
- **Scan FFs**: each frame's PPI is free (independently controlled)
- **Frame 0**: all PPIs are treated as unknown (X initial state)

T=1 is not a valid partial-scan model: with one frame, non-scan FF PPIs are free and the ATPG artificially reproduces full-scan coverage. T=8 is chosen as a depth sufficient for the sequential complexity of the ITC'99 benchmarks.

### Sequential ATPG flow

FAN_ATPG performs stuck-at ATPG on the T=8 unrolled partial-scan circuit. The non-scan FF names are specified via a `set_nonscan_ff` command added to FAN. Static and dynamic test compression are enabled.

### Experiment automation

A Python runner iterates all 55 `(circuit, x)` combinations, generates a FAN script per combination, invokes FAN, parses `report_statistics` output, and appends one row per run to a results CSV.

---

## Method

### Problem Definition

Let circuit *C* contain *N* flip-flops. Timing analysis ranks FFs by minimum path slack; the top `x%` are designated non-scan, the rest form the scan chain. The partial-scan circuit is unrolled into T=8 time frames under `PARTIAL_SEQUENTIAL` mode. Sequential ATPG then targets all stuck-at faults in this unrolled model.

### Baselines

| Baseline | Description |
|----------|-------------|
| Full-scan (x=0%, T=1) | All FFs scan; standard 1-frame ATPG — ceiling coverage |
| Partial-scan (x>0%, T=8) | Non-scan FFs present; sequential ATPG over 8 frames |

### Parameter Sweep

| Parameter | Values |
|-----------|--------|
| Non-scan ratio `x` | 0% (full-scan), 5%, 10%, 15%, 20% |
| Frames T | 1 for x=0%; 8 for x>0% |

Total runs: 11 circuits × 5 ratios = **55 runs**

### Benchmarks

| Circuit | FFs |
|---------|-----|
| b03 | 31 |
| b04 | 67 |
| b05 | 88 |
| b07 | 45 |
| b08 | 28 |
| b09 | 30 |
| b11 | 58 |
| b12 | 192 |
| b13 | 65 |
| b14 | 219 |
| b15 | 839 |

### Evaluation Metrics

| Metric | Purpose |
|--------|---------|
| Fault coverage | Primary metric |
| Test coverage | Secondary coverage view |
| Undetected / aborted faults | Remaining ATPG gap |
| Pattern count | Test-cost proxy |
| ATPG runtime | Practicality |

---

## Current Implementation Status

| Task | Description | Status |
|------|-------------|--------|
| A | Yosys synthesis + OpenSTA timing, non-scan mask generation | **Done** |
| B | `PARTIAL_SEQUENTIAL` mode in FAN_ATPG (T=8 multi-frame unrolling) | **Done** |
| C | `set_nonscan_ff` command, script integration | **Done** |
| D | Python experiment runner, CSV logging | Script done; blocked on FAN ATPG bug |
| E | Full experiment run + analysis | Pending |

**Verified `s27` sequential-ATPG sanity results:**

| Circuit | Mode | x | T | Fault coverage | Patterns |
|---------|------|---|---|----------------|----------|
| s27 | Full scan | 0% | 1 | 94.55% | 7 |
| s27 | Partial scan, no recovery | 67% | 1 | 39.36% | 5 |
| s27 | Partial scan, bounded recovery | 67% | 4 | 88.68% | 4 |

These three cases now satisfy the intended ordering `full_scan >= bounded partial-scan >= no-recovery partial-scan`.

The key backend fix was a consistent **final-frame stuck-at fault mapping** for multi-frame SAF ATPG. Before this correction, representative faults such as `G17 SA1` were falsely classified as ATPG-untestable at `T=4`. After aligning ATPG target selection and fault simulation to the final observation frame, the same fault becomes detected with one generated pattern. The remaining `T=4` ATPG-untestable faults on `s27` are localized to the `U_G10 -> U_G5` cone and are consistent with the intended partial-scan observability limit rather than the earlier infrastructure bug.

ITC'99 full sweep results remain pending; the current validated pilot is `s27`.

### Current Blocker

The main blocker is no longer the `s27` FAN_ATPG core path. The remaining work is to extend the same validated sequential-ATPG reporting flow from the `s27` pilot to the broader benchmark matrix and integrate those outputs into the final evaluation tables.

---

## Results

*(Pending — will be filled in after FAN bug fix and full 55-run sweep)*

Expected tables:
- Coverage vs. non-scan ratio per circuit (RQ1)
- Coverage recovery by sequential ATPG (RQ2)
- Runtime and pattern count summary

---

## Discussion

*(Pending)*

---

## Remaining Work

1. Fix `atpg.cpp` `findFinalObjective` / `finalObjectives_.empty()` bug
2. Run pilot (b03, 5 ratios) to verify fix
3. Run full 55-experiment sweep
4. Analyze coverage loss (RQ1) and recovery (RQ2) trends
5. Write results and discussion sections

**Future directions:** A cone-guided multi-frame simplification — restricting per-fault time-frame reasoning to the fault-relevant logic cone rather than duplicating the entire circuit — is a natural extension that could reduce memory overhead for large circuits and deep T.

---

## Job Partition

| Member | Responsibilities |
|--------|-----------------|
| 丁睿濂 | FAN_ATPG extensions (PARTIAL_SEQUENTIAL mode, set_nonscan_ff, bug fix); synthesis + STA pipeline; experiment runner |
| 駱彥竹 | Method design, algorithm discussion, literature review |
| 黃思維 | Testing, report writing, result analysis |

---

## Schedule

| Date | Milestone |
|------|-----------|
| 2026-05-29 | Progress report submission |
| 2026-05-30–06-01 | Fix FAN ATPG bug; run pilot sweep |
| 2026-06-02–06-07 | Full 55-run sweep; write results section |
| 2026-06-08–06-10 | Write discussion; finalize figures |
| 2026-06-11–06-14 | Finalize report; prepare presentation |
| 2026-06-16 | **Presentation** |
| 2026-06-17 noon | **Final report + code submission** |
| 2026-06-17 13:30–17:30 | **Demo** |

---

## References

[1] FAN algorithm: H. Fujiwara and T. Shimono, "On the acceleration of test generation algorithms," *IEEE Trans. Computers*, vol. C-32, no. 12, 1983.

[2] ITC'99 benchmarks: F. Corno, M. S. Reorda, and G. Squillero, "RT-level ITC'99 benchmarks and first ATPG results," *IEEE Design & Test*, vol. 17, no. 3, 2000.

[3] NanGate Open Cell Library, FreePDK 45nm.

---

## AI Usage Declaration

**Claude (Anthropic):** C++ implementation and debugging, specification drafting, bug analysis

**Cursor:** AI-assisted code review, implementation, and debugging

**GitHub Copilot:** Code completion during development

**HAPI:** Commit automation and session management

All key design decisions, algorithm logic, and experimental analysis were reviewed and confirmed by the team.
