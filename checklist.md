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
| Task C | Sequential ATPG design | `in progress` |
| Task D | Evaluation and reporting | `in progress` |

Important: the project is **not** done. So far, the implemented work mainly covers the timing-driven exclusion evaluation case and its reporting pipeline. The sequential ATPG part required by `Task C` is still missing.

---

## Working Board

Use this board to show what the spec still requires, not only what has already been completed.

### Task A. Timing analysis and non-scan mask generation

- Completed:
- [x] Timing-ranking CSV input path is supported
- [x] Netlist-based timing proxy exists for automatic FF ranking
- [x] Top-`x%` non-scan mask generation works for `5/10/15/20%`
- [x] Batch generation across the current benchmark set works
- In progress:
- [ ] Decide whether the current structural timing proxy is sufficient for the final report comparison set
- [ ] Define how timing-proxy assumptions will be documented in report figures/tables
- Next:
- [ ] Add a reproducibility note for ranking generation per benchmark
- [ ] Decide whether to freeze the current ranking method or leave room for one refinement
- Unknown / blocked:
- [ ] No richer timing-analysis flow has been selected yet beyond the current proxy

### Task B. Partial-scan circuit modeling

- Completed:
- [x] Single-chain scan-capable FF construction exists after non-scan exclusion
- [x] Non-scan FF mask can be exported for downstream use
- [x] Partial-scan comparison metrics can be reported from the current flow
- [x] The `partial-scan without sequential recovery` evaluation case artifact and comparison fields are now defined
- In progress:
- [ ] Separate outputs that belong only to the current implemented case from outputs that must survive future sequential recovery comparison
- Next:
- [ ] Decide whether the current comparison columns are sufficient or whether one dedicated residual-fault field is required before Task C
- Unknown / blocked:
- [ ] The boundary between current modeling code and future sequential ATPG integration is not fixed yet

### Task C. Sequential ATPG design

- Completed:
- [x] Pairwise comparison targets among the three evaluation cases are defined
- [x] The minimum row-oriented result artifact for the future sequential-recovery case is defined
- In progress:
- [ ] Narrow the first bounded sequential recovery target to the smallest runnable experiment
- Next:
- [ ] Decide whether the first prototype should emit a new CSV directly or adapt the current exclusion master CSV into the new schema
- [ ] Decide how unrecovered faults will be represented once the first sequential-recovery prototype exists
- [ ] Choose the first bounded-depth recovery mechanism to prototype
- [ ] Write the first failing check for sequential recovery
- Unknown / blocked:
- [ ] Exact sequential ATPG algorithm is still open
- [ ] It is not yet decided whether recovery will be built by extending existing FAN_ATPG behavior or by orchestration around existing outputs

### Task D. Evaluation and reporting

- Completed:
- [x] Multi-benchmark exclusion sweep exists
- [x] Master CSV aggregation exists
- [x] Report-oriented CSV summary exists
- In progress:
- [ ] Define the final experiment matrix so reporting matches the three spec evaluation cases
- [ ] Separate current-case-only metrics from metrics that must survive into sequential-recovery comparison tables
- Next:
- [ ] Add final-report table generation for coverage, runtime, and pattern-count comparison
- [ ] Add sequential-depth sweep support once Task C exists
- [ ] Prepare one reproducible artifact list for all report figures/tables
- Unknown / blocked:
- [ ] Runtime and pattern-count comparisons required by the spec cannot be completed before Task C

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

## Task: Timing-driven scan exclusion case

Related spec task: `Task A` and part of `Task B`

### Goal

Provide a reproducible flow for the current timing-driven exclusion evaluation case: identify timing-critical FFs, exclude the top `x%` as non-scan, build the remaining single scan chain, and report comparison metrics for the resulting partial-scan architecture.

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
| Exclusion CLI exists | `./src/scanforge ../results/s27.sf --timing-ranking /tmp/s27_timing.csv --exclude-ratio 0.34` | prints timing-driven exclusion evaluation-case report | `passed` |
| Netlist timing proxy works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --exclude-ratio 0.34` | prints evaluation-case report without manual ranking CSV | `passed` |
| Ranking export works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --timing-ranking-out ../results/s27_timing_proxy.csv --exclude-ratio 0.34` | writes ranking CSV | `passed` |
| Exclusion sweep works | `./src/scanforge ../results/s27.sf --timing-netlist ../FAN_ATPG/mod_netlist/s27.v --exclude-sweep --exclude-summary-csv ../results/s27_exclude_sweep.csv` | writes 4-row sweep CSV | `passed` |
| Build regression | `make` in `src/` | ScanForge build succeeds | `passed` |

### Notes

- Assumptions:
- Timing criticality is currently approximated by combinational logic depth feeding each FF `D` input.
- This is a structural proxy for the current spec evaluation case, not full STA.
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

---

## Task: Partial-scan without sequential recovery case definition

Related spec task: `Task B` and prerequisite for `Task C`

### Goal

Define the exact interface and result fields for the `partial-scan ATPG without sequential recovery` case, so later sequential ATPG work has a stable pairwise comparison target.

### Acceptance Criteria

- [x] The checklist names the exact artifact or command that represents the `partial-scan ATPG without sequential recovery` case
- [x] The required comparison fields are listed explicitly
- [x] The case definition is narrow enough to support the first sequential-recovery failing check

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Case definition exists | inspect `README.md`, `spec.md`, and current CLI/result files | one concrete definition of the current implemented comparison case is written down | `passed` |
| Comparison fields are fixed | inspect current summary CSV and comparison outputs | coverage-oriented comparison fields are enumerated explicitly | `passed` |

### Notes

- Assumptions:
- The first sequential ATPG work should compare the three evaluation cases pairwise instead of forcing one global baseline term.
- The canonical current-case artifact is one row from `results/timing_exclusion/timing_exclusion_master.csv`.
- The canonical current-case command is the current `--exclude-sweep` flow documented in `README.md`.
- Risks:
- If the current `partial-scan without sequential recovery` case is underspecified now, Task C will drift and pairwise comparisons will not be stable.
- Follow-up:
- The next missing definition is how residual faults will be represented before bounded sequential recovery is attempted.

---

## Task: Sequential recovery comparison contract

Related spec task: `Task C` and `Task D`

### Goal

Define the required outputs for the future `partial-scan ATPG with sequential recovery` case before choosing the exact algorithm, so the implementation has a fixed comparison target against the other two evaluation cases.

### Acceptance Criteria

- [x] The checklist states which three evaluation cases must appear in the final pairwise comparison
- [x] The checklist states that `T = 0` corresponds to the current `partial-scan ATPG without sequential recovery` case
- [x] The checklist lists the minimum comparison fields that the future sequential-recovery case must report
- [x] The checklist separates fixed comparison requirements from still-open algorithm questions
- [x] The checklist defines the minimum row shape of the future sequential-recovery result artifact

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Comparison contract exists | inspect `spec.md`, `README.md`, and this checklist | the future sequential-recovery case has a written comparison contract | `passed` |
| Minimum fields are fixed | inspect `results/timing_exclusion/timing_exclusion_master.csv` and `spec.md` metrics | the required shared fields are explicitly listed | `passed` |
| Row artifact is defined | inspect `README.md` and this checklist | the future sequential-recovery case has a minimum CSV row schema | `passed` |

### Notes

- Fixed comparison requirements:
- The final report must compare `full-scan ATPG`, `partial-scan ATPG without sequential recovery`, and `partial-scan ATPG with sequential recovery`.
- The current implemented case is the `T = 0` point in any sequential-depth sweep.
- The future sequential-recovery case must preserve at least these fields for pairwise comparison:
  `circuit`, `case`, `ratio`, `depth`, `coverage`, `pattern_count`, and `runtime_sec`.
- The minimum intended artifact is one CSV row per `(circuit, case, ratio, depth)`.
- If the current proxy-based flow is reused before true fault coverage exists, the temporary shared field must still map cleanly to a later true-coverage field.
- Open algorithm questions:
- The exact bounded sequential ATPG mechanism is still undecided.
- It is still open whether the first prototype should extend FAN_ATPG internals or orchestrate around existing outputs.
- It is still open how unrecovered faults will be represented in the first prototype.
- Follow-up:
- The next Task C step should decide how the first sequential-recovery prototype will emit this schema.

---

## Task: Direct evaluation-case CSV output for exclusion sweep

Related spec task: `Task B`, `Task C`, and `Task D`

### Goal

Make the current `--exclude-summary-csv` path emit the row-oriented evaluation-case schema directly from the main program, so future sequential-recovery results can reuse the same report format without an extra normalization step.

### Acceptance Criteria

- [x] `--exclude-summary-csv` writes rows that include `circuit`, `case`, `ratio`, `depth`, `coverage`, `pattern_count`, and `runtime_sec`
- [x] The current timing-driven exclusion case is emitted as `case = partial_scan_no_recovery`
- [x] The current timing-driven exclusion case is emitted as `depth = 0`
- [x] Existing exclusion batch flow still produces a valid master CSV
- [x] Existing summary script still works on the updated master CSV

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| New row schema exists | inspect exclusion CSV header after one sweep run | required evaluation-case columns appear in the output | `passed` |
| Batch master CSV still builds | `bash scripts/run_timing_exclusion_sweep.sh s27` | the batch flow finishes and writes a master CSV with the new schema | `passed` |
| Summary script still works | `python3 scripts/summarize_timing_exclusion.py results/timing_exclusion/timing_exclusion_master.csv results/timing_exclusion/report_summary.csv` | summary CSV is regenerated successfully from the new schema | `passed` |

### Notes

- Assumptions:
- For the current implemented case, `coverage` may temporarily mirror `coverage_proxy_combined`.
- For the current implemented case, `pattern_count` will mirror the number of directly applicable patterns from the existing estimate path.
- Risks:
- Changing the CSV header in-place can break existing scripts if the new schema is not propagated consistently.
- Follow-up:
- This path is now in place for the current implemented case; the next sequential-recovery prototype should target the same row schema directly.
