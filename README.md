# ScanForge

Sequential ATPG research pipeline for studying fault coverage loss and recovery under timing-driven partial-scan constraints.

**Current active work:** ITC'99 benchmarks synthesized with NanGate45, timing-driven scan exclusion via OpenSTA, and multi-frame sequential ATPG (PARTIAL_SEQUENTIAL mode in FAN_ATPG).

Authoritative direction: [`docs/spec.md`](./docs/spec.md) | Task tracker: [`docs/checklist.md`](./docs/checklist.md) | Pipeline details: [`docs/flow_and_results.md`](./docs/flow_and_results.md)

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
│   ├── gen_nonscan_masks.sh   — orchestrates STA + mask generation
│   └── run_atpg_sweep.py      — runs all 55 experiments, writes results CSV
├── masks/                 # non-scan masks: masks/<circuit>_x<ratio>.mask
├── results/               # experiment output
│   └── itc99_partial_scan.csv — 55-row results table
├── docs/                  # Project specification, checklist, agent instructions, flow docs
│   ├── spec.md
│   ├── checklist.md
│   ├── AGENTS.md
│   ├── progress_report.md
│   └── flow_and_results.md
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

### 6. Run ATPG experiment sweep

```bash
# Pilot (b03, 5 ratios):
python3 scripts/run_atpg_sweep.py --circuits b03

# Full (11 circuits × 5 ratios = 55 runs):
python3 scripts/run_atpg_sweep.py

# Resume after interruption:
python3 scripts/run_atpg_sweep.py --skip-done
```

FAN_ATPG must be invoked from the `FAN_ATPG/` working directory. The runner handles this automatically.

---

## Quick Sanity Checks

```bash
# Synthesis sanity
grep -cE '\bDFFR?S?_X[12]\b' FAN_ATPG/mod_netlist/b03.v   # should be ~31

# Mask sanity
wc -l masks/b03_x5.mask    # should be ceil(31 × 0.05) = 2

# ATPG sanity — full-scan b03 should give fault_coverage ≥ 90%
grep b03 results/itc99_partial_scan.csv | head -1
```

---

## Evaluation Cases

| Case | Description | Status |
|------|-------------|--------|
| `full_scan` | All FFs scan, x=0%, T=1 ATPG | Completed (Baseline >91% verified across all circuits) |
| `partial_scan_no_recovery` | Non-scan FFs, T=1, X initial state | Completed & Verified |
| `partial_scan_with_recovery` | Non-scan FFs, T=2/T=4/T=8 sequential ATPG | Completed (Progressive residual recovery pipeline implemented) |

---

## Current Status

**Completed:**
- FAN_ATPG `PARTIAL_SEQUENTIAL` multi-frame unrolling mode
- `set_nonscan_ff` command and script integration
- ITC'99 synthesis + OpenSTA timing pipeline
- Non-scan mask generation at 5/10/15/20%
- Fixed `atpg.cpp` core bugs (dominator event-stack OOB, MUX2 PODEM backtrace, and multi-frame SAF consistency bugs)
- Full-scan baseline verified at >91% coverage for all Tier A & B benchmarks (see [results/phase_d_fullscan_dataset.csv](./results/phase_d_fullscan_dataset.csv))
- Progressive residual multi-frame ATPG pipeline (`run_progressive_residual.py`) implemented and verified

**Next Steps:**
- Run the full progressive residual sweep on all Tier A benchmarks across ratios 5%, 10%, 15%, 20%
- Update the final report draft ([docs/final_report.md](./docs/final_report.md)) with the sweep results and generate plots

See [`docs/spec.md`](./docs/spec.md) and [`docs/checklist.md`](./docs/checklist.md) for details.

---

## Parameter Sweep

| Parameter | Values |
|---|---|
| Circuits | b03, b04, b05, b07, b08, b09, b11, b12, b13, b14, b15 |
| Non-scan ratio `x` | 0% (full-scan), 5%, 10%, 15%, 20% |
| Sequential ATPG depth | T=1 for x=0%; T=8 for x>0% |

Total: **55 runs**

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

Full scan switching activity and partial scan sweep tables for s27 through s38584 are available in git history and in `docs/flow_and_results.md` (Section 9).

### Stress-Aware Partial Scan Study

The initial project topic was "Stress-Aware Partial Scan Selection" targeting ISCAS'89 with a SCOAP coverage proxy. This produced a full experimental study (7 modes, 12 circuits) documented in `docs/progress_report.md`. As of May 2026, the project has been redirected to the current topic: "Sequential ATPG Coverage Recovery for Timing-Driven Partial-Scan Circuits."

---

## License

MIT License — see [LICENSE](LICENSE).
