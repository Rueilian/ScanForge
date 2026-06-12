# ScanForge — Sequential ATPG Optimization Designs

This document outlines the detailed algorithms and implementation plans for two proposed optimizations to reduce the complexity of Time-Frame Expansion (TFE) in sequential ATPG.

---

## Design 1: Cone-of-Influence (COI) Guided Selective Unrolling

### 1. Objective
Reduce memory footprint and search space by unrolling only the gates that structurally participate in the controllability and observability path of the target fault, instead of duplicating the entire netlist for all $T$ frames.

### 2. Algorithmic Flow
For a target fault $f$ at gate $G_f$:
1. **Extract Structural Cones**:
   * $ControllabilityCone(G_f)$: All gates in the transitive fan-in (backward logic cone) of $G_f$.
   * $ObservabilityCone(G_f)$: All gates in the transitive fan-out (forward logic cone) of $G_f$ leading to any Primary Output (PO) or scan Pseudo-Primary Output (PPO).
2. **On-Demand Time-Frame Unrolling**:
   * For the final observation frame $T-1$, instantiate only gates in $ControllabilityCone(G_f) \cup ObservabilityCone(G_f)$.
   * For previous frames $t < T-1$:
     * Identify the set of non-scan FFs $N_{active}(t+1)$ whose outputs (PPIs) are active in frame $t+1$.
     * Instantiate gate $g$ at frame $t$ **only if** $g$ is in the transitive fan-in cone of any $FF \in N_{active}(t+1)$.
     * As $t$ goes backward ($T-2 \rightarrow 0$), the number of active FFs and gates shrinks significantly (exponential decay in typical circuits).
3. **ATPG Solver Mapping**:
   * Skipped gates are modeled as constant unknown `X` values.
   * Backtrace solver ignores decisions on gates outside the active cones.

### 3. C++ Implementation Plan in `FAN_ATPG`
* In `circuit.cpp`, implement `buildSelectiveTimeFrames(int targetFaultGateId, int T)`.
* Maintain a 2D boolean array `isGateNeeded[time_frame][gate_id]`.
* Walk backward from the target gate to populate `isGateNeeded` and construct the unrolled gate array dynamically.

---

## Design 2: Two-Phase State Justification

### 1. Objective
Decouple the fault sensitization task from the sequential state justification task. This avoids the backtrack explosion of trying to solve both simultaneously on a large unrolled circuit.

### 2. Algorithmic Flow
1. **Phase 1: Combinational ATPG (with Pseudo-Controllability)**:
   * Treat all non-scan FFs as fully controllable Pseudo-Inputs at $T=1$.
   * Run the standard combinational ATPG engine.
   * If a pattern is generated, extract the required state vector $S_{req}$ (the values assigned to non-scan FFs).
     * Example: $S_{req} = \{FF_3: 1, FF_8: 0\}$ (often only a very small subset of FFs need specific values).
2. **Phase 2: Bounded Sequential Justification**:
   * Perform a backward state search to check if the partial state $S_{req}$ can be justified from the initial state (all $X$ or reset state) in $T$ clock cycles.
   * **Backward State Justification BFS/DFS**:
     * Start with target state $S_{req}$ at frame $t$.
     * Determine the required gate values at frame $t$ to justify $S_{req}$.
     * Read the required values at the non-scan FF inputs at frame $t$, which defines the new target state $S'_{req}$ for the previous frame $t-1$.
     * Repeat until frame 0 is reached or a conflict occurs.
   * If a valid PI sequence is found, prepend it to the combinational pattern. Otherwise, backtrack in Phase 1 and look for another combinational pattern.

### 3. C++ Implementation Plan in `FAN_ATPG`
* Keep the circuit combinational ($T=1$).
* Extend the main ATPG loop: after `run_atpg` finds a pattern for a fault, intercept the PPI assignments.
* Implement a `StateJustifier` class that performs backward BFS search on the single-frame circuit structure across $T$ virtual steps, keeping track of required state transitions without duplicating the physical gates.
