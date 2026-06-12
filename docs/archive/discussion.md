# ScanForge — Discussion and Decisions Log

This document records the major discussions, design trade-offs, and decisions made during the development of the ScanForge project.

---

## 1. Project Topic Redirection (May 2026)
* **Context**: The project was originally titled *"Stress-Aware Partial Scan Selection"* and targeted scan shift power reduction on ISCAS'89 benchmarks using a SCOAP coverage proxy.
* **Decision**: Redirected the topic to *"Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits"* on ITC'99 benchmarks. 
* **Rationale**: Shifted focus to a more industrially relevant problem using a true stuck-at fault coverage metric (via `FAN_ATPG` simulation) instead of a structural proxy.

---

## 2. Base-Gate Netlist Synthesis & Cell Library (June 9, 2026)
* **Context**: Synthesizing ITC'99 benchmarks with the full Nangate45 library produced complex compound gates (OAI/AOI) that caused low coverage baseline anomalies in the ATPG engine.
* **Decision**: 
  1. Synthesize all netlists using `NangateOpenCellLibrary_base.lib` which restricts cells to `INV`, `AND`, `OR`, `NAND`, `NOR`, `XOR`, and `MUX2`.
  2. Forbid `OAI*/AOI*` compound gates (forcing ABC to map them to primitives).
  3. Revert complex OAI/AOI modeling extensions in `FAN_ATPG`, keeping only `Gate::MUX` modeling.
* **Rationale**: Restored a clean, reproducible gate-level representation that matches the ATPG engine's modeling capabilities while achieving high full-scan coverage baselines (>91%).

---

## 3. Scan Protocol & Coverage Metrics Definition (June 9, 2026)
* **Context**: Including stuck-at faults on async reset pins in the fault coverage denominator under-represented the true efficiency of the ATPG engine because reset pins are held inactive during capture cycle in commercial practice.
* **Decision**: Adopted `FC_scan` (excluding async reset pins from the denominator) as the primary coverage metric, aligning with commercial tools (e.g., TetraMAX, Modus).
* **Rationale**: Restored consistency between academic evaluation and real-world DFT protocols.

---

## 4. Multi-Frame SAF Observability & Replication (June 9, 2026)
* **Context**: Multi-frame unrolling for stuck-at faults had consistency issues between ATPG search and fault simulation.
* **Decision**: 
  1. Stuck-at faults are modeled on the final observation frame consistently across ATPG search, fault injection, and fault simulation.
  2. The `Pattern` structure and Simulator were updated to store and replay scan PPI values across all time frames (instead of only frame 0).
* **Rationale**: Ensured complete reproducibility between ATPG patterns and in-memory fault simulation coverage.
