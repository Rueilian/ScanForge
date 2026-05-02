# ScanForge — Detailed Flow, Architecture & Results

## 1. Project Overview

ScanForge implements a **partial scan chain selection** flow for VLSI design-for-testability (DFT).  
Given a circuit netlist and its ATPG test patterns, ScanForge:

1. Computes **SCOAP** (Sandia Controllability/Observability Analysis Program) metrics for every flip-flop
2. Selects the **K most testability-critical FFs** (partial scan) using CC0, CC1, CO values
3. Simulates the **scan-shift sequence** and reports switching activity

The tool is evaluated on all 12 ISCAS'89 benchmark circuits.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  FAN_ATPG (Rueilian/FAN_ATPG — submodule)                           │
│                                                                      │
│   Script commands:                                                   │
│     build_circuit <netlist.v>                                        │
│     add_fault                                                        │
│     run_atpg                                                         │
│     add_scan_chains -o results/<circuit>.sf   ← key export step     │
│                                                                      │
│   add_scan_chains -o:                                                │
│     • calls Atpg::calSCOAP() to compute CC0/CC1/CO for all gates    │
│     • extracts PPI gates (FF Q-outputs) at indices [numPI..numPI+N) │
│     • writes .sf file: FF names, SCOAP values, PPI/PPO patterns     │
└────────────────────────────┬─────────────────────────────────────────┘
                             │  <circuit>.sf
┌────────────────────────────▼─────────────────────────────────────────┐
│  ScanForge Engine (src/)                                             │
│                                                                      │
│  parseScanData(path)  → ScanData { numFF, ffs[], patterns[] }       │
│                                                                      │
│  selectFFs(data, K, mode):                                           │
│    SCOAP_CO       → rank by CO  (observability)                     │
│    SCOAP_COMBINED → rank by CC0+CC1+2×CO                            │
│    RANDOM         → random shuffle                                   │
│    → returns sorted chain[K] of FF indices                          │
│                                                                      │
│  simulate(data, chain):                                              │
│    for each pattern:                                                 │
│      shift-in PPI values through chain (K cycles)                   │
│      count toggles per shift                                        │
│    → ScanResult { shiftCycles, toggles, switchActivity, perFF[] }  │
│                                                                      │
│  sweepPartialScan(data, {0.25,0.5,0.75,1.0}, mode):                 │
│    → prints ratio/K/cycles/toggles/activity table                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. SCOAP Metrics

SCOAP assigns each gate a **controllability** (how hard it is to set to 0/1) and **observability** (how hard it is to observe at a primary output):

| Metric | Symbol | Meaning | Good for scan? |
|--------|--------|---------|---------------|
| CC0 | Combinational Controllability 0 | Cost to force gate output to 0 | Higher = harder |
| CC1 | Combinational Controllability 1 | Cost to force gate output to 1 | Higher = harder |
| CO  | Combinational Observability     | Cost to propagate fault to PO  | Higher = harder |

**Partial scan strategy**: Select FFs with highest CO (or combined score) — these are the hardest FFs to test without scan access, so adding them to the scan chain gives the maximum fault coverage gain per FF scanned.

### Computation Fix

The original `calSCOAP()` in FAN_ATPG processed gates in forward gateID order for both CC and CO.  
CC requires a **forward** pass (PI→PO): correct.  
CO requires a **reverse** pass (PO→PI): the original code was wrong.

ScanForge's fork fixes this by reversing the CO loop:
```cpp
// Fixed: reverse topological order for co_ (PO → PI)
for (int gateID = pCircuit_->totalGate_ - 1; gateID >= 0; --gateID)
```

This yields correct non-zero CO values (e.g. s27: U_G6 CO=13, vs. 0 before fix).

---

## 4. The `.sf` File Format

```
SCAN_DATA 1.0
NUM_FF <N>
FF_NAMES <name0> <name1> ... <nameN-1>
SCOAP  <cc0_0> <cc1_0> <co_0>  <cc0_1> <cc1_1> <co_1> ...
PATTERNS <P>
PPI <val0> <val1> ... <valN-1>
PPO <val0> <val1> ... <valN-1>
... (PPI/PPO pair repeated P times)
```

Value encoding: 0=Low, 1=High, 2=X (unknown), 3=D (fault sensitized), 4=B (D-bar), 5=Z (high-Z)

---

## 5. Scan Shift Simulation

For each test pattern:
- **Load phase** (K shift cycles): shift PPI values through the scan chain  
  - Cycle t: chain[j] captures chain[j-1]'s state (or SI=0 for j=0)
- A **toggle** is counted when a FF's state changes between two consecutive shift cycles

```
Switching Activity = total_toggles / (K × total_shift_cycles)
```

where `total_shift_cycles = K × P` (K FFs × P patterns).

---

## 6. Benchmark Results

### 6.1 Full Scan — All 12 ISCAS'89 Circuits

| Circuit | FFs | Patterns | Shift Cycles | Toggles     | Switch Activity |
|---------|-----|----------|--------------|-------------|-----------------|
| s27     | 3   | 5        | 15           | 16          | 0.3556          |
| s208    | 8   | 29       | 232          | 555         | 0.2990          |
| s510    | 6   | 59       | 354          | 984         | 0.4633          |
| s953    | 29  | 89       | 2,581        | 24,933      | 0.3331          |
| s1196   | 18  | 134      | 2,412        | 20,854      | 0.4803          |
| s1238   | 18  | 145      | 2,610        | 22,683      | 0.4828          |
| s5378   | 179 | 117      | 20,943       | 1,703,514   | 0.4544          |
| s9234   | 211 | 156      | 32,916       | 3,539,659   | 0.5096          |
| s15850  | 534 | 133      | 71,022       | 17,928,805  | 0.4727          |
| s35932  | 1728| 21       | 36,288       | 17,332,183  | 0.2764          |
| s38417  | 1636| 105      | 171,780      | 133,742,630 | 0.4759          |
| s38584  | 1426| 133      | 189,658      | 134,638,017 | 0.4978          |

### 6.2 Partial Scan Sweep — s27 (3 FFs)

| Ratio | K | Shift Cycles | Toggles | Activity | Selected FFs |
|-------|---|--------------|---------|----------|-------------|
| 25%   | 1 | 5            | 2       | 0.4000   | U_G6        |
| 50%   | 2 | 10           | 7       | 0.3500   | U_G6, U_G7  |
| 75%   | 2 | 10           | 7       | 0.3500   | U_G6, U_G7  |
| 100%  | 3 | 15           | 16      | 0.3556   | U_G5, U_G6, U_G7 |

U_G6 (CO=13) is selected first — it has the highest observability cost.

### 6.3 Partial Scan Sweep — s953 (29 FFs, SCOAP-CO)

| Ratio | K  | Shift Cycles | Toggles | Activity |
|-------|----|-------------|---------|----------|
| 25%   | 7  | 623         | 1,690   | 0.3875   |
| 50%   | 15 | 1,335       | 7,645   | 0.3818   |
| 75%   | 22 | 1,958       | 15,703  | 0.3645   |
| 100%  | 29 | 2,581       | 24,933  | 0.3331   |

### 6.4 Partial Scan Sweep — s5378 (179 FFs, SCOAP-CO)

| Ratio | K   | Shift Cycles | Toggles     | Activity |
|-------|-----|-------------|-------------|----------|
| 25%   | 45  | 5,265       | 109,220     | 0.4610   |
| 50%   | 90  | 10,530      | 410,140     | 0.4328   |
| 75%   | 134 | 15,678      | 945,111     | 0.4499   |
| 100%  | 179 | 20,943      | 1,703,514   | 0.4544   |

### 6.5 Partial Scan Sweep — s9234 (211 FFs, SCOAP-CO)

| Ratio | K   | Shift Cycles | Toggles     | Activity |
|-------|-----|-------------|-------------|----------|
| 25%   | 53  | 8,268       | 211,006     | 0.4815   |
| 50%   | 106 | 16,536      | 852,578     | 0.4864   |
| 75%   | 158 | 24,648      | 1,958,384   | 0.5029   |
| 100%  | 211 | 32,916      | 3,539,659   | 0.5096   |

### 6.6 Partial Scan Sweep — s15850 (534 FFs, SCOAP-CO)

| Ratio | K   | Shift Cycles | Toggles     | Activity |
|-------|-----|-------------|-------------|----------|
| 25%   | 134 | 17,822      | 1,116,297   | 0.4674   |
| 50%   | 267 | 35,511      | 4,489,209   | 0.4735   |
| 75%   | 401 | 53,333      | 10,138,723  | 0.4741   |
| 100%  | 534 | 71,022      | 17,928,805  | 0.4727   |

---

## 7. Key Observations

1. **Switching activity is relatively stable across ratios** for most circuits (~0.46–0.50). This suggests the ATPG patterns have fairly uniform toggle density across FFs, regardless of which ones are selected.

2. **s35932 has notably lower activity (~0.26)** — its large number of FFs (1728) relative to few patterns (21) means the scan chain is mostly shifting stable values.

3. **SCOAP-CO selection is meaningful**: for s27, U_G6 is selected first with CO=13 (the only FF not directly feeding a PO), which is the intuitively correct choice.

4. **Shift cycle reduction scales linearly** with ratio, as expected (K × P patterns). This is the primary hardware cost metric for partial scan.

---

## 8. How to Run All Circuits

```bash
cd FAN_ATPG
mkdir -p results
for s in s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584; do
    ./bin/opt/fan -f script/fanScripts/atpg_$s.script
done
cd ..

for s in s27 s208 s510 s953 s1196 s1238 s5378 s9234 s15850 s35932 s38417 s38584; do
    echo "=== $s ===" && ./src/scanforge FAN_ATPG/results/$s.sf --sweep
done
```

---

## 9. Dependencies

| Component | Version | Purpose |
|-----------|---------|---------|
| g++       | ≥ 7     | Build ScanForge engine |
| bison, flex | system | Build FAN_ATPG |
| FAN_ATPG  | fork    | ATPG + SCOAP export backend |

---

## 10. Future Work

- **Chain reordering**: reorder FFs in scan chain to minimize switching activity
- **Multi-chain**: split FFs across K chains (reduces test time at cost of scan-in/out pins)
- **Fault coverage estimation**: estimate coverage loss from partial scan selection
- **Power-aware selection**: minimize scan shift power as primary objective
