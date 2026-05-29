# AGENTS.md

## Overview

ScanForge is a sequential ATPG research pipeline for studying fault coverage loss and recovery under timing-driven partial-scan constraints. It uses FAN_ATPG (with project-specific extensions) as the ATPG backend, targeting ITC'99 circuits synthesized with NanGate45.

The authoritative project direction lives in [`spec.md`](./spec.md). The task tracker and implementation audit lives in [`checklist.md`](./checklist.md).

---

## Build

### FAN_ATPG (required)

```bash
sudo apt install bison flex
cd FAN_ATPG && make -j$(nproc) && cd ..
# binary: FAN_ATPG/bin/opt/fan
```

The submodule contains project-specific modifications (PARTIAL_SEQUENTIAL mode, `set_nonscan_ff` command). Always build from this repo's submodule, not upstream.

### ScanForge engine (optional)

```bash
make -C src
# binary: src/scanforge
```

Used for the older timing-exclusion sweep flow (ISCAS'89 benchmark assets).

### External tools (no sudo — install to ~/local)

```bash
export PATH=$HOME/local/bin:$PATH
# Yosys: ~/local/bin/yosys
# OpenSTA: ~/local/bin/sta
```

---

## Run

### Synthesis (Yosys → NanGate45 gate-level Verilog)

```bash
export PATH=$HOME/local/bin:$PATH
bash scripts/synth_itc99.sh
# output: FAN_ATPG/mod_netlist/b{03,04,05,07,08,09,11,12,13,14,15}.v
```

### Non-scan mask generation (OpenSTA → per-FF slack → masks)

```bash
bash scripts/gen_nonscan_masks.sh
# output: masks/<circuit>_x{5,10,15,20}.mask
```

### ATPG experiment sweep

```bash
# FAN_ATPG binary must be built first
cd FAN_ATPG && make -j$(nproc) && cd ..

# Pilot (b03, 5 ratios):
python3 scripts/run_atpg_sweep.py --circuits b03

# Full (11 circuits × 5 ratios = 55 runs):
python3 scripts/run_atpg_sweep.py

# Resume after interruption:
python3 scripts/run_atpg_sweep.py --skip-done
```

FAN_ATPG must be invoked from the `FAN_ATPG/` working directory. The runner handles this automatically.

### Timing-exclusion sweep (ISCAS'89, legacy)

```bash
./src/scanforge FAN_ATPG/results/s27.sf \
  --timing-netlist FAN_ATPG/mod_netlist/s27.v \
  --exclude-sweep \
  --exclude-summary-csv results/timing_exclusion/s27_exclude_sweep.csv

bash scripts/run_timing_exclusion_sweep.sh
```

### Single FAN_ATPG run (manual)

```bash
cd FAN_ATPG
./bin/opt/fan -f script/fanScripts/<circuit>_x<ratio>.script
cd ..
```

---

## Test

No automated test suite. Validation is done by checking:

```bash
# Synthesis sanity
grep -cE '\bDFFR?S?_X[12]\b' FAN_ATPG/mod_netlist/b03.v   # should be ~31

# Mask sanity
wc -l masks/b03_x5.mask    # should be ceil(31 × 0.05) = 2

# ATPG sanity — full-scan b03 should give fault_coverage ≥ 90%
grep b03 results/itc99_partial_scan.csv | head -1
```

---

## Lint

Compilation with `-Wall -Wextra` (already in the Makefile) serves as the linter. There is no separate lint command.

---

## Gotchas

- FAN_ATPG must be run from the `FAN_ATPG/` directory (relative paths in scripts)
- `_const0_` appears in synthesized netlists as a module input port (constant-literal fixup); FAN treats it as a free PI — if fault coverage is unexpectedly low, check that `_const0_` is constrained to 0
- Synthesized FF cells are `DFFR_X1`, `DFFS_X1`, `DFFRS_X1` (NOT `SDFF_X1` — hilomap is not used)
- `make -C FAN_ATPG` emits warnings and may exit with code 2, but the binary is still produced — check for `FAN_ATPG/bin/opt/fan`
- All task owners are swear01; do not assume Rueilian owns any task
- The `results/` directory in the repo root contains pre-generated `.sf` files from ISCAS'89 benchmarks. `FAN_ATPG/results/` is where newly generated files go when running the ATPG pipeline.
