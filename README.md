# ScanForge

Sequential ATPG research pipeline for evaluating **progressive T=1→T=2→T=4 fault-coverage gain** on timing-driven partial-scan ITC'99 benchmarks.

**Research focus:** How much does the multi-frame residual pipeline add **beyond T=1**? Non-scan ratios (5/10/15/20%) are experimental setup, not the primary comparison axis.

**Authoritative direction:** [`docs/spec.md`](./docs/spec.md) | [`docs/final_report.md`](./docs/final_report.md) | [`docs/README.md`](./docs/README.md)

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
├── masks/                 # non-scan masks: masks/<circuit>_x<ratio>.mask
├── results/
│   ├── progressive_residual_summary.csv — 32-run pipeline results (primary)
│   ├── phase_d_fullscan_dataset.csv     — full-scan FC_scan baselines
│   └── archive/                         — superseded CSVs and legacy sweeps
├── docs/
│   ├── README.md            — doc index (active vs archive)
│   ├── spec.md
│   └── final_report.md
├── src/                   # ScanForge C++ engine (legacy ISCAS'89 tool)
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
# output: masks/<circuit>_x{5,10,15,20}.mask
```

### 6. Run progressive residual pipeline (primary evaluation)

```bash
# Single case:
ATPG_PER_TARGET_TIMEOUT=0 python3 scripts/run_progressive_residual.py \
  --circuit b03 --ratio 0.20 --nonscan $(cat masks/b03_x20.mask | tr '\n' ' ')

# Tier A sweep (8 circuits × 4 ratios = 32 runs):
ATPG_PER_TARGET_TIMEOUT=0 python3 scripts/run_progressive_residual_sweep.py

# Regenerate report figures:
python3 scripts/generate_figures.py
```

---

## Quick Sanity Checks

```bash
# Synthesis sanity
grep -cE '\bDFFR?S?_X[12]\b' FAN_ATPG/mod_netlist/b03.v   # should be ~31

# Mask sanity
wc -l masks/b03_x5.mask    # should be ceil(31 × 0.05) = 2

# ATPG sanity — progressive pipeline summary
head -3 results/progressive_residual_summary.csv
grep 'b03,0.2' results/progressive_residual_summary.csv
```

---

## Evaluation Cases

| Case | Description | Metric |
|------|-------------|--------|
| **T=1 partial-scan** | Non-scan FFs, single frame | FC_T1 (pipeline baseline) |
| **+ residual T=2** | ATPG on R1 = F − D1 | FC_T1_T2, gain_T2_pp |
| **+ residual T=4** | ATPG on R2 = F − D1 − D2 | FC_T1_T2_T4, **total_gain_pp** |
| `full_scan` | x=0%, separate dataset | FC_scan (context only) |

Primary question: **total_gain_pp = FC_T1_T2_T4 − FC_T1**, not FC vs exclusion ratio.

---

## Current Status (June 2026)

**Completed:**
- Progressive residual T=1→T=2→T=4 pipeline + union FC accounting
- OpenSTA mask regeneration on aligned gate-level netlists
- Tier A sweep: **32/32 PASS** → `results/progressive_residual_summary.csv`
- Report updated: `docs/final_report.md`

**Key result @20% exclusion:** only **b03** shows pipeline gain (**+2.16pp**, all from T=2); all other Tier A circuits **0.00pp** gain.

**Open issues:**
- Full-scan FC_scan (91–97%) still has AU/UD headroom — separate from pipeline evaluation
- b11 pipeline runtime ~277s @20% with zero gain

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
  --exclude-sweep           Sweep 5/10/15/20% exclusion ratios
  --exclude-summary-csv <path>  Write exclusion-sweep summary CSV
  --mode <co|combined|random|co_wear|...>  FF selection strategy
  --lambda <x>              Penalty weight for wear modes
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

The initial project topic was "Stress-Aware Partial Scan Selection" targeting ISCAS'89 with a SCOAP coverage proxy. This work is documented in [`docs/archive/progress_report.md`](./docs/archive/progress_report.md). As of 2026, the active topic is progressive T=1→T=2→T=4 pipeline evaluation on timing-driven partial-scan ITC'99 benchmarks.

---

## License

MIT License — see [LICENSE](LICENSE).
