# ScanForge Final Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ITC'99 ATPG pipeline, run the full 55-experiment sweep, and produce the final report tables/figures before the 6/16 presentation deadline.

**Architecture:** The main blocker is low fault coverage on ITC'99 full-scan baselines (34-52% vs expected >90%). Root cause is likely `_const0_` being treated as a free PI by FAN_ATPG. After fixing the netlist pipeline, the full 55-run sweep can execute, enabling the three-way comparison (full_scan / no_recovery / partial_T8) required by the spec.

**Tech Stack:** FAN_ATPG (C++), Python 3 (experiment runner, figure scripts), Yosys + NanGate45 (synthesis), matplotlib (figures)

**Deadline:** 2026-06-16 presentation, 2026-06-17 final report

---

## Current Blocker Summary

| Circuit | Full-scan FC | Issue |
|---------|-------------|-------|
| b03 | 34.37% | `_const0_` wire not declared; LOGIC0_X1 present but may not be recognized |
| b04 | 42.25% | `_const0_` same as b03 |
| b05 | BLOCKED | `assign` syntax error in netlist |
| b07 | 42.54% | `_const0_` still a module input port + no LOGIC0 tie cell |
| b08 | 41.09% | no `_const0_` but low coverage — separate root cause |
| b09 | 34.13% | no `_const0_` but low coverage — separate root cause |
| b11 | TIMEOUT | 120s timeout (runner now has 600s) |
| b12 | TIMEOUT | 120s timeout |
| b13 | 52.29% | no `_const0_` but low coverage |
| b14 | TIMEOUT | 120s timeout |
| b15 | UNTESTED | 839 FFs, very large |

**Key observation:** Even circuits WITHOUT `_const0_` (b08, b09, b13) have low full-scan coverage. This means `_const0_` is not the only root cause. The investigation must also check FAN_ATPG's handling of NanGate45 cells, clock modeling, and fault collapsing.

---

### Task 1: Diagnose low full-scan coverage root cause on b03

**Files:**
- Inspect: `FAN_ATPG/mod_netlist/b03.v`
- Inspect: `FAN_ATPG/rpt/b03_x0.rpt` (full-scan report)
- Inspect: `FAN_ATPG/techlib/mod_nangate45.mdt`
- Create: `FAN_ATPG/script/fanScripts/b03_debug_fullscan.script`

- [ ] **Step 1: Run b03 full-scan with verbose fault report**

Create a debug script that runs full-scan ATPG on b03 and dumps the undetected fault list:

```
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b03.v
build_circuit --frame 1
set_fault_type saf
add_fault --all
set_static_compression on
set_dynamic_compression on
run_atpg
report_statistics > rpt/b03_debug_fullscan.rpt
report_fault -s AU > rpt/b03_debug_au_faults.txt
report_fault -s UD > rpt/b03_debug_ud_faults.txt
exit
```

- [ ] **Step 2: Run the debug script and capture output**

```bash
cd /home/swear01/ScanForge/FAN_ATPG && ./bin/opt/fan -f script/fanScripts/b03_debug_fullscan.script
```

- [ ] **Step 3: Analyze AU fault patterns**

```bash
head -50 /home/swear01/ScanForge/FAN_ATPG/rpt/b03_debug_au_faults.txt
```

Check:
- Are AU faults concentrated in specific logic cones?
- Are AU faults near `_const0_` connections?
- Are AU faults on FF inputs/outputs (suggesting scan chain modeling issue)?
- Are AU faults on gates driven by LOGIC0_X1/LOGIC1_X1?

- [ ] **Step 4: Check FAN circuit parsing for b03**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
echo "read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b03.v
build_circuit --frame 1
report_circuit
exit" | ./bin/opt/fan
```

Look for:
- Total gate count vs expected
- PI/PPO/PO counts
- Whether LOGIC0_X1 is parsed as TIEL (tie-low) or as a generic gate
- Whether `_const0_` appears as a PI

- [ ] **Step 5: Compare with s27 full-scan report**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
echo "read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/s27.v
build_circuit --frame 1
set_fault_type saf
add_fault --all
set_static_compression on
set_dynamic_compression on
run_atpg
report_statistics
report_circuit
exit" | ./bin/opt/fan
```

Compare gate counts, PI/PO/PPI counts, and fault statistics to identify structural differences.

- [ ] **Step 6: Document root cause hypothesis**

Write findings in `docs/checklist.md` under the ITC'99 pipeline section. Record:
- What FAN sees (gate counts, PI counts, cell type mapping)
- Where AU faults concentrate
- Whether the issue is `_const0_`, cell mapping, clock handling, or something else

---

### Task 2: Fix `_const0_` handling in fixup_verilog.py

**Files:**
- Modify: `scripts/fixup_verilog.py`
- Test: re-synthesize b03, b07 and verify `_const0_` is not a PI

- [ ] **Step 1: Add wire declaration for `_constN_` signals**

In `fixup_verilog.py`, after Pass 7 (tie cell instantiation), add a new pass that:
1. Finds all `_constN_` signals used in the netlist
2. Removes them from the module port list if present
3. Removes `input _constN_;` declarations
4. Adds `wire _constN_;` declarations before the tie cell instances

- [ ] **Step 2: Fix Pass 4 to strip `_constN_` from module header**

In the `expand_module` function (Pass 4), filter out any port whose name matches `_const\d+_`.

- [ ] **Step 3: Re-run fixup on b03 and b07**

```bash
cd /home/swear01/ScanForge
python3 scripts/fixup_verilog.py FAN_ATPG/mod_netlist/b03.v FAN_ATPG/mod_netlist/b03.v
python3 scripts/fixup_verilog.py FAN_ATPG/mod_netlist/b07.v FAN_ATPG/mod_netlist/b07.v
```

- [ ] **Step 4: Verify `_const0_` is no longer a PI**

```bash
grep "input.*_const" FAN_ATPG/mod_netlist/b03.v  # should be empty
grep "input.*_const" FAN_ATPG/mod_netlist/b07.v  # should be empty
grep "wire.*_const" FAN_ATPG/mod_netlist/b03.v   # should show wire declaration
grep "LOGIC0_X1" FAN_ATPG/mod_netlist/b03.v      # should show tie cell
```

- [ ] **Step 5: Re-run b03 full-scan and check coverage**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
./bin/opt/fan -f script/fanScripts/b03_debug_fullscan.script
```

Expected: fault coverage should increase significantly if `_const0_` was the root cause.

---

### Task 3: Fix b05 netlist assign syntax

**Files:**
- Inspect: `FAN_ATPG/mod_netlist/b05.v`
- Modify: `scripts/fixup_verilog.py` (add assign-statement handler if needed)
- Or: `scripts/synth_itc99.sh` (add Yosys pass to eliminate assigns)

- [ ] **Step 1: Identify the exact assign syntax error**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
echo "read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b05.v
build_circuit --frame 1
exit" | ./bin/opt/fan 2>&1 | head -30
```

Record the exact error message and line number.

- [ ] **Step 2: Check if Yosys can avoid generating assigns**

```bash
grep -n "assign" /home/swear01/ScanForge/FAN_ATPG/mod_netlist/b05.v | head -10
```

If assigns exist, add `opt -full` or `techmap` to the Yosys script in `synth_itc99.sh` to eliminate them.

- [ ] **Step 3: Re-synthesize b05 if needed**

```bash
cd /home/swear01/ScanForge
export PATH=$HOME/local/bin:$PATH
yosys -q -p "
  read_verilog itc99_rtl/b05.v;
  synth -top b05 -flatten;
  dfflibmap -liberty FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib;
  abc -liberty FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib;
  splitnets;
  opt_clean -purge;
  write_verilog -noattr FAN_ATPG/mod_netlist/b05.v;
"
python3 scripts/fixup_verilog.py FAN_ATPG/mod_netlist/b05.v FAN_ATPG/mod_netlist/b05.v.tmp && mv FAN_ATPG/mod_netlist/b05.v.tmp FAN_ATPG/mod_netlist/b05.v
```

- [ ] **Step 4: Verify b05 loads in FAN**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
echo "read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b05.v
build_circuit --frame 1
report_circuit
exit" | ./bin/opt/fan
```

---

### Task 4: Re-synthesize all affected circuits and verify

**Files:**
- Run: `scripts/synth_itc99.sh` (full re-synthesis with fixed fixup)
- Verify: all 11 netlists load in FAN

- [ ] **Step 1: Re-run full synthesis pipeline**

```bash
cd /home/swear01/ScanForge
export PATH=$HOME/local/bin:$PATH
bash scripts/synth_itc99.sh
```

- [ ] **Step 2: Verify all 11 netlists load in FAN**

```bash
cd /home/swear01/ScanForge/FAN_ATPG
for c in b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15; do
  echo "=== $c ==="
  echo "read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/$c.v
build_circuit --frame 1
report_circuit
exit" | timeout 30 ./bin/opt/fan 2>&1 | grep -E "gate|PI|PO|PPI|error|Error"
done
```

- [ ] **Step 3: Quick full-scan sanity check on 3 representative circuits**

```bash
cd /home/swear01/ScanForge
python3 scripts/run_atpg_sweep.py --circuits b03 b07 b13 --ratios 0.0 --no-skip
```

Expected: full-scan coverage should be >80% for at least b03 and b07.

---

### Task 5: Run full 55-experiment sweep

**Files:**
- Run: `scripts/run_atpg_sweep.py`
- Output: `results/itc99_partial_scan.csv`

- [ ] **Step 1: Run full-scan baselines (11 circuits, x=0%)**

```bash
cd /home/swear01/ScanForge
python3 scripts/run_atpg_sweep.py --ratios 0.0 --no-skip
```

This runs 11 circuits at full-scan. Expected runtime: ~30 min for small circuits, longer for b12/b14/b15.

- [ ] **Step 2: Run partial-scan no-recovery (11 circuits × 4 ratios, T=1)**

Modify `run_atpg_sweep.py` or create a wrapper that sets `frame=1` for partial-scan no-recovery runs:

```bash
python3 scripts/run_atpg_sweep.py --ratios 0.05 0.10 0.15 0.20 --no-skip
```

Note: the current script uses `frame=8` for `ratio > 0`. For the no-recovery case, we need `frame=1`. This requires either:
- Adding a `--mode no_recovery` flag that forces `frame=1`
- Or running the no-recovery and partial-recovery sweeps separately

- [ ] **Step 3: Run partial-scan with sequential recovery (11 circuits × 4 ratios, T=8)**

```bash
python3 scripts/run_atpg_sweep.py --ratios 0.05 0.10 0.15 0.20 --no-skip --frame 8
```

- [ ] **Step 4: Verify CSV completeness**

```bash
wc -l results/itc99_partial_scan.csv
# Expected: 1 header + 55 rows = 56 lines (or 99 if 3 cases × 11 circuits × 3 ratios + 11 full-scan)
```

- [ ] **Step 5: Spot-check ordering constraints**

```bash
python3 -c "
import csv
with open('results/itc99_partial_scan.csv') as f:
    rows = list(csv.DictReader(f))
for c in ['b03','b07','b13']:
    fs = [r for r in rows if r['circuit']==c and float(r['nonscan_ratio'])==0.0]
    nr = [r for r in rows if r['circuit']==c and r.get('mode','')=='no_recovery']
    pr = [r for r in rows if r['circuit']==c and r.get('mode','')=='partial_T4']
    if fs: print(f'{c} full_scan: {fs[0][\"fault_coverage\"]}%')
    if nr: print(f'{c} no_recovery: {nr[0][\"fault_coverage\"]}%')
    if pr: print(f'{c} partial_T8: {pr[0][\"fault_coverage\"]}%')
"
```

Expected: `full_scan >= partial_T8 >= no_recovery` for each circuit.

---

### Task 6: Add three-case evaluation schema to sweep runner

**Files:**
- Modify: `scripts/run_atpg_sweep.py`
- Output: `results/itc99_partial_scan.csv` with `case` and `depth` columns

- [ ] **Step 1: Add `case` and `depth` columns to CSV schema**

Update `CSV_FIELDS` in `run_atpg_sweep.py`:

```python
CSV_FIELDS = [
    "circuit", "case", "nonscan_ratio", "depth",
    "fault_coverage", "test_coverage",
    "DT", "AU", "AB", "UD", "patterns", "runtime_s",
]
```

- [ ] **Step 2: Set case/depth based on run parameters**

In `run_one()`:
- `ratio == 0` → `case = "full_scan"`, `depth = 1`
- `ratio > 0, frame == 1` → `case = "partial_scan_no_recovery"`, `depth = 0`
- `ratio > 0, frame == 8` → `case = "partial_scan_sequential"`, `depth = 8`

- [ ] **Step 3: Add `--mode` flag to select case**

```python
ap.add_argument("--mode", choices=["full_scan", "no_recovery", "sequential"],
                default=None, help="Force evaluation case mode")
```

- [ ] **Step 4: Verify backward compatibility**

```bash
python3 scripts/run_atpg_sweep.py --circuits b03 --ratios 0.0 --dry-run
```

---

### Task 7: Generate final report tables and figures

**Files:**
- Create: `scripts/generate_final_figures.py`
- Output: `figures/` directory with publication-quality PNGs

- [ ] **Step 1: Create RQ1 figure — coverage loss vs non-scan ratio**

Bar chart or line plot showing:
- X-axis: non-scan ratio (0%, 5%, 10%, 15%, 20%)
- Y-axis: fault coverage (%)
- One line/bar group per circuit
- Full-scan baseline as reference line

- [ ] **Step 2: Create RQ2 figure — coverage recovery by sequential ATPG**

Grouped bar chart showing:
- X-axis: circuit name
- Y-axis: fault coverage (%)
- Three bars per circuit: full_scan, no_recovery, sequential_T8
- At the highest non-scan ratio (20%)

- [ ] **Step 3: Create RQ3 figure — scalability trend**

Table or scatter plot showing:
- Coverage loss (full_scan - no_recovery) vs circuit size (FF count)
- Coverage recovery (sequential_T8 - no_recovery) vs circuit size

- [ ] **Step 4: Create summary CSV for report tables**

```python
# Pivot table: circuit × ratio → fault_coverage for each case
```

- [ ] **Step 5: Generate runtime and pattern count comparison table**

Secondary metrics table for the report appendix.

---

### Task 8: Update progress report and checklist

**Files:**
- Modify: `docs/progress_report.md`
- Modify: `docs/checklist.md`
- Modify: `docs/spec.md`

- [ ] **Step 1: Fill in Results section of progress_report.md**

Write the RQ1/RQ2/RQ3 analysis using the generated tables and figures.

- [ ] **Step 2: Fill in Discussion section**

Discuss:
- Coverage loss trends
- Recovery effectiveness
- Scalability observations
- Limitations (T=8 fixed, NanGate45 proxy timing)

- [ ] **Step 3: Update checklist.md with final status**

Mark all completed items. Record any remaining open questions.

- [ ] **Step 4: Update spec.md implementation status table**

Change Task D and E to "Done" if sweep completed successfully.

---

## Execution Priority

Given the 6/16 deadline:

1. **Task 1** (diagnose) — MUST DO FIRST. Everything else depends on understanding the root cause.
2. **Task 2** (fix `_const0_`) — likely needed based on Task 1 findings
3. **Task 3** (fix b05) — parallel with Task 2
4. **Task 4** (re-synthesize) — after Tasks 2+3
5. **Task 5** (full sweep) — after Task 4. This is the critical path.
6. **Task 6** (schema update) — can be done in parallel with Task 5
7. **Task 7** (figures) — after Task 5
8. **Task 8** (report) — after Task 7

**Fallback plan:** If the coverage issue cannot be fully resolved, use the current partial results (b03, b04, b07, b08, b09, b13) and document the limitation. The s27 pilot results are already validated and can serve as the primary correctness demonstration.
