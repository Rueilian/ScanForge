# ScanForge Paper Spec (Revised)

## 1. Scope

**Paper focus:** Partial scan FF selection for stuck-at fault coverage under physical design constraints  
**Core framing:** In modern designs, partial scan is not an area-saving technique — it is a consequence of physical constraints (timing-critical FFs, routing restrictions) that prevent full-scan insertion. The test engineer's problem is: given a set of FFs that cannot be scanned, how to maximize stuck-at fault coverage through the sequential ATPG problem that results.

This paper studies which FFs, when made scannable, best preserve stuck-at fault coverage — evaluated with **actual fault coverage from FAN_ATPG**, not a proxy.

---

## 2. Problem Statement

**Given:** A circuit with N flip-flops. A subset F_fixed ⊆ {FF₁, …, FF_N} cannot be scanned (physical constraint). The remaining FFs may or may not be scanned, subject to a budget K_free.

**Goal:** Select K_free FFs from the remaining candidates such that stuck-at fault coverage under sequential ATPG is maximized.

**Why this is hard:**  
Non-scan FFs require sequential ATPG: the circuit must be unrolled across multiple time-frames to sensitize and propagate faults through non-scan FFs. This causes memory/time explosion. The choice of which FFs to scan directly affects the sequential depth and cycle structure of the S-graph, which determines ATPG tractability.

---

## 3. Target Contribution

> We study how partial scan FF selection affects sequential ATPG difficulty and stuck-at fault coverage on ISCAS'89 benchmarks, compare SCOAP-based and S-graph-based selection strategies against actual measured fault coverage, and characterize when each strategy is most beneficial.

This is a **measurement and characterization paper** more than a pure algorithm paper. The contribution is:

1. Empirical comparison of partial scan selection strategies under **actual fault coverage** (not proxy)
2. S-graph construction and MFVS analysis to characterize sequential ATPG complexity
3. Comparison: SCOAP CO ranking vs MFVS vs combined strategy
4. Characterization of which FF properties (SCOAP score, S-graph position, cycle membership) best predict coverage importance
5. A reproducible evaluation flow on ISCAS'89 using FAN_ATPG

---

## 4. Research Questions

### RQ1. Does SCOAP CO ranking correlate with actual fault coverage improvement?
When a FF is selected for scan based on its CO score (high observability cost), does it actually improve fault coverage more than a random or MFVS-selected FF?

### RQ2. Does MFVS-based selection (cycle breaking) outperform SCOAP-based selection for coverage?
The classic Cheng & Agrawal 1990 method prioritizes FFs that break S-graph cycles. Does this give higher fault coverage than SCOAP-ranking on ISCAS'89?

### RQ3. Does a combined MFVS + SCOAP strategy outperform either alone?
MFVS addresses ATPG tractability; SCOAP addresses observability. A hybrid may address both.

### RQ4. How does sequential depth / ATPG abort rate vary with partial scan configuration?
Which partial scan configurations lead to more ATPG aborts (timeframe limit exceeded)? Can we predict this from S-graph structure without running ATPG?

### RQ5. At what scan ratio does fault coverage stabilize?
How many FFs need to be scanned before coverage approaches full-scan levels? Does the answer depend on S-graph topology or SCOAP distribution?

---

## 5. Key Technical Dependency

**Critical prerequisite:** The entire evaluation depends on being able to run FAN_ATPG in partial scan mode and obtain actual stuck-at fault coverage.

This must be verified **before** any other implementation work:
1. Can FAN_ATPG accept a partial scan chain definition (specifying which FFs are scan vs non-scan)?
2. Does it run sequential ATPG for the non-scan FFs?
3. Does it report per-fault detection status and overall fault coverage?

If yes → all RQs are tractable.  
If FAN_ATPG cannot do this directly → need to investigate workaround (modify .sf file, use external fault simulator, or use FAN_ATPG's existing partial scan output).

---

## 6. Selection Methods to Implement

| Method | Description | Status |
|--------|-------------|--------|
| `random` | Uniform random selection | ✅ Existing |
| `co` | Sort by SCOAP CO (high observability first) | ✅ Existing |
| `combined` | Sort by CC0+CC1+2·CO | ✅ Existing |
| `mfvs` | Select FFs that break S-graph cycles (MFVS heuristic) | ❌ New |
| `mfvs_co` | MFVS first, then SCOAP CO for remaining budget | ❌ New |
| `co_mfvs` | SCOAP CO first, then MFVS for remaining budget | ❌ New |

**Removed** (old stress-based modes — no longer relevant to paper direction):
- `co_wear`, `combined_wear`, `co_wear_leveling`, `combined_wear_leveling`

These remain in the codebase but are not evaluated in the paper.

---

## 7. New Infrastructure Required

### 7.1 S-graph Construction

Build the FF dependency graph from the circuit netlist or .sf file:
- Node: each FF
- Edge FF_i → FF_j: exists if there is a combinational path from FF_i's Q-output to FF_j's D-input
- Required for: MFVS computation, sequential depth analysis, cycle detection

### 7.2 MFVS Heuristic

Minimum Feedback Vertex Set is NP-complete in general. Use the standard heuristic:
- Iteratively remove the FF on the most/longest cycles
- Continue until the S-graph is acyclic
- This gives the MFVS candidates; remaining scan budget goes to SCOAP ranking

### 7.3 Actual Fault Coverage Integration

Replace SCOAP coverage proxy with FAN_ATPG-measured stuck-at fault coverage:
- Input: partial scan configuration (which FFs are scan)
- Output: # detected faults / # total faults
- Must handle sequential ATPG for non-scan FF faults

### 7.4 Sequential Depth Measurement

For each partial scan configuration:
- Compute the sequential depth of the resulting partial-scan circuit (max timeframe depth needed)
- Track ATPG abort rate (faults aborted due to timeframe limit)

---

## 8. Evaluation Metrics

| Metric | Definition | How obtained |
|--------|------------|--------------|
| Stuck-at fault coverage | # detected / # total SAF | FAN_ATPG |
| ATPG abort rate | # aborted faults / # total faults | FAN_ATPG log |
| Sequential depth | Max timeframe depth in S-graph | S-graph analysis |
| S-graph cycle count | # cycles in non-scan FF subgraph | S-graph analysis |
| MFVS size | # FFs needed to break all cycles | MFVS algorithm |
| SCOAP CO (selected FFs) | Sum/avg CO of selected FFs | .sf file |
| Selection time | ms | ScanForge timer |

**Removed metrics** (stress-based, no longer relevant):
- toggle rate, stress variance, segment stress, hotspot count

---

## 9. Baselines

| Baseline | Source | Status |
|----------|--------|--------|
| Random | ScanForge existing | ✅ |
| SCOAP CO | ScanForge existing | ✅ |
| SCOAP Combined | ScanForge existing | ✅ |
| MFVS (Cheng & Agrawal 1990) | New implementation | ❌ |
| VTS'11 (Alawadhi test cube analysis) | Reference only (requires full-scan cubes) | Optional |

---

## 10. Experiment Matrix

### Circuits
All 12 ISCAS'89 benchmarks: s27, s208, s510, s953, s1196, s1238, s5378, s9234, s15850, s35932, s38417, s38584

### Scan ratios
10%, 25%, 50%, 75%, 100%

### Modes
`random`, `co`, `combined`, `mfvs`, `mfvs_co`

### No λ sweep needed
λ is a stress-tradeoff hyperparameter from the old direction; not relevant here.

---

## 11. Paper Structure

### 1. Introduction
- Modern partial scan is driven by physical constraints, not area saving
- Non-scan FFs create sequential ATPG difficulty (timeframe expansion)
- The FF selection problem: which FFs to scan to maximize coverage under budget
- Contributions

### 2. Background
- Sequential ATPG and timeframe expansion
- S-graph and sequential depth
- SCOAP metrics and their relationship to coverage
- Prior partial scan selection work (MFVS, ETD, SCOAP-based)

### 3. Method
- S-graph construction
- MFVS heuristic
- Selection modes
- Actual fault coverage evaluation flow

### 4. Experimental Results
- RQ1–RQ5 answers
- Circuit-by-circuit comparison
- Coverage vs scan ratio curves

### 5. Discussion
- When does SCOAP predict coverage well?
- When does MFVS outperform SCOAP?
- ATPG abort rate vs S-graph structure
- Limitations

### 6. Conclusion

---

## 12. Literature Review Targets

### Bucket A. Partial scan FF selection (coverage-focused)
- Cheng & Agrawal, IEEE TC 1990 — MFVS foundational paper
- Cheng & Agrawal, JETA 1993 — empirical testability (ETD)
- Agrawal et al., JETA 1993 — SCOAP-based partial scan analysis
- Hsiao, FTCS 1997 — beyond cycle cutting (state reachability)
- Alawadhi & Sinanoglu, VTS 2011 — most recent classical method

### Bucket B. Sequential ATPG complexity
- El-Maleh et al., IEEE TCAD 1996 — density of encoding as complexity driver
- Bounded ATPG / timeframe limits — standard industrial practice
- SAT-based sequential ATPG — modern approach

### Bucket C. SCOAP and testability measures
- Goldstein, DAC 1979 — original SCOAP definition
- Validation of SCOAP as coverage proxy

---

## 13. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| FAN_ATPG cannot do partial scan | Medium | Check first; if blocked, use alternative fault simulator or FAN_ATPG workaround |
| MFVS not extractable from .sf file | Medium | S-graph may need netlist-level info; check if .sf has enough connectivity |
| Sequential ATPG too slow on large circuits | High | Limit evaluation to small/medium circuits (s27–s5378); use timeout |
| Deadline pressure (June 16/17) | High | Prioritize: coverage measurement first, S-graph second, MFVS third |

---

## 14. Immediate Next Actions

1. **Verify FAN_ATPG partial scan mode** — can it accept a partial scan config and return actual coverage?
2. **Check .sf file for S-graph info** — does it have FF-to-FF connectivity, or do we need the netlist?
3. Replace SCOAP coverage proxy with actual coverage in existing pipeline
4. Implement S-graph construction
5. Implement MFVS heuristic
6. Run comparison experiment: random vs co vs mfvs on small circuits
7. Update progress_report.md with new direction

---

## 15. What to Keep from Old Implementation

| Component | Keep? | Note |
|-----------|-------|------|
| .sf parser | ✅ | SCOAP data still needed |
| SCOAP CO/combined selection | ✅ | Now a baseline, not the main method |
| Random selection | ✅ | Still baseline |
| Scan simulation (toggle counting) | ❌ | Not needed for new direction |
| Stress metrics | ❌ | Not relevant |
| Segment stress / hotspot | ❌ | Not relevant |
| co_wear / co_wear_leveling | ❌ | Not relevant |
| Sweep mode | ✅ | Reuse infrastructure, change metrics |
| CSV export | ✅ | Reuse |
| FAN_ATPG integration | ✅ | Extend to get actual fault coverage |
