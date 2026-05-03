# ScanForge

**ScanForge** is an open-source scan chain DFT (Design for Testability) analysis tool.  
It uses [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG) as a backend to export circuit data, then performs scan chain simulation and **partial scan selection** via SCOAP testability metrics — all in a standalone C++ engine.

---

## Features

| Feature | Description |
|---------|-------------|
| **Full scan analysis** | Simulate all FFs in scan chain, report switching activity |
| **Per-FF stress CSV** | Optional `--stress-csv` export: toggles, duty, run-length, composite stress score |
| **Partial scan selection** | Select a subset of FFs using SCOAP-CO, SCOAP-Combined, stress-aware combined, or Random |
| **Ratio sweep** | Sweep 25/50/75/100% ratios in one command (`--sweep`) |
| **SCOAP export** | FAN_ATPG fork computes CC0/CC1/CO and exports them to `.sf` format |
| **12 ISCAS'89 benchmarks** | Scripts and results for s27 through s38584 |

---

## Repository Structure

```
ScanForge/
├── FAN_ATPG/          # git submodule — Rueilian/FAN_ATPG (minimal fork: SCOAP export only)
├── src/               # ScanForge C++ engine
│   ├── scan_chain.h/cpp   — .sf parser + scan shift simulator
│   ├── partial_scan.h/cpp — SCOAP-based FF selection & sweep
│   ├── main.cpp           — CLI entry point
│   └── Makefile
├── scripts/           # run_all.sh batch runner + per-circuit atpg scripts
├── results/           # Generated .sf files + sweep result tables
├── docs/              # Detailed flow, architecture, and results
└── README.md
```

---

## Quick Start

### 1. Clone (with submodule)

```bash
git clone --recurse-submodules https://github.com/Rueilian/ScanForge.git
cd ScanForge
```

### 2. Build FAN_ATPG

```bash
sudo apt install bison flex   # if not installed
cd FAN_ATPG
make
cd ..
```

### 3. Build ScanForge engine

```bash
cd src
make
cd ..
```

### 4. Run ATPG on a circuit

```bash
cd FAN_ATPG
mkdir -p results
./bin/opt/fan -f script/fanScripts/atpg_s27.script
# → produces results/s27.sf
cd ..
```

### 5. Analyze with ScanForge

```bash
# Full scan
./src/scanforge FAN_ATPG/results/s27.sf

# Per-FF stress profile (CSV) + sanity lines on stdout
./src/scanforge FAN_ATPG/results/s27.sf --stress-csv stress.csv

# Partial scan sweep (25/50/75/100%) using SCOAP-CO strategy
./src/scanforge FAN_ATPG/results/s953.sf --sweep

# Single ratio with combined SCOAP metric
./src/scanforge FAN_ATPG/results/s5378.sf --partial 0.5 --mode combined

# Random baseline
./src/scanforge FAN_ATPG/results/s5378.sf --sweep --mode random

# Coverage–stress tradeoff sweep (SCOAP proxy + stress + Pareto flags) to CSV
./src/scanforge FAN_ATPG/results/s5378.sf --sweep --mode combined_wear --lambda 0.5 --summary-csv sweep.csv
```

---

## CLI Reference

```
Usage: scanforge [options] <scan_data.sf>

Options:
  (no options)              Full scan analysis
  --sweep                   Sweep partial scan ratios 25/50/75/100%
  --coverage                Coverage estimate sweep
  --fine                    Finer sweep steps (with --sweep / --coverage)
  --csv                     With --coverage: CSV to stdout. With --sweep: CSV to stdout
                            unless --summary-csv is set
  --summary-csv <path>      With --sweep: write tradeoff sweep CSV (coverage proxy, stress, score)
  --stress-csv <path>       Write per-FF scan stress metrics (full or --partial run)
  --partial <ratio>         Partial scan at given ratio (0.0–1.0)
  --mode <co|combined|combined_wear|random>
                            FF selection strategy (default: co)
  --lambda <value>          Wear blend for combined_wear (0 matches combined)
  --coverage-proxy <co|combined|controllability>
                            Which SCOAP sums define coverage_proxy in sweep / --partial
  -h, --help                Print this help
```

---

## The `.sf` File Format

FAN_ATPG exports a `.sf` (ScanForge data) file with:

```
SCAN_DATA 1.0
NUM_FF <N>
FF_NAMES <name0> <name1> ... <nameN-1>
SCOAP  <cc0_0> <cc1_0> <co_0>  <cc0_1> <cc1_1> <co_1> ...
PATTERNS <P>
PPI <val0> <val1> ... <valN-1>
PPO <val0> <val1> ... <valN-1>
...
```

Values: 0=L, 1=H, 2=X, 3=D, 4=B, 5=Z

---

## Partial Scan Selection Strategies

ScanForge ranks FFs by their SCOAP testability metrics and selects the **K hardest-to-test** FFs for scanning:

| Mode | Score formula | Rationale |
|------|---------------|-----------|
| `co`       | `CO`              | Observability — hard-to-observe FFs benefit most from scan |
| `combined` | `CC0 + CC1 + 2×CO` | Overall testability difficulty |
| `random`   | Random shuffle    | Baseline for comparison |

Higher SCOAP score = harder to test = higher priority for inclusion in scan chain.

---

## Results on ISCAS'89 Benchmarks

### Full Scan Switching Activity

| Circuit | FFs | Patterns | Shift Cycles | Toggles | Switch Activity |
|---------|-----|----------|--------------|---------|-----------------|
| s27     | 3   | 5        | 15           | 19      | 0.4222          |
| s208    | 8   | 29       | 232          | 555     | 0.2990          |
| s510    | 6   | 59       | 354          | 984     | 0.4633          |
| s953    | 29  | 89       | 2581         | 24933   | 0.3331          |
| s1196   | 18  | 134      | 2412         | 20854   | 0.4803          |
| s1238   | 18  | 145      | 2610         | 22683   | 0.4828          |
| s5378   | 179 | 117      | 20943        | 1703514 | 0.4544          |
| s9234   | 211 | 156      | 32916        | 3539659 | 0.5096          |
| s15850  | 534 | 133      | 71022        | 17928805| 0.4727          |
| s35932  | 1728| 21       | 36288        | 17332183| 0.2764          |
| s38417  | 1636| 105      | 171780       | 133742630| 0.4759         |
| s38584  | 1426| 133      | 189658       | 134638017| 0.4978         |

### Partial Scan Sweep — s953 (29 FFs, SCOAP-CO)

| Ratio | K  | Shift Cycles | Toggles | Switch Activity |
|-------|----|-------------|---------|-----------------|
| 25%   | 7  | 623         | 1690    | 0.3875          |
| 50%   | 15 | 1335        | 7645    | 0.3818          |
| 75%   | 22 | 1958        | 15703   | 0.3645          |
| 100%  | 29 | 2581        | 24933   | 0.3331          |

### Partial Scan Sweep — s5378 (179 FFs, SCOAP-CO)

| Ratio | K   | Shift Cycles | Toggles   | Switch Activity |
|-------|-----|-------------|-----------|-----------------|
| 25%   | 45  | 5,265       | 109,220   | 0.4610          |
| 50%   | 90  | 10,530      | 410,140   | 0.4328          |
| 75%   | 134 | 15,678      | 945,111   | 0.4499          |
| 100%  | 179 | 20,943      | 1,703,514 | 0.4544          |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FAN_ATPG (submodule)                                           │
│   build_circuit → add_fault → run_atpg                         │
│   → add_scan_chains -o results/circuit.sf                       │
│      • calls calSCOAP() to compute CC0/CC1/CO per FF            │
│      • exports FF names, SCOAP values, PPI/PPO patterns         │
└────────────────────────────┬────────────────────────────────────┘
                             │  .sf file
┌────────────────────────────▼────────────────────────────────────┐
│  ScanForge Engine (src/)                                        │
│   parseScanData()   — reads .sf, builds ScanData struct         │
│   selectFFs()       — ranks FFs by SCOAP, returns chain[K]      │
│   simulate()        — scan-shift simulation on chain            │
│   sweepPartialScan()— iterates over ratios, prints table        │
└─────────────────────────────────────────────────────────────────┘
```

---

## How Scan Shift Simulation Works

For each test pattern:
1. Load phase: shift in PPI values through the scan chain (K shifts)
   - Chain order: FF[chain[0]] → FF[chain[1]] → … → FF[chain[K-1]]
   - Each shift: the entering value is the previous FF's state (or SI=0 for first)
2. Capture phase: latch PPO values into the chain
3. A toggle is counted each time a FF's state changes between consecutive shifts

**Switching Activity** = total toggles / (K × total shift cycles)

---

## Based On

- [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG) — NTU Laboratory of Dependable Systems, MIT License
- ISCAS'89 benchmark circuits

## License

MIT License — see [LICENSE](LICENSE).

