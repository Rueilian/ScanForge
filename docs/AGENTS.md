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

### ITC'99 netlist build（推薦：base-gate pipeline）

One-shot entry point (prep → synth → fixup → validate). See [`docs/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md`](./superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md).

```bash
export PATH=$HOME/local/bin:$PATH
bash scripts/build_itc99_netlists.sh
# input:  itc99_rtl/ → itc99_synth_rtl/ (prep)
# output: FAN_ATPG/mod_netlist/{c}_dffr.v  (Yosys raw)
#         FAN_ATPG/mod_netlist/{c}.v        (SDFFR full-scan)
#         FAN_ATPG/mod_netlist/{c}_reset_tie.v (if reset PI)
```

**Base-gate policy:** synthesis uses `NangateOpenCellLibrary_base.lib` — allows INV/AND/OR/NAND/NOR/XOR + **MUX2**; **forbids OAI*/AOI*** (ABC expands to primitives). FAN keeps **`Gate::MUX`** (Phase D1); OAI/AOI atomic gates (D3.2/D3.3) will be removed once pipeline is live.

### Synthesis only (legacy / debug)

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

### Benchmark scope (ITC tiers)

Defined in [`scripts/itc99_benchmark_scope.sh`](./scripts/itc99_benchmark_scope.sh):

| Tier | Circuits | ATPG sweeps |
|------|----------|-------------|
| **A (active)** | b03 b04 b05 b07 b08 b09 b11 b13 | ✅ default |
| **B (deferred)** | b12 b14 b15 | netlist only; engine too slow / crash |
| **C (out)** | b17+ mega-ISCAS | not in pipeline |

Speed improvement plan: [`docs/superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md`](./superpowers/plans/2026-06-10-saf-atpg-speed-improvement.md)

### ATPG timeouts (unified defaults)

Defined in [`scripts/atpg_timeouts.sh`](./scripts/atpg_timeouts.sh) / [`scripts/atpg_timeouts.py`](./scripts/atpg_timeouts.py):

| Variable | Default | Meaning |
|----------|---------|---------|
| `ATPG_WALL_TIMEOUT` | **3600** s | Max wall-clock per FAN invocation |
| `ATPG_PER_TARGET_TIMEOUT` | **0** s (off) | Per-fault wall clock; use **30** for Tier B only |
| `ATPG_THREADS` | **0** (all cores) | Parallel workers; `0` = `nproc` / `hardware_concurrency` |

Parallel ATPG example:

```bash
ATPG_THREADS=4 bash scripts/run_phase_d_fullscan_dataset.sh
```

FAN script equivalent: `set_atpg_threads 4` before `run_atpg`.

Override example:

```bash
ATPG_WALL_TIMEOUT=7200 ATPG_PER_TARGET_TIMEOUT=180 bash scripts/run_phase_d_fullscan_dataset.sh
```

### ATPG experiment sweep

```bash
# FAN_ATPG binary must be built first
cd FAN_ATPG && make -j$(nproc) && cd ..

# Pilot (b03, 5 ratios):
python3 scripts/run_atpg_sweep.py --circuits b03

# Full (8 active ITC × 5 ratios = 40 runs):
python3 scripts/run_atpg_sweep.py

# Include deferred large ITC (b12/b14/b15) — not recommended yet:
ITC_INCLUDE_DEFERRED=1 python3 scripts/run_atpg_sweep.py

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

```bash
# Netlist pipeline (after build_itc99_netlists.sh)
python3 scripts/validate_netlist.py --all
bash scripts/verify_fullscan_netlist.sh

# ATPG regression
bash scripts/test_phase_c_atpg.sh
bash scripts/test_phase_d_atpg.sh
cd FAN_ATPG && ./pkg/core/bin/opt/phase_d_test .

# Full-scan dataset sweep (FC_scan primary; uses ATPG_WALL_TIMEOUT=3600)
bash scripts/run_phase_d_fullscan_dataset.sh
```

Manual sanity checks:

```bash
grep -cE '\bSDFFR_X1\b' FAN_ATPG/mod_netlist/b03.v          # full-scan FF
grep -cE '\bMUX2_X1\b' FAN_ATPG/mod_netlist/b03.v           # base gate OK
grep -cE '\bOAI\d+_X1\b|\bAOI\d+_X1\b' FAN_ATPG/mod_netlist/b03.v  # must be 0
grep "fault coverage (scan protocol)" FAN_ATPG/rpt/b03_fs.rpt  # ≥ 93%
```

---

## Lint

Compilation with `-Wall -Wextra` (already in the Makefile) serves as the linter. There is no separate lint command.

---

## Gotchas

- FAN_ATPG must be run from the `FAN_ATPG/` directory (relative paths in scripts)
- **Do not hand-edit** `FAN_ATPG/mod_netlist/*.v` — use `build_itc99_netlists.sh` + `itc99_prep_rules.yaml`
- **`_dffr.v` is source of truth** for fixup; never `strip(bad netlist) → fixup`
- **MUX2 is a base gate** — allowed in netlist; FAN `Gate::MUX` must stay. **OAI/AOI compound cells** must not appear (synthesis expands them)
- `_const0_` is fixed by `fixup_verilog.py` tie cells — should not appear as module `input`
- **Full-scan FC metric:** use **FC_scan** (auto on `add_fault --all`). See `docs/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md`
- ITC'99 designs with `reset` PI: `mod_netlist/{c}_reset_tie.v` or auto scan protocol on `{c}.v`
- Yosys raw output uses `DFFR_X1`; fixup converts to `SDFFR_X1` + scan chain
- `make -C FAN_ATPG` emits warnings and may exit with code 2, but the binary is still produced — check for `FAN_ATPG/bin/opt/fan`
- All task owners are swear01; do not assume Rueilian owns any task
- The `results/` directory in the repo root contains pre-generated `.sf` files from ISCAS'89 benchmarks. `FAN_ATPG/results/` is where newly generated files go when running the ATPG pipeline.
