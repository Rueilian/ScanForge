# ScanForge Development Checklist

This file is the required entry point before writing code for this project.

## Rules

- Every code task must start by adding or updating a checklist entry here.
- Follow a TDD-style order: define behavior, identify a failing check, implement the minimum fix, verify, then move on.
- Do not mark an item complete unless the corresponding check has actually been run.
- If a task is exploratory and no automated test exists yet, define the smallest reproducible command or artifact check first.
- Keep this checklist aligned with [spec.md](./spec.md). Do not let completed sub-tasks imply that the entire spec is complete.

---

## Spec Alignment

Source of truth: [spec.md](./spec.md)

Current alignment to Section 7 `Implementation Plan`:

| Spec Task | Meaning in spec | Current status |
|---|---|---|
| Task A | Timing analysis and non-scan mask generation | `in progress` |
| Task B | Partial-scan circuit modeling | `in progress` |
| Task C | Sequential ATPG design | `not started` |
| Task D | Evaluation and reporting | `in progress` |

Important: the project is **not** done. So far, the implemented work mainly covers the timing-driven exclusion baseline and its reporting pipeline. The sequential ATPG part required by `Task C` is still missing.

---

## Update Format

When adding a new task to this file, use the same section structure already used below:

- `Task`
- `Goal`
- `Acceptance Criteria`
- `TDD Plan`
- `Checks`
- `Notes`

The format is intentionally kept inside this project file instead of a shared generic template.

---

## Task: Timing-driven scan exclusion baseline

Related spec task: `Task A` and part of `Task B`

### Goal

Provide a reproducible baseline flow that can identify timing-critical FFs, exclude the top `x%` as non-scan, build the remaining single scan chain, and report baseline metrics for the partial-scan architecture.

### Acceptance Criteria

- [x] The CLI can load a timing ranking from CSV and apply `--exclude-ratio`
- [x] The CLI can build a timing proxy directly from a gate-level netlist
- [x] The tool can export an aligned timing ranking / non-scan mask CSV
- [x] The tool can run the main `5%/10%/15%/20%` exclusion sweep

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Exclusion CLI exists | `./src/scanforge ../results/s27.sf --timing-ranking /tmp/s27_timing.csv --exclude-ratio 0.34` | prints timing-driven exclusion baseline report | `passed` |
| Netlist timing proxy works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --exclude-ratio 0.34` | prints baseline report without manual ranking CSV | `passed` |
| Ranking export works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --timing-ranking-out ../results/s27_timing_proxy.csv --exclude-ratio 0.34` | writes ranking CSV | `passed` |
| Exclusion sweep works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --exclude-sweep --exclude-summary-csv ../results/s27_exclude_sweep.csv` | writes 4-row sweep CSV | `passed` |
| Build regression | `make` in `src/` | ScanForge build succeeds | `passed` |

### Notes

- Assumptions:
- Timing criticality is currently approximated by combinational logic depth feeding each FF `D` input.
- This is a structural proxy for the spec baseline, not full STA.
- Risks:
- Small circuits may collapse multiple exclusion ratios to the same integer number of non-scan FFs.
- Pattern applicability is currently strict and may remain zero for many ATPG-generated `.sf` patterns.
- Follow-up:
- Replace or supplement the structural timing proxy with a richer timing-analysis flow if time permits.
- Add report-friendly aggregation over the generated sweep CSVs.

---

## Task: Batch timing-exclusion experiment generation

Related spec task: `Task D` and part of `Task A`

### Goal

Generate timing-driven exclusion results across multiple ISCAS'89 benchmarks so the project has a reusable first-pass experiment table aligned with the current spec.

### Acceptance Criteria

- [x] A batch script exists for multi-circuit exclusion sweep
- [x] The script writes per-circuit sweep CSV files
- [x] The script writes one master CSV for downstream reporting
- [x] The flow has been exercised on all currently available ISCAS'89 benchmarks in this workspace

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Batch script exists | `bash scripts/run_timing_exclusion_sweep.sh s27` | writes per-circuit and master CSV outputs | `passed` |
| FAN_ATPG script execution | `./pkg/fan/bin/opt/fan -f script/fanScripts/atpg_s27.script` | generates `FAN_ATPG/results/s27.sf` | `passed` |
| Full benchmark generation | `for s in ...; do ./pkg/fan/bin/opt/fan -f ...; done` | all 12 target `.sf` files are generated | `passed` |
| Full batch exclusion sweep | `bash scripts/run_timing_exclusion_sweep.sh` | writes 12 per-circuit sweep CSVs and one master CSV | `passed` |
| Master CSV completeness | `wc -l results/timing_exclusion/timing_exclusion_master.csv` | `49` lines = header + `12 × 4` rows | `passed` |

### Notes

- Assumptions:
- The available benchmark set is the 12 ISCAS'89 circuits already shipped in the repository.
- The current FAN_ATPG top-level build is fragile, so the working binary path is `FAN_ATPG/pkg/fan/bin/opt/fan`.
- Risks:
- Re-running FAN_ATPG may be time-consuming on larger circuits.
- Current batch flow depends on matching `.sf` names and `mod_netlist/*.v` names.
- Follow-up:
- Add a report summarizer that groups the master CSV by circuit and exclusion ratio.
- Add a manifest of generated artifacts for final-report reproducibility.

---

## Task: Timing-exclusion report summary

Related spec task: `Task D`

### Goal

Turn the raw timing-exclusion experiment outputs into a smaller report-oriented summary that is easier to cite in the final report and easier to inspect during development.

### Acceptance Criteria

- [x] A reproducible summary flow exists for `results/timing_exclusion/timing_exclusion_master.csv`
- [x] The summary highlights coverage and activity trends across exclusion ratios
- [x] The output format is concise enough to use in the report or slides without manual cleanup
- [x] The summary flow is documented in the repository

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Summary command exists | `python3 scripts/summarize_timing_exclusion.py results/timing_exclusion/timing_exclusion_master.csv results/timing_exclusion/report_summary.csv` | a deterministic summary can be generated from the master CSV | `passed` |
| Summary artifact is generated | `python3 - <<'PY' ... Path('results/timing_exclusion/report_summary.csv').exists() ... PY` | a report-oriented CSV is written | `passed` |
| Regression check | `bash scripts/run_timing_exclusion_sweep.sh s27` | existing exclusion batch flow still works | `passed` |

### Notes

- Assumptions:
- The first summary should reuse the existing master CSV rather than rerun ATPG.
- Risks:
- It is easy to over-design the summary format before knowing what the report actually needs.
- Follow-up:
- If the report needs a presentation-ready table, add a Markdown export on top of the current CSV summary.
