# ScanForge

**ScanForge** is an open-source scan-chain DFT analysis tool.  
It uses [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG) as a backend to export circuit data, then performs scan-chain simulation and partial-scan analysis in a standalone C++ engine.

The repository is currently being refocused toward **sequential ATPG for partial-scan circuits under timing-driven scan exclusion**. The first implemented evaluation case is a timing-driven non-scan modeling flow: given a timing-criticality ranking, ScanForge excludes the top `x%` FFs from scan and analyzes the resulting single-chain partial-scan architecture.

Development in this repository should follow a **checklist-first, TDD-oriented workflow**. Before implementing a feature, create or update [checklist.md](./checklist.md) with the project-specific task definition, failing checks, implementation steps, and verification results.

---

## Features

| Feature | Description |
|---------|-------------|
| **Full scan analysis** | Simulate all FFs in scan chain, report switching activity |
| **Per-FF stress CSV** | Optional `--stress-csv` export: toggles, duty, run-length, composite stress score |
| **Segment stress CSV** | Sliding-window stress along the **current scan chain** (`--segment-window`, `--segment-csv`); hotspot flag from mean+1σ over segment averages |
| **Timing-driven scan exclusion case** | Load a timing-ranking CSV, exclude top `x%` FFs as non-scan, and analyze the remaining one-chain partial-scan architecture |
| **Partial scan selection** | SCOAP-CO, SCOAP-Combined, Random, **wear-aware** (`co_wear`, `combined_wear`), or **wear-leveling** (`co_wear_leveling`, `combined_wear_leveling`) greedy selection using segment max stress along the chain |
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
│   ├── segment_stress.h/cpp — segment-level / hotspot profiling
│   ├── main.cpp           — CLI entry point
│   └── Makefile
├── scripts/           # run_all.sh batch runner + per-circuit atpg scripts
├── results/           # Generated .sf files + sweep result tables (includes `leveling_demo.sf` for wear-leveling docs)
├── docs/              # Detailed flow, architecture, and results
├── checklist.md       # TDD-oriented development checklist for this project
└── README.md
```

---

## Development Workflow

For every code change:

1. define the task and acceptance criteria in `checklist.md`
2. identify the smallest failing check first
3. implement only enough code to make that check pass
4. rerun verification and record the result in `checklist.md`
5. only then move to the next checklist item

This project is not supposed to skip directly from idea to implementation. The checklist is the development contract.

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

# Timing-driven scan exclusion case
./src/scanforge FAN_ATPG/results/s27.sf \
  --timing-netlist FAN_ATPG/mod_netlist/s27.v \
  --exclude-ratio 0.10

# Exclusion sweep for the main spec ratios
./src/scanforge FAN_ATPG/results/s27.sf \
  --timing-netlist FAN_ATPG/mod_netlist/s27.v \
  --exclude-sweep \
  --exclude-summary-csv exclude_sweep.csv

# Batch sweep across multiple ISCAS'89 benchmarks
bash scripts/run_timing_exclusion_sweep.sh

# Summarize the master timing-exclusion CSV into one report-oriented row per circuit
python3 scripts/summarize_timing_exclusion.py \
  results/timing_exclusion/timing_exclusion_master.csv \
  results/timing_exclusion/report_summary.csv

# Per-FF stress profile (CSV) + segment-level sliding-window CSV (W=16)
./src/scanforge FAN_ATPG/results/s27.sf --stress-csv stress.csv \
  --segment-csv segment.csv --segment-window 16

# Partial scan sweep (25/50/75/100%) using SCOAP-CO strategy
./src/scanforge FAN_ATPG/results/s953.sf --sweep

# Single ratio with combined SCOAP metric
./src/scanforge FAN_ATPG/results/s5378.sf --partial 0.5 --mode combined

# Random baseline
./src/scanforge FAN_ATPG/results/s5378.sf --sweep --mode random

# Wear-aware combined metric (stress penalty λ=0.5)
./src/scanforge FAN_ATPG/results/s953.sf --partial 0.5 --mode combined_wear --lambda 0.5

# Coverage–stress tradeoff sweep (SCOAP proxy + stress + segment metrics + Pareto flags) to CSV
./src/scanforge FAN_ATPG/results/s5378.sf --sweep --mode combined_wear --lambda 0.5 \
  --segment-window 16 --summary-csv sweep.csv

# Wear-leveling partial scan (greedy; requires --segment-window; chain order = FF index order)
./src/scanforge FAN_ATPG/results/s5378.sf \
  --partial 0.5 \
  --mode combined_wear_leveling \
  --lambda 0.5 \
  --segment-window 16
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
  --segment-csv <path>      Write segment stress CSV (needs --segment-window > 0; full/--partial only)
  --segment-window <n>      Sliding window along chain for segment metrics (0 = off; also used in --sweep CSV)
  --partial <ratio>         Partial scan at given ratio (0.0–1.0)
  --timing-ranking <csv>    Timing-criticality CSV (ff_name,score or score,ff_name)
  --timing-netlist <v>      Gate-level netlist used to build a timing-depth proxy
  --exclude-ratio <ratio>   Mark top ratio of timing-critical FFs as non-scan and
                            analyze the remaining one-chain partial-scan architecture
  --exclude-sweep           Run timing-driven exclusion sweep at 5/10/15/20%
  --non-scan-csv <path>     Export aligned timing scores and the generated non-scan mask
  --timing-ranking-out <path>
                            Write the generated timing ranking to CSV when using
                            --timing-netlist
  --exclude-summary-csv <path>
                            Write exclusion-sweep summary CSV
  --mode <co|combined|random|co_wear|combined_wear|
                            co_wear_leveling|combined_wear_leveling>
                            FF selection strategy (default: co)
  --lambda <x>              Penalty weight for *_wear and *_wear_leveling (default: 0.5)
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

## Timing Ranking CSV Format

The timing-driven exclusion flow accepts a simple two-column CSV:

```csv
ff_name,score
U_G5,0.10
U_G6,0.90
U_G7,0.30
```

or equivalently:

```csv
score,ff_name
0.10,U_G5
0.90,U_G6
0.30,U_G7
```

The top `round(x% × N)` FFs are treated as **non-scan FFs**, and the remaining FFs are connected into the default single scan chain.

## Timing Proxy from Netlist

If you do not already have a timing-ranking CSV, ScanForge can build a first-order timing proxy directly from the gate-level netlist:

- identify scan FF instances (`SDFF_*`)
- trace the combinational logic feeding each FF `D` input
- use the resulting logic depth as a timing-criticality score

This is a library-agnostic structural timing proxy, not full STA. It is intended for the `timing-driven scan exclusion` evaluation case defined in the project spec.

## Current Evaluation Cases

For the current project spec, the intended comparison is among three evaluation cases:

- `full-scan ATPG`
- `partial-scan ATPG without sequential recovery`
- `partial-scan ATPG with sequential recovery`

At the current implementation stage, only the second case is concretely available in this repository's timing-driven exclusion flow:

- apply timing-driven scan exclusion at a chosen ratio `x`
- keep the excluded FFs as non-scan FFs
- connect all remaining FFs into the default single scan chain
- report the resulting partial-scan behavior without any sequential recovery step

In other words, the current implemented case corresponds to the exclusion flow with **no sequential state justification, no bounded sequential search, and no residual-fault recovery**. In the spec language, this is the `T = 0` comparison point for later sequential ATPG work.

### Canonical artifact for the current implemented case

The canonical per-circuit artifact for `partial-scan ATPG without sequential recovery` is one row in:

- `results/timing_exclusion/timing_exclusion_master.csv`

That row is produced by running:

```bash
./src/scanforge FAN_ATPG/results/<circuit>.sf \
  --timing-netlist FAN_ATPG/mod_netlist/<circuit>.v \
  --exclude-sweep \
  --exclude-summary-csv results/timing_exclusion/<circuit>_exclude_sweep.csv
```

The batch version is:

```bash
bash scripts/run_timing_exclusion_sweep.sh
```

### Comparison fields for the current implemented case

The current row currently contains these fields:

| Field | Meaning | Role in later comparison |
|---|---|---|
| `circuit` | benchmark name | grouping key |
| `case` | current evaluation case identifier | pairwise comparison key |
| `ratio` | timing-driven non-scan ratio | independent variable |
| `depth` | sequential depth; `0` for the current implemented case | pairwise comparison key |
| `coverage` | current primary coverage value | primary comparison field |
| `pattern_count` | number of directly applicable patterns | primary comparison field |
| `runtime_sec` | runtime for this row | primary comparison field |
| `non_scan_ff` | number of excluded FFs | architecture context |
| `scan_ff` | number of remaining scan FFs | architecture context |
| `coverage_proxy_combined` | combined SCOAP-based coverage proxy | primary comparison field |
| `coverage_proxy_co` | observability-oriented coverage proxy | secondary comparison field |
| `pattern_applicability` | fraction of existing patterns that remain directly usable | diagnostic field for the current implemented case |
| `switching_activity` | scan-shift activity proxy | cost/context field |
| `max_segment_stress` | worst segment stress under current chain model | structural context field |
| `segment_variance` | spread of segment stress | structural context field |
| `hotspot_count` | number of high-stress chain segments | structural context field |

For the current spec, later sequential recovery work should preserve pairwise comparability on:

- `circuit`
- `case`
- `ratio`
- `depth`
- `coverage`
- `pattern_count`
- `runtime_sec`

If the recovery flow later adds extra diagnostic fields, those should be added without changing the meaning of the columns above.

## Planned Sequential-Recovery Result Artifact

Before the sequential ATPG algorithm is fixed, the repository will treat the future `partial-scan ATPG with sequential recovery` result as a row-oriented CSV artifact.

The intended minimum row schema is:

| Field | Meaning |
|---|---|
| `circuit` | benchmark name |
| `case` | one of `full_scan`, `partial_scan_no_recovery`, `partial_scan_with_recovery` |
| `ratio` | timing-driven non-scan ratio |
| `depth` | sequential search depth; `0` means no sequential recovery |
| `coverage` | primary coverage result for the case |
| `pattern_count` | number of generated or retained test patterns |
| `runtime_sec` | runtime for the case |

The intended comparison logic is:

- `full_scan` vs `partial_scan_no_recovery`
- `partial_scan_no_recovery` vs `partial_scan_with_recovery`
- `partial_scan_with_recovery` vs `full_scan`

For this schema, the current timing-driven exclusion flow corresponds to:

- `case = partial_scan_no_recovery`
- `depth = 0`

If the first sequential-recovery prototype still relies on proxy coverage rather than true fault coverage, the column name may temporarily map to a proxy quantity internally, but the row shape above should remain unchanged so later reporting scripts do not need to be redesigned.

---

## Partial Scan Selection Strategies

ScanForge ranks FFs by their SCOAP testability metrics and selects the **K hardest-to-test** FFs for scanning:

| Mode | Score formula | Rationale |
|------|---------------|-----------|
| `co`       | `CO`              | Observability — hard-to-observe FFs benefit most from scan |
| `combined` | `CC0 + CC1 + 2×CO` | Overall testability difficulty |
| `random`   | Random shuffle    | Baseline for comparison |
| `co_wear`       | `norm(CO) − λ × norm(stress)` | Same priority as `co`, penalizing high **full-scan** per-FF stress |
| `combined_wear` | `norm(CC0+CC1+2×CO) − λ × norm(stress)` | Same as `combined` with stress penalty |
| `co_wear_leveling` | Greedy: maximize `norm(CO) − λ × (max_segment_avg_stress / max_full_scan_stress)` on the tentative chain | Segment term is **dimensionless** (0–1 scale when segment averages stay within full-scan per-FF range). Uses **full-scan** `stress_score` as a static wear proxy (not re-simulated each greedy step). Chain order = **ascending FF index** among selected FFs. |
| `combined_wear_leveling` | Same with `norm(CC0+CC1+2×CO)` | Same as `co_wear_leveling`. |

`max_full_scan_stress` is `max_i` full-scan `stress_score` over all FFs in the circuit (same vector as `*_wear` modes). Normalization uses min–max over all FFs for SCOAP-derived testability (`stress_score` for wear modes: `--stress-csv` full-scan simulation). For `*_wear`, higher score = higher priority. For `*_wear_leveling`, **`λ = 0`** yields the same **selected FF set** as `co` / `combined` (verified on `results/s27.sf` and synthetic `results/leveling_demo.sf`). With **`segment_window = 1`**, each segment’s average equals a single FF’s stress, so the penalty tracks **per-FF** stress along the index-ordered chain (related to `*_wear`, which penalizes normalized per-FF stress in a single global sort).

**Scope note:** Selection optimizes the **proxy** above; reported `max_segment_stress` after `--partial` is from **simulated** partial-scan shift activity and may differ from the greedy objective.

### Wear-leveling illustration (synthetic circuit)

Small reproducible example `results/leveling_demo.sf` (8 FFs, 40 random patterns, fixed seed) shows how modes diverge under stress pressure. Partial scan **50%** (K=4), sliding window **W=2**, segment metrics from **post-simulation** partial chain:

| Mode | λ | Coverage proxy (combined) | Max segment stress | Segment variance | Hotspot count |
|------|---|---------------------------:|-------------------:|-----------------:|---------------:|
| `combined` | — | 0.6577 | 0.3156 | 0.0001 | 1 |
| `combined_wear` | 0.5 | 0.6538 | 0.3438 | 0.0000 | 1 |
| `combined_wear_leveling` | 0.5 | 0.6577 | 0.3156 | 0.0001 | 1 |
| `combined_wear` | 2.0 | 0.5500 | 0.3250 | 0.0000 | 1 |
| `combined_wear_leveling` | 2.0 | 0.6538 | 0.3438 | 0.0000 | 1 |

At **λ = 0.5**, wear-leveling keeps the same high-testability set as `combined` while **per-FF wear** (`combined_wear`) trades coverage for lower per-FF stress picks. At **λ = 2**, objectives differ: `combined_wear` lowers simulated max segment stress more aggressively at a larger coverage-proxy cost, while wear-leveling follows its **segment/full-scan** greedy objective and can report **higher** simulated max segment stress here — so always validate on your target benchmarks (`scripts/run_leveling_sweep.sh` once `FAN_ATPG/results/*.sf` exist).

**Benchmark checklist:** After generating `FAN_ATPG/results/<circuit>.sf`, run `scripts/run_leveling_sweep.sh` and compare sweep CSVs. **`λ = 0`** parity for wear-leveling vs `combined` was checked on **`results/s27.sf`** (3 FFs) and on **`results/leveling_demo.sf`**; re-run the same `--partial` / `--segment-window` command on **s953** and **s5378** before publication tables (this workspace clone may not ship those `.sf` files).

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

`--sweep` prints **Ratio, K, Toggles, Switching Activity**, plus **MaxStress**, **Stress Variance**, and **Stress Imbalance** (max / mean of full-scan `stress_score` over selected FFs).

| Ratio | K  | Toggles | Switch Activity |
|-------|----|---------|-----------------|
| 25%   | 7  | 1690    | 0.3875          |
| 50%   | 15 | 7645    | 0.3818          |
| 75%   | 22 | 15703   | 0.3645          |
| 100%  | 29 | 24933   | 0.3331          |

### Partial Scan Sweep — s5378 (179 FFs, SCOAP-CO)

| Ratio | K   | Toggles   | Switch Activity |
|-------|-----|-----------|-----------------|
| 25%   | 45  | 109,220   | 0.4610          |
| 50%   | 90  | 410,140   | 0.4328          |
| 75%   | 134 | 945,111   | 0.4499          |
| 100%  | 179 | 1,703,514 | 0.4544          |

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
