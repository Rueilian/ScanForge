# AGENTS.md — ScanForge

**Read this before any code, doc, or experiment change.**

## Project scope (mandatory)

| Item | Value |
|------|--------|
| **Research framing** | **B1** (partial T=1) → **Experiment** (T1→T2→T4) → **B2** (full-scan) |
| **Experiment metric** | `FC_T1_T2_T4`; gain = Exp−B1; gap to B2 = B2−Exp |
| **Partial-scan ratio** | **10% only** (`ratio=0.10`, masks `masks/<circuit>_x10.mask`) |
| **Tier A circuits** | b03, b04, b05, b07, b08, b09, b11, b13 |
| Results | `results/progressive_residual_summary.csv` (B1 + pipeline, @10%) |
| Full-scan baseline | `results/phase_d_fullscan_dataset.csv` (B2, `fc_scan_coll`) |
| **Authoritative docs** | `docs/spec.md`, `docs/final_report.md`, `README.md`, `docs/README.md` |

## Forbidden (do not repeat)

1. **Do not run or document multi-ratio sweeps.** Only 10% is in scope.
2. **Do not read or cite `*/archive/` directories** for current numbers, masks, scripts, or plans. They are historical only.
3. **Do not restore** multi-ratio `RATIOS` lists or “32-run sweep” language in active files.
4. **Do not use** `scripts/archive/run_atpg_sweep.py` or legacy T=8 flows for the report.

## Archive policy (hard)

Paths in `.cursorignore` are **out of scope** for Read, Grep, Glob, and subagent search.

**Unless the user explicitly asks for archived content:**

- Do **not** `grep` / `rg` / search under `**/archive/**`
- Do **not** open files in `docs/archive/`, `results/archive/`, `scripts/archive/`, `masks/archive/`
- Do **not** cite archived CSVs, masks, or plans in active docs

**Always exclude `archive/` when running grep/rg/find:**

```bash
grep -r --exclude-dir=archive "pattern" .
rg --glob '!**/archive/**' "pattern"
find . -not -path '*/archive/*' -name "*.py"
```

Cursor rule: `.cursor/rules/no-archive-scan.mdc` (`alwaysApply: true`).

If old data seems useful, **ask the user** — do not recover it silently from archive.

## Commands (current)

```bash
# Masks (10% only)
bash scripts/gen_nonscan_masks.sh

# ITC'99 sweep (8 circuits @10%, no per-target timeout):
ATPG_WALL_TIMEOUT=3600 python3 scripts/run_progressive_residual_sweep.py --fresh

# ISCAS'89 sweep (9 circuits @10%, no per-target timeout):
ATPG_WALL_TIMEOUT=3600 python3 scripts/run_progressive_residual_iscas89_sweep.py --fresh

# Figures + report tables
python3 scripts/generate_figures.py
```

Single case:

```bash
ATPG_WALL_TIMEOUT=3600 python3 scripts/run_progressive_residual.py \
  --circuit b03 --ratio 0.10 \
  --nonscan "$(tr '\n' ' ' < masks/b03_x10.mask)" --per-target-timeout 0
```

## Build

```bash
cd FAN_ATPG && make -j$(nproc) bin/opt/fan
export PATH=$HOME/local/bin:$PATH   # yosys, sta
```

## Gotchas

- FAN must run with `cwd=FAN_ATPG/` (runners handle this).
- Regenerate masks after netlist changes (`scripts/build_itc99_netlists.sh`).
- **b11 @10%** excluded — runner exits silently with no output.
- Full-scan B2: `results/phase_d_fullscan_dataset.csv` (ITC'99), `results/iscas89_fullscan_baseline.csv` (ISCAS'89).
