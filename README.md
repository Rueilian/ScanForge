# ScanForge

Sequential ATPG research pipeline for evaluating **progressive T=1→T=2→T=4 fault-coverage gain** on timing-driven partial-scan ITC'99 benchmarks.

**Research focus:** Progressive T=1→T=2→T=4 **pipeline gain** at **10%** non-scan exclusion only.

**Authoritative direction:** [`docs/spec.md`](./docs/spec.md) | [`docs/final_report.md`](./docs/final_report.md) | [`docs/README.md`](./docs/README.md)

## Features

| Feature | Description |
|---------|-------------|
| **Full scan analysis** | Simulate all FFs in scan chain, report switching activity |
| **Per-FF stress CSV** | Optional `--stress-csv` export: toggles, duty, run-length, composite stress score |
| **Segment stress CSV** | Sliding-window stress along the **current scan chain** (`--segment-window`, `--segment-csv`); hotspot flag from mean+1σ over segment averages |
| **Partial scan selection** | SCOAP-CO, SCOAP-Combined, Random, **wear-aware** (`co_wear`, `combined_wear`), or **wear-leveling** (`co_wear_leveling`, `combined_wear_leveling`) greedy selection using segment max stress along the chain |
| **Ratio sweep** | Sweep 25/50/75/100% ratios in one command (`--sweep`) |
| **Sequential graph — cycle breaking** | Parse a gate-level Verilog netlist, build the FF-to-FF **combinational reachability** graph (Tarjan SCC-based, O(V×(V+E))), and select a heuristic FVS to break all directed cycles; scales to 1 728 FFs and 32 000+ edges |
| **Sequential graph — depth reduction** | After cycle breaking, greedily remove additional FFs to reduce the longest sequential path to a user-defined maximum (`--seq-depth`) |
| **SCOAP export** | FAN_ATPG fork computes CC0/CC1/CO and exports them to `.sf` format |
| **12 ISCAS'89 benchmarks** | Scripts and results for s27 through s38584 |

---

## Repository Structure

```
ScanForge/
├── FAN_ATPG/              # git submodule — FAN_ATPG with PARTIAL_SEQUENTIAL mode
│   ├── bin/opt/fan        # compiled ATPG binary
│   ├── mod_netlist/       # synthesized ITC'99 gate-level Verilog (b03–b15)
│   ├── techlib/           # NanGate45 .lib and .mdt files
│   └── pkg/core/src/      # core ATPG engine (atpg.cpp, circuit.cpp, etc.)
├── itc99_rtl/             # git submodule — ITC'99 RTL source (b03–b15)
├── scripts/               # pipeline scripts
│   ├── synth_itc99.sh         — Yosys synthesis → mod_netlist/b*.v
│   ├── fixup_verilog.py       — post-process Yosys output for FAN compatibility
│   ├── run_progressive_residual.py      — T=1→T=2→T=4 pipeline (primary)
│   ├── run_progressive_residual_sweep.py — Tier A batch runner
│   ├── gen_nonscan_masks.sh           — OpenSTA + mask generation
│   ├── generate_figures.py            — report figures
│   └── archive/                       — legacy runners (T=8 sweep, ISCAS tools)
├── masks/                 # non-scan FF lists: masks/<circuit>_x10.mask
├── results/
│   ├── progressive_residual_summary.csv — 8-run pipeline results (@10%)
│   ├── phase_d_fullscan_dataset.csv     — B2 full-scan FC_scan_coll
│   └── archive/                         — superseded CSVs and legacy sweeps
├── docs/
│   ├── README.md            — doc index (active vs archive)
│   ├── spec.md
│   └── final_report.md
├── src/                   # ScanForge C++ engine
│   ├── scan_chain.h/cpp       — .sf parser + scan-shift simulator
│   ├── partial_scan.h/cpp     — SCOAP-based FF selection & sweep
│   ├── segment_stress.h/cpp   — segment-level / hotspot profiling
│   ├── seq_graph.h/cpp        — sequential FF graph: cycle breaking + depth reduction
│   ├── verilog_netlist.cpp    — lightweight structural Verilog parser (Q→D FF edges)
│   ├── timing_exclusion.h/cpp — timing-driven non-scan FF exclusion
│   ├── netlist_timing_proxy.h/cpp — timing-depth proxy from gate-level netlist
│   ├── main.cpp               — CLI entry point
│   └── Makefile
```

---

## Quick Start

### 1. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/Rueilian/ScanForge.git
cd ScanForge
```

### 2. Build FAN_ATPG

```bash
sudo apt install bison flex
cd FAN_ATPG && make -j$(nproc) && cd ..
# binary: FAN_ATPG/bin/opt/fan
```

### 3. Install external tools (no sudo)

```bash
# Yosys and OpenSTA:
export PATH=$HOME/local/bin:$PATH
```

### 4. Synthesize ITC'99 benchmarks (NanGate45 gate-level)

```bash
bash scripts/synth_itc99.sh
# output: FAN_ATPG/mod_netlist/b{03,04,05,07,08,09,11,12,13,14,15}.v
```

### 5. Generate non-scan masks via OpenSTA

```bash
bash scripts/gen_nonscan_masks.sh
# output: masks/<circuit>_x10.mask
```

### 6. Run progressive residual pipeline (primary evaluation)

```bash
# Single case (@10%):
ATPG_PER_TARGET_TIMEOUT=0 ATPG_WALL_TIMEOUT=7200 python3 scripts/run_progressive_residual.py \
  --circuit b03 --ratio 0.10 --nonscan $(cat masks/b03_x10.mask | tr '\n' ' ')

# Tier A sweep (8 circuits @ 10%):
ATPG_PER_TARGET_TIMEOUT=0 ATPG_WALL_TIMEOUT=7200 \
  python3 scripts/run_progressive_residual_sweep.py --fresh

# Regenerate report figures:
python3 scripts/generate_figures.py

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

# Sequential graph: cycle-break + depth heuristic, then scan simulation on selected chain
./src/scanforge circuit.sf --seq-graph --seq-netlist circuit.v

# Same with a stricter depth threshold (≤3 edges between FFs)
./src/scanforge circuit.sf --seq-graph --seq-netlist circuit.v --seq-depth 3

# --partial-seq-graph is an alias (same behavior as --seq-graph)
./src/scanforge circuit.sf --partial-seq-graph --seq-netlist circuit.v --seq-depth 3
```

---

## Quick Sanity Checks

```bash
# Synthesis sanity
grep -cE '\bDFFR?S?_X[12]\b' FAN_ATPG/mod_netlist/b03.v   # should be ~31

# Mask sanity
wc -l masks/b03_x10.mask

# ATPG sanity — progressive pipeline summary
head -3 results/progressive_residual_summary.csv
grep 'b03,0.1' results/progressive_residual_summary.csv
```

---

## Evaluation — B1, Experiment, B2

| Role | Setup | Metric | Data |
|------|-------|--------|------|
| **B1** | Partial-scan @10%, T=1 | `FC_T1` | `progressive_residual_summary.csv` |
| **Experiment** | Partial-scan @10%, T=1→T=2→T=4 | `FC_T1_T2_T4` | same CSV |
| **B2** | Full-scan, T=1 | `FC_scan_coll` | `phase_d_fullscan_dataset.csv` |

### Results @10% (June 2026, 7/8 complete)

| Circuit | B1 | Experiment | B2 | Exp−B1 | B2−Exp |
|---------|---:|-----------:|---:|-------:|-------:|
| b03 | 89.54% | 89.54% | 91.62% | 0.00 | +2.08 pp |
| b04 | 87.60% | 87.60% | 93.46% | 0.00 | +5.86 pp |
| b05 | 92.81% | 92.81% | 95.34% | 0.00 | +2.53 pp |
| b07 | 93.50% | 93.50% | 93.46% | 0.00 | −0.04 pp |
| b08 | 92.75% | 92.75% | 94.03% | 0.00 | +1.28 pp |
| b09 | 87.63% | 87.63% | 93.44% | 0.00 | +5.81 pp |
| b13 | 87.59% | 87.59% | 91.13% | 0.00 | +3.54 pp |
| b11 | — | — | 97.43% | — | — (T=1 TIMEOUT) |

Full table: [`docs/final_report.md`](./docs/final_report.md) §7.2.

---

## Current Status (June 2026)

**Scope:** Tier A @ **10%** only. Two baselines: **B1** partial T=1, **B2** full-scan.

**Sweep:** 7/8 PASS in `progressive_residual_summary.csv`; **b11 T=1 TIMEOUT** @ 7200 s. See [`docs/final_report.md`](./docs/final_report.md) §7.2 for B1/B2 comparison table.

---

## Legacy: ScanForge C++ Engine (ISCAS'89)

The `src/` directory contains a standalone C++ engine originally built for ISCAS'89 benchmark analysis. It supports:

- SCOAP-based partial scan FF selection
- Scan-shift switching activity simulation
- Stress-aware and wear-leveling partial scan modes
- Timing-exclusion sweep analysis

This engine is independent of the current ITC'99 sequential ATPG pipeline.

### Build

```bash
make -C src
# binary: src/scanforge
```

### Key commands

```bash
# Full scan analysis
./src/scanforge FAN_ATPG/results/s27.sf

# Timing-driven exclusion sweep (ISCAS'89)
./src/scanforge FAN_ATPG/results/s27.sf \
  --timing-netlist FAN_ATPG/mod_netlist/s27.v \
  --exclude-sweep \
  --exclude-summary-csv exclude_sweep.csv

# Batch sweep across ISCAS'89 benchmarks
bash scripts/run_timing_exclusion_sweep.sh

# Per-FF stress profile
./src/scanforge FAN_ATPG/results/s27.sf --stress-csv stress.csv \
  --segment-csv segment.csv --segment-window 16

# Partial scan sweep (SCOAP-CO)
./src/scanforge FAN_ATPG/results/s953.sf --sweep
```

### CLI Reference

```
Usage: scanforge [options] <scan_data.sf>

Options:
  --sweep                   Sweep partial scan ratios 25/50/75/100%
  --coverage                Coverage estimate sweep
  --csv                     CSV output (with --coverage or --sweep)
  --summary-csv <path>      Write tradeoff sweep CSV
  --stress-csv <path>       Write per-FF scan stress metrics
  --segment-csv <path>      Write segment stress CSV (needs --segment-window)
  --segment-window <n>      Sliding window for segment metrics
  --partial <ratio>         Partial scan at given ratio (0.0–1.0)
  --timing-ranking <csv>    Timing-criticality CSV
  --timing-netlist <v>      Gate-level netlist for timing-depth proxy
  --exclude-ratio <ratio>   Mark top ratio as non-scan
  --exclude-sweep           Sweep exclusion ratios (legacy ISCAS'89 only)
  --exclude-summary-csv <path>  Write exclusion-sweep summary CSV
  --mode <co|combined|random|co_wear|combined_wear|
                            co_wear_leveling|combined_wear_leveling>
                            FF selection strategy (default: co)
  --lambda <x>              Penalty weight for *_wear and *_wear_leveling (default: 0.5)
  --coverage-proxy <co|combined|controllability>
                            Which SCOAP sums define coverage_proxy in sweep / --partial
  --seq-graph               Load full .sf + Verilog netlist; print sequential-graph report,
                            then simulate the selected partial chain when non-empty
  --seq-graph-only          Alias for --seq-graph
  --partial-seq-graph       Same as --seq-graph (backward-compatible name)
  --seq-netlist <path>      Required with --seq-graph / --partial-seq-graph: gate-level
                            Verilog netlist (.v); FF instance names should match FF_NAMES
  --seq-depth <n>           Maximum allowed sequential path length in edges; paths strictly
                            longer trigger the depth-reduction greedy pass (default: 4)
  --seq-path-cap <n>        Safety cap on long paths enumerated per greedy step
                            (default: 500000)
  -h, --help                Print this help
```

### The `.sf` File Format

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

### Archived Results (ISCAS'89)

Full scan switching activity and partial scan sweep tables for s27 through s38584 are available in git history and in [`docs/archive/flow_and_results.md`](./docs/archive/flow_and_results.md) (Section 9).

### Stress-Aware Partial Scan Study

The initial project topic was "Stress-Aware Partial Scan Selection" targeting ISCAS’89 with a SCOAP coverage proxy. This work is documented in [`docs/archive/progress_report.md`](./docs/archive/progress_report.md). As of 2026, the active topic is progressive T=1→T=2→T=4 pipeline evaluation on timing-driven partial-scan ITC’99 benchmarks.

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

---

## Sequential Graph Analysis

### Overview

The sequential graph features let you analyze and break unwanted **feedback loops** in the FF dependency graph of a circuit, and **reduce the sequential depth** (maximum path length between FFs).

The sequential graph flow is exposed as **`--seq-graph`** (alias **`--seq-graph-only`**) and **`--partial-seq-graph`**, which behave the same: load the **full** `.sf` (patterns included), merge netlist-derived FF edges, print the sequential-graph report, then — **if `all_selected_ffs` is non-empty** — run scan simulation on that partial chain and print the **Scan Chain Analysis Report** plus coverage lines. If the unioned selection is empty (no cycles to break and no paths longer than `--seq-depth`), scan simulation is skipped and the run exits successfully.

| Mode | What it does |
|------|-------------|
| `--seq-graph` | Sequential-graph report; partial-chain scan simulation only when at least one FF is selected |
| `--partial-seq-graph` | Same as `--seq-graph` |

Both require `--seq-netlist <circuit.v>`: a structural gate-level Verilog file whose DFF instance names match the `FF_NAMES` in the `.sf` file.

### Verilog Netlist Parsing

ScanForge parses the netlist to build the **FF-to-FF combinational reachability graph**: an edge `FF_i → FF_j` is added when FF_i's Q net can reach FF_j's D net by following assign/gate fanout without crossing another FF's Q net (i.e., no implicit F0→F2 shortcut when only F0→F1 and F1→F2 exist). Both named-port (`.d(net)`, `.q(net)`) and positional (`clk, d, q`) DFF instantiation styles are supported, and a single D net shared by multiple FFs produces an edge to each of them.

> **Note:** Many standard ISCAS'89 gate-level netlists connect each FF's D pin through combinational gates, so the combinational reachability graph is dense. ScanForge handles this correctly at scale — see the benchmark results below.

### Cycle Breaking (Heuristic FVS)

ScanForge runs **Tarjan's SCC algorithm** to find all non-trivial strongly-connected components (SCCs) in the FF graph. It then applies a **greedy feedback vertex set (FVS) heuristic**: at each step it removes the FF with the highest combined in+out degree within the remaining cyclic SCCs, repeating until no cyclic SCCs remain. Self-loops are excluded.

The selected FFs form the set found by this heuristic that breaks all detected cycles. The SCC-based approach runs in O(V×(V+E)) and handles circuits up to 1 728 FFs and 32 000+ edges without exponential blowup.

### Depth Reduction

After the cycle-breaking FFs are removed from the graph, ScanForge enumerates simple paths whose **edge count exceeds `--seq-depth`** (default: 4). A **greedy vertex-removal pass** picks FFs that appear most frequently near the **center** of long paths (center-weighted scoring), ensuring that removing one FF breaks the maximum number of oversized paths.

The two passes are independent and their results are **unioned** into `all_selected_ffs` — the final partial-scan chain used for simulation under `--seq-graph` / `--partial-seq-graph`.

### Command Usage

```bash
# Sequential graph report + scan simulation on the selected partial chain
./src/scanforge circuit.sf \
    --seq-graph \
    --seq-netlist circuit.v

# Stricter depth threshold (≤3 edges between FFs)
./src/scanforge circuit.sf \
    --seq-graph \
    --seq-netlist circuit.v \
    --seq-depth 3

# Same as above (--partial-seq-graph is a synonym)
./src/scanforge circuit.sf \
    --partial-seq-graph \
    --seq-netlist circuit.v \
    --seq-depth 3

# Stress and segment CSV exports (same as other full/partial runs)
./src/scanforge circuit.sf \
    --seq-graph \
    --seq-netlist circuit.v \
    --seq-depth 3 \
    --stress-csv stress.csv \
    --segment-csv seg.csv \
    --segment-window 8
```

### Demo: `s27` benchmark (3 FFs)

The smallest ISCAS'89 circuit, `s27`, gives a concrete example:

```
$ ./src/scanforge results/s27.sf \
    --seq-graph --seq-netlist FAN_ATPG/netlist/s27.v

Sequential FF graph: 4 directed edge(s) (combinational reachability from each FF's Q to others' D; 4 from this netlist).

====================================================
  ScanForge — Sequential FF Graph (--seq-graph)
  Circuit FFs: 3   Seq edges: 4
  Depth threshold: 4   Path enum cap: 500000
  Edges: combinational Q→D reachability (no FF shortcuts across intermediate FFs)
====================================================
Metric                  Count   Detail
--------------------------------------------------------------------------
Cyclic SCCs             1       non-trivial strongly-connected components
Cycle-break FFs         1       heuristic FVS (SCC greedy)
Depth-reduction FFs     0       greedy on paths longer than depth threshold
Combined selected       1       union of cycle-break and depth-reduction
Long paths (<= cap)     0       enumerated for last depth pass
====================================================
  Cycle-breaking FFs (1)
    Indices: 1
    Names: U_G6
  Combined selected FFs (1)
    Indices: 1
    Names: U_G6
====================================================
Seq-graph chain: selected FFs 1 / 3
Switching Activity: 0.6000
Max Stress: 0.6500
Stress Variance: 0.0000
Stress Imbalance: 1.0000
====================================================
  ScanForge — Scan Chain Analysis Report
====================================================
  Total FFs in circuit : 3
  FFs in chain (K)     : 1
  Scan ratio           : 33.3%
  Test patterns        : 5
  ...
====================================================
  Estimated coverage: 0/5 patterns applicable (68.4%)
  Coverage proxy (combined): 0.6364  (loss 0.3636)
```

The circuit has one cyclic SCC (U_G5↔U_G6 form a feedback pair through combinational logic); breaking U_G6 removes the cycle. The **Scan Chain Analysis Report** reflects simulation on that single selected FF only (K=1).

### Effect of `--seq-depth` on Sequential Depth

With `--seq-depth 3`, additional depth-reduction FFs are selected to ensure no sequential path exceeds 3 edges. Example on s953 (29 FFs):

```
$ ./src/scanforge FAN_ATPG/results/s953.sf \
    --seq-graph --seq-netlist FAN_ATPG/netlist/s953.v

  Cyclic SCCs: 1   Cycle-breaking FFs: 5   Depth-reduction FFs: 0
```

All state-machine FFs belong to one SCC; after breaking 5 FFs the remaining graph is acyclic with paths ≤ 4 edges, so no additional depth-reduction FFs are needed at the default `--seq-depth 4`.

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

### Sequential Graph Analysis — All ISCAS'89 Benchmarks

Results of `--seq-graph` on all 12 ISCAS'89 benchmarks using `FAN_ATPG/netlist/*.v` (gate-level, combinational reachability edges).  
**Algorithm:** Tarjan's SCC (Cyclic SCCs) + greedy FVS via in/out-degree heuristic (cycle-break FFs) + center-weighted greedy on long paths (depth-reduction FFs, `--seq-depth 4`).

| Circuit | FFs | Comb. Edges | Cyclic SCCs | Cycle-break FFs | Depth-red. FFs | Total selected |
|---------|----:|------------:|:-----------:|:---------------:|:--------------:|:--------------:|
| s27     |   3 |           4 |      1      |        1        |        0       |        1       |
| s208    |   8 |          28 |      0      |        0        |        3       |        3       |
| s510    |   6 |          30 |      1      |        5        |        0       |        5       |
| s953    |  29 |         150 |      1      |        5        |        0       |        5       |
| s1196   |  18 |          20 |      0      |        0        |        0       |        0       |
| s1238   |  18 |          20 |      0      |        0        |        0       |        0       |
| s5378   | 179 |       1,200 |      1      |       32        |        7       |       39       |
| s9234   | 211 |       2,546 |     10      |       63        |       23       |       86       |
| s15850  | 534 |      11,497 |      7      |      105        |       99       |      204       |
| s35932  | 1728|       4,475 |     18      |      306        |      171       |      477       |
| s38417  | 1636|      32,774 |     31      |      390        |      205       |      595       |
| s38584  | 1426|      15,300 |      1      |      376        |      269       |      645       |

**Combinational edges** = FF-to-FF combinational reachability edges (from `--seq-netlist`); higher counts reflect denser FSM-to-datapath connectivity.  
**Cyclic SCCs** = non-trivial strongly-connected components in the FF dependency graph; circuits with 0 SCCs are acyclic.  
**Cycle-break FFs** = minimum heuristic FVS to dissolve all cycles; after removal the graph is a DAG.  
**Depth-red. FFs** = additional FFs chosen to ensure no sequential path exceeds `--seq-depth 4` edges; 0 means the post-FVS DAG already satisfies the depth constraint.

Run command for any circuit:
```bash
./src/scanforge FAN_ATPG/results/<circuit>.sf \
    --seq-graph \
    --seq-netlist FAN_ATPG/netlist/<circuit>.v
```

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
               ┌─────────────┤  (optional) gate-level .v netlist
               │             │
┌──────────────▼─────────────▼────────────────────────────────────┐
│  ScanForge Engine (src/)                                        │
│                                                                 │
│  ── SCOAP-based partial scan ──────────────────────────────     │
│   parseScanData()         — reads .sf, builds ScanData struct   │
│   selectFFs()             — ranks FFs by SCOAP, returns chain[K]│
│   simulate()              — scan-shift simulation on chain      │
│   sweepPartialScan()      — iterates over ratios, prints table  │
│                                                                 │
│  ── Sequential graph analysis ─────────────────────────────     │
│   mergeSequentialEdgesFromVerilog()                             │
│                           — parses .v; adds Q→D FF edges        │
│   selectSequentialGraphFFs()                                    │
│                           — heuristic FVS (cycle break)         │
│                           — greedy depth-reduction pass         │
│   simulate() on all_selected_ffs                                │
│                           — scan simulation of seq-graph chain  │
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
