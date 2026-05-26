# ScanForge Project Specification

## 1. Motivation

**Working title:** Sequential ATPG for Partial-Scan Circuits Under Timing-Driven Scan Exclusion

Modern industrial testing flows aim to insert scan on as many flip-flops (FFs) as possible. In practice, however, a subset of FFs may remain non-scan because converting them to scan FFs can worsen timing or violate implementation constraints. Once this happens, scan-based ATPG loses full controllability and observability over circuit state, and stuck-at fault coverage may drop accordingly.

This project focuses on that practical setting. Rather than studying generic scan selection under area overhead assumptions, the project investigates how much fault coverage is lost when timing-critical FFs are excluded from scan, and how much of that loss can be recovered through a sequential ATPG flow designed for partial-scan circuits.

## 2. Problem Statement

The target problem can be stated as follows:

> Given a sequential circuit in which a timing-critical subset of FFs cannot be converted to scan FFs, construct a partial-scan test model and develop a sequential ATPG flow that recovers as much stuck-at fault coverage as possible.

The project assumes:

- a gate-level benchmark circuit
- a stuck-at fault model
- an open-source technology library with cell-delay information
- a user-defined scan-exclusion ratio `x%`

To emulate timing-driven scan exclusion, the project will perform timing-criticality ranking using a library-based timing proxy. FFs will be ranked by timing criticality using metrics such as slack or critical-path participation, and the top `x%` FFs will be treated as non-scan FFs. This setup is intended as a practical timing-sensitivity model rather than a claim of full post-layout timing realism.

All remaining FFs will be treated as scan-capable FFs and connected into a single scan chain. The main research objective is not scan-chain architecture exploration, but sequential test generation under constrained scan access.

## 3. Research Questions

### RQ1. Coverage loss under timing-driven scan exclusion

How much stuck-at fault coverage is lost when the top `x%` timing-critical FFs are left as non-scan FFs?

### RQ2. Coverage recovery by sequential ATPG

How much of that lost coverage can be recovered by a sequential ATPG flow for the resulting partial-scan circuit?

### RQ3. Sensitivity to sequential search depth

How do fault coverage, pattern count, and runtime vary as the sequential ATPG depth increases?

## 4. Proposed Method

The proposed flow consists of four main stages.

### 4.1 Timing-driven non-scan FF identification

The circuit will be analyzed using an open-source timing flow and technology library. Based on a timing-criticality ranking, the top `x%` FFs will be marked as non-scan FFs. The output of this stage is a non-scan mask for each benchmark circuit.

### 4.2 Partial-scan modeling

After the non-scan set is determined, all remaining FFs will be modeled as scan-capable FFs and connected into one scan chain. This produces the constrained partial-scan architecture that will be used for ATPG and evaluation.

### 4.3 Sequential ATPG strategy

The project will study a sequential ATPG flow for partial-scan circuits with the following high-level structure:

1. solve faults that are manageable through the scanned portion of the circuit first
2. apply sequential recovery to residual faults that depend on non-scan state
3. increase sequential search depth in a bounded manner and observe the resulting coverage gain and computational cost

At the current stage, the exact sequential ATPG algorithm is not fixed. The project scope is to design and evaluate a bounded sequential recovery strategy suitable for partial-scan circuits under timing-driven scan exclusion.

### 4.4 Success criteria

The project will be considered successful if it can:

- quantify the coverage loss introduced by timing-driven scan exclusion
- demonstrate measurable fault-coverage recovery over the no-recovery partial-scan baseline
- report the runtime and pattern-count cost associated with deeper sequential search

## 5. Experimental Plan

### Benchmarks

- ISCAS'89 sequential benchmark circuits

### Main parameter sweeps

1. **non-scan ratio:** `x ∈ {5%, 10%, 15%, 20%}`
2. **sequential depth limit:** `T ∈ {0, 1, 2, 4, 8}` or a similar bounded sequence

### Baselines

- full-scan ATPG
- partial-scan ATPG without sequential recovery
- partial-scan ATPG with sequential recovery

### Evaluation metrics

| Metric | Purpose |
|---|---|
| Fault coverage | Primary success metric |
| Undetected / aborted faults | Remaining ATPG gap |
| Pattern count | Test-cost proxy |
| ATPG runtime | Practicality of the method |
| Sequential depth used | Search difficulty indicator |
| Scan shift cycles | Secondary test-time metric |

The core comparison will measure how coverage changes as the timing-driven non-scan ratio increases, and how much of that loss can be recovered as the sequential ATPG depth increases.

## 6. Expected Contributions

This project is expected to contribute:

1. a timing-driven scan-exclusion setup for evaluating partial-scan testability on sequential benchmark circuits
2. a sequential ATPG flow aimed at recovering fault coverage under non-scan constraints
3. an experimental study of the tradeoff among fault coverage, runtime, pattern count, and sequential depth

## 7. Implementation Plan

The implementation work is organized into four tasks:

### Task A. Timing analysis and non-scan mask generation

- build the timing-analysis flow
- rank FFs by timing criticality
- generate non-scan masks for each benchmark and exclusion ratio

### Task B. Partial-scan circuit modeling

- represent scan-capable FFs and non-scan FFs explicitly
- construct the one-chain partial-scan model used for ATPG

### Task C. Sequential ATPG design

- define the bounded sequential recovery flow
- integrate depth control and result collection
- support coverage-oriented comparison against the no-recovery baseline

### Task D. Evaluation and reporting

- run experiments across benchmark circuits and exclusion ratios
- summarize coverage, runtime, and pattern-count trends
- produce final tables, plots, and discussion

## 8. Scope

The main scope of the project is limited to:

- timing-driven scan exclusion
- single-chain partial-scan modeling
- stuck-at fault coverage recovery through sequential ATPG

The following items are outside the main scope:

- random scan-exclusion baselines
- multi-chain architecture comparison
- scan-power optimization
- diagnosis-oriented scan placement
- test compression and physical scan routing
