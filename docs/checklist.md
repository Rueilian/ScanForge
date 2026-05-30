# ScanForge Development Checklist

This file is the required entry point before writing code for this project.

## Rules

- Every code task must start by adding or updating a checklist entry here.
- Follow a TDD-style order: define behavior, identify a failing check, implement the minimum fix, verify, then move on.
- Do not mark an item complete unless the corresponding check has actually been run.
- If a task is exploratory and no automated test exists yet, define the smallest reproducible command or artifact check first.
- Keep this checklist aligned with [spec.md](./spec.md). Do not let completed sub-tasks imply that the entire spec is complete.
- Any important decision must be written down here and, when it changes project definition, also reflected in [spec.md](./spec.md).

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

## Decision Log

- `partial_scan_no_recovery` remains defined as:
  - `T = 1`
  - non-scan FF initial state modeled as `X`
- `partial_scan_no_recovery` must not use extra initialization cycles outside the modeled time frames
- A valid `partial_scan_no_recovery` implementation must treat non-scan FFs as unknown and uncontrollable at the single modeled frame
- `partial_scan_with_recovery` will be tackled only after the above `T = 1` model is verified to behave differently from `full_scan`
- Important decisions must not remain only in chat history; they must be reflected in both `spec.md` and `checklist.md` when applicable.

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
- [ ] Make the `partial_scan_no_recovery` `T = 1, X-initial-state` definition behave as a true unknown-uncontrollable boundary instead of collapsing to `full_scan`
- [ ] Record the exact internal FAN_ATPG modification points required for the `T = 1, X-initial-state` no-recovery model
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

---

## Task: T=1 X-source no-recovery model audit

Related spec task: `Task C`

### Goal

Identify the exact FAN_ATPG internal paths that must be changed so that `partial_scan_no_recovery` with `T = 1` and non-scan initial state `X` behaves as a true unknown-uncontrollable model instead of collapsing to `full_scan`.

### Acceptance Criteria

- [x] The controllability boundary points for `TIEX` are explicitly listed
- [x] The line-type / headline classification impact is explicitly listed
- [x] The SCOAP impact is explicitly listed
- [x] The pattern / simulation consistency impact is explicitly listed
- [ ] The remaining `PPO` shortcut paths are classified into observation semantics vs structural gate semantics
- [x] A minimum modification set is written down before deeper ATPG edits begin

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check after each minimum patch
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Stage-1 s27 check | `python3 scripts/run_stage1_fan_cases.py --circuit s27 --ratio 0.67 --timing-csv results/timing_exclusion/s27_timing_proxy.csv --out results/stage1_s27_cases_x67.csv` | `partial_scan_no_recovery` should differ from `full_scan`; currently fails because both rows are identical | `failed as expected` |
| ATPG boundary audit | read `FAN_ATPG/pkg/core/src/atpg.cpp`, `atpg.h` | list all places where `PI/PPI` are treated as controllable or stopping boundaries | `passed` |
| SCOAP audit | read `FAN_ATPG/pkg/core/src/atpg.cpp` | locate `cc0/cc1/co` handling for `PPI` and note missing `TIEX` handling | `passed` |
| Simulation audit | read `FAN_ATPG/pkg/core/src/simulator.h` | confirm `TIEX/TIEZ` already evaluate to `X` in good/fault simulation | `passed` |
| Pattern/simulation interface audit | read `FAN_ATPG/pkg/core/src/atpg.h`, `simulator.h`, `simulator.cpp` | identify whether `pattern.PPI_` still treats non-scan PPI as scan-controllable | `passed` |

### Notes

- Assumptions:
- `TIEX` is the intended representation of an unknown non-scan source at `T = 1`.
- Risks:
- Updating only gate type semantics is insufficient; ATPG backtrace and heuristic logic may still collapse the model to `full_scan`.
- Minimum modification set currently identified:
- treat `TIEX/TIEZ` as uncontrollable stopping boundaries in backward implication and fanout-free backtrace
- update line-type classification so `TIEX` is not treated like an ordinary internal gate
- update SCOAP controllability handling so `TIEX` is not scored like `PI/PPI`
- verify whether pattern export should continue writing `TIEX`-backed PPIs into `pattern.PPI_`
- split scan and non-scan semantics at the ATPG/pattern boundary: non-scan PPI bits must not be exported as controllable `pattern.PPI_`
- split scan and non-scan semantics at the simulation boundary: single-pattern and packed fault simulation must not re-apply `pattern.PPI_` values onto non-scan PPIs
- prevent X-fill from assigning `0/1` to non-scan `pattern.PPI_` entries
- Verification update:
- A first minimum patch covering ATPG boundary checks, line-type classification, and SCOAP was applied and rebuilt.
- `s27` still produced identical `full_scan` and `partial_scan_no_recovery` rows at `67%` non-scan ratio, so the current no-recovery model remains invalid.
- Second-round audit located the main remaining leak in the ATPG-to-pattern and pattern-to-simulation interfaces:
  - `writeAtpgValToPatternPI()` exported all `PPI` bits uniformly
  - `randomFill()` / `adjacentFill()` filled all `PPI` `X` bits uniformly
  - `Simulator::assignPatternToCircuitInputs()` and the packed-fault-sim path in `simulator.cpp` re-applied all `pattern.PPI_` bits uniformly
- A valid next patch must split those paths using `isPpiNonscan_`.
- Third-round verification update:
  - the `isPpiNonscan_` split was applied to pattern export, X-fill, single-pattern fault simulation, and packed-pattern fault simulation
  - rebuild succeeded
  - `python3 scripts/run_stage1_fan_cases.py --circuit s27 --ratio 0.67 --timing-csv results/timing_exclusion/s27_timing_proxy.csv --out results/stage1_s27_cases_x67_after_ppi_split.csv` now yields:
    - `full_scan`: `coverage=94.55`, `pattern_count=7`
    - `partial_scan_no_recovery`: `coverage=94.55`, `pattern_count=8`
  - interpretation: the new patch changed ATPG behavior enough to alter pattern count/runtime, but the current coverage oracle still does not separate the two cases.
  - a no-DTC control run also kept the same coverage:
    - `full_scan`: `coverage=94.55`, `pattern_count=9`
    - `partial_scan_no_recovery`: `coverage=94.55`, `pattern_count=8`
  - interpretation: the remaining mismatch is not only a dynamic-compression artifact; the deeper ATPG / fault-simulation semantics still need audit.
- Fourth-round verification update:
  - a `final objective` guard was added so `TIEX/TIEZ` no longer enter `finalObjectives_` and are skipped by `assignAtpgValToFinalObjectiveGates()`
  - rebuild succeeded, but `python3 scripts/run_stage1_fan_cases.py --circuit s27 --ratio 0.67 --timing-csv results/timing_exclusion/s27_timing_proxy.csv --out results/stage1_s27_cases_x67_after_finalobj_fix.csv` still yielded:
    - `full_scan`: `coverage=94.55`, `pattern_count=7`
    - `partial_scan_no_recovery`: `coverage=94.55`, `pattern_count=8`
  - interpretation: the `final objective / decision tree` leak was real but not the dominant remaining cause of the full-scan collapse.
- Fifth-round verification update:
  - the decisive remaining leak was observability, not controllability alone: ATPG propagation checks and fault simulation still treated all `PPO`s as observable even when the corresponding FF was declared non-scan
  - the observability fix now masks non-scan `PPO`s in ATPG propagation (`checkIfFaultHasPropagatedToPO()`, `xPathTracing()`, `doUniquePathSensitization()`, `depthFromPo_`, `co_`) and in both fault-simulation detection loops
  - rebuild succeeded
  - `python3 scripts/run_stage1_fan_cases.py --circuit s27 --ratio 0.67 --timing-csv results/timing_exclusion/s27_timing_proxy.csv --out results/stage1_s27_cases_x67_after_observability_fix.csv` now yields:
    - `full_scan`: `coverage=94.55`, `pattern_count=7`
    - `partial_scan_no_recovery`: `coverage=85.45`, `pattern_count=6`, `AU=10`, `UD=6`
  - interpretation: the `T = 1` no-recovery case now separates from `full_scan` in the expected direction, so non-scan FFs are no longer receiving full-scan observability through `PPO` endpoints
- Sixth-round semantic audit update:
  - the current observability mask is not enough to declare the implementation correct, because several ATPG paths still special-case all `PPO`s as generic single-input endpoints without checking whether the `PPO` is scan-observable
  - the main remaining paths are:
    - `doOneGateBackwardImplication()`
    - `findEasiestInput()`
    - the `pFaultyGate->gateType_ == ... || Gate::PPO` branches in fault activation / output-fault handling
    - the `pFaultyLine->gateType_ == ... || Gate::PPO` branch in faulty-line handling
  - audit conclusion:
    - the observability fix itself is semantically plausible
    - but these residual `PPO` shortcuts are not yet aligned with the new scan/non-scan observability criterion
    - they must be split into:
      - `PPO` as scan-observation endpoint
      - `PPO` as structural pseudo-output of the FF data input
  - next implementation step:
    - patch those three `atpg.cpp` paths only after each one is classified by role, so we do not accidentally break legitimate structural use of `PPO`
  - additional audit clue:
    - converting frame-0 non-scan FF sources from `PPI` to `TIEX` may also bypass code paths that are keyed only on `gateType_ == Gate::PPI`, especially in `fault.cpp`
    - this is not yet a confirmed bug, but it is now a tracked semantic-audit item because `TIEX` may need explicit handling wherever the engine distinguishes scan-FF pseudo-input semantics from ordinary internal-gate semantics
- Seventh-round semantic audit update:
  - a stronger bug class is now confirmed: several ATPG paths still perform direct `X -> 0/1` assignments on `TIEX/TIEZ`
  - this is a semantic violation independent of observability, because `TIEX/TIEZ` are supposed to model `unknown and uncontrollable` frame-0 non-scan FF sources
  - the first guard patch must block direct assignment into `TIEX/TIEZ` in:
    - `doOneGateBackwardImplication()`
    - `doUniquePathSensitization()`
    - `setFaultyGate()`
    - `setUpFirstTimeFrame()`
  - re-run `s27` stage-1 sanity after this patch and specifically inspect whether the `G17/U_G17/G11` cone is still being justified through frame-0 non-scan state
  - new structural root cause found while tracing `G17 SA1`:
    - `build_circuit` resolved `nonscanCellNames_` too late
    - `createCircuitPPI()` therefore built frame-0 non-scan PPIs as ordinary `PPI`, not `TIEX`
    - this explains why a single-fault run could still report `ppi: 1XX` for `partial_scan_no_recovery`
  - next patch moves non-scan PPI resolution ahead of `createCircuitGates()` so `T = 1` frame-0 pseudo-inputs are born with partial-sequential semantics instead of being patched after the fact
  - follow-up execution fix:
    - once frame-0 non-scan PPIs become real `TIEX`, `doOneGateBackwardImplication()` must treat required assignments into those sources as immediate `CONFLICT`
    - leaving them as generic `unjustified` objectives causes the ATPG loop to spin on impossible final-objective decisions instead of backtracking cleanly
  - next convergence fix:
    - `findFinalObjective()` previously had no explicit failure return when every remaining objective ultimately depended on `TIEX`
    - this let the engine re-enter objective selection forever instead of surfacing a dead end to `generateSinglePatternOnTargetFault()`
    - patch it to return `false` when no assignable final objective exists, and let the caller backtrack or mark the fault untestable
- Eighth-round convergence audit update:
  - after the `build_circuit` ordering fix and the first `TIEX` guards, `partial_scan_no_recovery` stopped collapsing to `full_scan`, but bounded `run_atpg` runs now hang before report generation
  - the remaining hang is no longer explained by `findFinalObjective()` alone:
    - `multipleBacktrace()` now reports `finalObjectiveId < 0` for `TIEX/TIEZ` dead ends
    - but the `numGatesInDFrontier == 1` branch still treats `doUniquePathSensitization() == 0` as unconditional progress
  - semantic interpretation:
    - `doUniquePathSensitization() == 0` only means `no backward implication level is required`
    - it does not guarantee that any new event or assignment was created
    - when no event is pending, unconditional `continue` causes ATPG to spin on the same d-frontier without progress
  - next patch:
    - add an explicit `hasPendingEvents()` check
    - in the single-d-frontier path, if unique sensitization returns `0` and there are no pending events, fall through to `findFinalObjective()` instead of looping
  - stronger loop diagnosis:
    - `UNIQUE_PATH_SENSITIZE_FAIL` is still handled as a blind `continue`
    - this relies on the next `countEffectiveDFrontiers()` pass to remove the frontier, but that assumption is not valid when the failure is caused by a `TIEX` side-input requirement rather than by loss of structural x-path
    - in that case ATPG can revisit the same unique-sensitization failure forever
  - next patch refinement:
    - when `doUniquePathSensitization()` returns `UNIQUE_PATH_SENSITIZE_FAIL` in the single-d-frontier branch, treat it like a local dead end:
      - clear events
      - try backtrack
      - otherwise mark `FAULT_UNTESTABLE`
  - verification after the convergence fixes:
    - bounded `run_atpg` no longer hangs for either:
      - `script/fanScripts/s27_partial_g17_sa1.script`
      - `script/fanScripts/s27_partial_scan_no_recovery_x67.script`
    - the repaired ordering is now monotone in the expected direction on `s27` with `U_G5 U_G6` as non-scan FFs:
      - `full_scan, T=1`: `fault coverage = 94.55%`
      - `partial_scan, T=4`: `fault coverage = 79.25%`
      - `partial_scan_no_recovery, T=1`: `fault coverage = 39.36%`
    - interpretation:
      - the latest fixes restored termination and the expected `full_scan >= larger-T partial scan >= T=1 no-recovery` ordering
      - but the new `39.36%` result is a strong semantic change, so it still needs follow-up logic review rather than being accepted only because it dropped
  - ninth-round audit finding:
    - direct `add_fault <type> <pin>` single-fault checks are currently not trustworthy when fault collapsing is enabled
    - root cause:
      - `AddFaultCmd::addPinFault()` and `addCellFault()` index into `extractedFaults_` using `gateIndexToFaultIndex_`
      - but `gateIndexToFaultIndex_` is built for the uncollapsed ordering, while `extractedFaults_` is a separately constructed collapsed list
    - consequence:
      - targeted debug runs such as `add_fault SA1 G17` may select the wrong fault object
      - this explains why some single-fault checks contradicted the all-fault reports
    - next patch:
      - resolve specific faults by semantic match `(gateID, faultType, faultyLine)` against `extractedFaults_`, not by positional offset from `gateIndexToFaultIndex_`
  - tenth-round audit finding:
    - direct single-fault checks for top-level output ports originally selected the wrong semantic fault:
      - `add_fault SA1 G17` was using `faultyLine = 0`
      - but the extracted stuck-at fault corresponding to a `PO` is the single `PO` input-line fault (`faultyLine = 1`)
    - after fixing that mapping, direct `T=4` `add_fault SA1 G17` now consistently reports:
      - `AU`
      - `#Patterns = 0`
    - interpretation:
      - the earlier contradiction between single-fault and all-fault results for `G17` was partly a tooling bug
      - after the fix, the `G17` inconsistency is now between:
        - FAN_ATPG's own ATPG result (`AU`)
        - an independent state-space reachability check that found a robust `T=4` sequence
      - therefore the remaining contradiction is now much more likely to be a real ATPG-core bug, not just a reporting/debug-command issue
  - eleventh-round audit finding:
    - `T=4` direct debug and all-fault runs expose a new infrastructure-level mismatch for stuck-at ATPG:
      - ATPG can produce a pattern for `build_circuit --frame 4` + `add_fault SA1 G17`
      - but the surrounding pattern/report flow still does not classify the fault consistently
    - root cause candidate:
      - `Pattern` stores only `PI1_` and `PI2_`
      - simulator-side pattern replay only re-applies those first two PI frames
      - for `T > 2`, later PI frames of a valid ATPG solution are dropped before fault simulation / reporting
  - twelfth-round semantic audit finding:
    - the stronger root cause is now narrowed to inconsistent fault-frame mapping for multi-frame SAF
    - `TransitionDelayFaultATPG()` already shifts the target fault into a later frame, but `StuckAtFaultATPG()` still targeted frame-0 faults on an unrolled circuit
    - the simulator activation/injection paths also still used the original extracted SAF gate id, so ATPG generation and fault simulation were not operating on the same frame
    - semantic decision:
      - for multi-frame `SA0/SA1`, the fault belongs to the final observation frame
      - this same mapping must be shared by:
        - single-pattern ATPG target selection
        - DTC fault activation checks
        - parallel fault simulation activation / injection
        - parallel pattern simulation activation / injection
    - minimum implementation patch:
      - add a shared final-frame SAF mapping helper in ATPG
      - add the same mapping helper in simulator
      - re-run `G17 SA1 @ T=4` and the `s27` partial-scan sanity checks
  - twelfth-round verification update:
    - after the SAF final-frame mapping patch:
      - direct `build_circuit --frame 4` + `add_fault SA1 G17` no longer returns `AU`
      - the same debug case now reports:
        - `DT = 1`
        - `AU = 0`
        - `fault coverage = 100%`
        - `#Patterns = 1`
    - `s27` sanity checks also changed:
      - `full_scan, T=1`: `fault coverage = 94.55%`, `#Patterns = 7`
      - `partial_scan_no_recovery, T=1`: `fault coverage = 39.36%`, `#Patterns = 5`
      - `partial_scan, T=4`: `fault coverage = 88.68%`, `#Patterns = 4`
    - interpretation:
      - the final-frame SAF mapping fixes a real multi-frame consistency bug, not only a single-fault debug path
      - the ordering is now semantically plausible:
        - `full_scan >= partial_scan(T=4) >= partial_scan_no_recovery(T=1)`
      - the previous `79.25%` `T=4` figure should no longer be treated as current behavior after this patch
    - residual-`AU` audit:
      - `report_fault -s AU` on `s27`, `partial_scan`, `T=4` now shows the remaining collapsed `AU` faults are concentrated at `U_G10`:
        - `SA0 U_G10/A1`
        - `SA0 U_G10/A2`
        - `SA0 U_G10/ZN`
        - `SA1 U_G10/ZN`
      - representative spot checks:
        - `full_scan, T=1`, `SA0 U_G10/ZN`: `DT`, `100%`, `#Patterns = 1`
        - `full_scan, T=1`, `SA1 U_G10/ZN`: `DT`, `100%`, `#Patterns = 1`
        - `partial_scan, T=4`, `SA0 U_G10/ZN`: `AU`, `0%`, `#Patterns = 0`
        - `partial_scan, T=8`, `SA0 U_G10/ZN`: still `AU`, `0%`, `#Patterns = 0`
        - `partial_scan, T=8`, `SA1 U_G10/ZN`: still `AU`, `0%`, `#Patterns = 0`
      - interpretation:
        - after the `G17` / final-frame SAF fix, the remaining `AU` behavior is no longer a broad multi-frame mismatch
        - it is localized to the `U_G10 -> G5 -> G11/G17` sequential cone and may be a genuine partial-scan limitation rather than the same infrastructure bug
    - `U_G10` cone logic audit:
      - `U_G10/ZN` drives only the `D` input of `U_G5`
      - in `full_scan, T=1`, `U_G5` remains scan-observable through its `PPO`, so `U_G10` stuck-at faults are still detectable
      - direct full-scan spot checks confirm this:
        - `SA0 U_G10/ZN`: `DT`, one pattern, with `ppi: 1XX` and `ppo: 10X`
        - `SA1 U_G10/ZN`: `DT`, one pattern, with `ppo: 0XX`
      - in partial scan, `U_G5` is explicitly non-scan:
        - its frame-local `PPO` is no longer a legal scan observation endpoint
        - the final-frame stuck-at model places the fault on the observation frame itself, so the fault effect cannot wait one more frame and then be observed through `G5`
      - consequence:
        - `U_G10` stuck-at faults lose their only direct observation path once `U_G5` becomes non-scan
        - this explains why `SA0/SA1 U_G10/ZN` are detectable in full scan but remain `AU` in partial scan even when `T` increases from `4` to `8`
      - audit conclusion:
        - these residual `AU` faults are consistent with the intended sequential semantics and do not currently indicate the same multi-frame implementation bug that affected `G17`
    - thirteenth-round correctness-risk fix:
      - two remaining `PARTIAL_SEQUENTIAL` modeling risks were patched:
        - frame-0 non-scan PPIs are now created as `TIEX` at every sequential depth, not only at `T = 1`
        - later-frame PPI handling now uses the PPI layout slot rather than `gateType_ == PPI`, so non-scan state still transfers as `previous-frame PPO -> BUF -> next-frame PPI`
        - PPO observability now uses a bounds-safe gate-id helper instead of deriving an unchecked index from `totalGate_ - numPPI_`
      - rebuild succeeded with the existing warning noise
      - verification after this patch:
        - `full_scan, T=1`: `fault coverage = 94.55%`, `#Patterns = 7`
        - `partial_scan_no_recovery, T=1`: `fault coverage = 39.36%`, `#Patterns = 5`
        - `partial_scan, T=4`: `fault coverage = 86.67%`, `#Patterns = 4`
      - interpretation:
        - the expected ordering still holds: `full_scan >= partial_scan(T=4) >= partial_scan_no_recovery(T=1)`
        - the `T=4` result tightened from `88.68%` to `86.67%` because ATPG no longer receives scan-like control of frame-0 non-scan state or accidental non-final PPO observability
    - consequence:
      - even if the ATPG core solves a multi-frame stuck-at objective correctly,
        fault dropping and final fault classification may still be wrong
    - next implementation step:
      - extend the SAF pattern/simulator path to preserve and replay all PI frames
      - update reporting so multi-frame PI assignments are visible during debug
    - fourteenth-round correctness fix (PARTIAL_SEQUENTIAL defect audit):
      - three defects found during a full end-to-end review were patched:
        - defect 1: `adjacentFill()` PPI bit-0 guard in `atpg.h` was inverted and read `isPpiNonscan_[0]` out of bounds on full-scan; it could also X-fill a non-scan FF bit. Guard changed to `(isPpiNonscan_.empty() || !isPpiNonscan_[0])`, matching `randomFill()` and the sibling loop.
        - defect 2 (main): scan-FF PPI was only stored/replayed for frame 0, but the unrolled circuit leaves scan PPIs free at every frame, so for `T>1` the ATPG-chosen scan inputs at frames >= 1 were dropped from the saved pattern and replayed as `X`, making reported coverage non-reproducible. Added a per-frame `PPIFrames_` plane to `Pattern` (mirrors `PIFrames_`), populated it in `writeAtpgValToPatternPI()` (non-scan = `X`), and replayed it in both `Simulator::assignPatternToCircuitInputs()` and `Simulator::parallelPatternSetPattern()`, skipping non-scan FFs and falling back to `PPI_`.
        - defect 3: `writeGoodSimValToPatternPO()` captured the PPO/second-PO response from a hardcoded frame 1 (wrong for `T>2`) and did not mask non-scan PPOs. It now reads PO/PPO from the final observation frame `(numFrame_-1)*numGate_` and writes `X` for non-scan PPOs. The 2-frame on-disk `.pat`/STIL limitation is noted in `pattern_rw.cpp` (reported coverage is unaffected because it is computed from the in-memory multi-frame replay).
      - files changed: `pkg/core/src/atpg.h`, `pkg/core/src/pattern.h`, `pkg/core/src/simulator.h`, `pkg/core/src/simulator.cpp`, `pkg/core/src/pattern_rw.cpp`
      - rebuild succeeded (existing `-Wsign-compare` warning noise only); `bin/opt/fan` produced
      - verification on `s27` with `U_G5 U_G6` non-scan (rebuild, `add_fault --all`, SC+DTC on):
        - `full_scan, T=1`: `fault coverage = 94.55%`, `#Patterns = 7`
        - `partial_scan_no_recovery, T=1`: `fault coverage = 39.36%`, `#Patterns = 5`
        - `partial_scan, T=4`: `fault coverage = 86.67%`, `#Patterns = 4`
        - `partial_scan, T=8`: `fault coverage = 86.67%`, `#Patterns = 4`
      - interpretation:
        - numbers are unchanged from the thirteenth-round baseline, so the pattern/replay consistency fix did not regress coverage on this case
        - full-scan dominance (criterion 7) holds: `94.55% >= 86.67% >= 39.36%`
        - monotonic depth (criterion 6) holds: `coverage(T=8) >= coverage(T=4) >= coverage(T=1)`
        - the defect-2 fix is most impactful for larger circuits with scan FFs whose frame >= 1 state is needed; s27 has a single scan FF so its absolute numbers are stable
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

### Regression verification (2026-05-30)

| Check | Result | Status |
|---|---|---|
| s27 full_scan T=1 | fault_coverage=94.55%, DT=104, AU=0, patterns=15 | `passed` |
| s27 partial_scan_no_recovery T=1 x=67% | fault_coverage=39.36%, DT=37, AU=55 | `passed` |
| s27 partial_scan T=4 x=67% | fault_coverage=88.68% | `passed` |
| Non-scan PPI = X in pattern trace | U_G5/U_G6 PPI are X, U_G7 (scan) has values | `passed` |
| Monotonic ordering | full(94.55%) > T=4(88.68%) > T=1(39.36%) | `passed` |

### ITC'99 pipeline status (2026-05-30)

- 11/11 ITC'99 netlists synthesized
- 55/55 mask files generated
- b03, b05, b08, b09, b12, b14: segfault during `run_atpg` — suspected `_const0_` issue
- b07, b13: survive but low coverage (~44-55%) due to `_const0_` floating
- `_const0_` constraint fix is the immediate blocker for ITC'99 sweep

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

---

## Task: Repository hygiene for generated artifacts

Related spec task: `Task D`

### Goal

Classify current generated files and local-only changes so the repository keeps reproducible experiment outputs while avoiding accidental commits of temporary or build-only artifacts.

### Acceptance Criteria

- [x] `FAN_ATPG` submodule changes are classified into source changes versus generated/build artifacts
- [x] `progress_report.md` local edits are reviewed and their status is explicitly recorded
- [x] Root-level temporary result files are either ignored or folded into the formal result path

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| FAN_ATPG state reviewed | inspect `git status` inside `FAN_ATPG` | build artifacts and generated reports are separated from source changes | `passed` |
| progress report diff reviewed | inspect `git diff -- progress_report.md` | local report edits are classified as keep/edit/discard | `passed` |
| temp result policy enforced | inspect `.gitignore` and `git status` | root-level temporary `s27` result files no longer show as untracked | `passed` |

### Notes

- Findings:
- `FAN_ATPG` currently contains generated `.pat`, `.stil`, `.rpt`, `results/`, and many compiled binaries/objects under `bin/`, `lib/`, and `pkg/*/lib/opt/`.
- No FAN_ATPG source-file edits were observed in the current status output; the dirty state was dominated by generated/build artifacts and a checked-out submodule commit that did not match the parent repo.
- `progress_report.md` had been heavily rewritten toward the new project topic, but it still contained outdated and contradictory content such as `timing-driven vs random` comparison language.
- `results/s27_exclude_sweep.csv` and `results/s27_timing_proxy.csv` are now ignored as temporary root-level artifacts; the tracked canonical outputs remain under `results/timing_exclusion/`.
- Follow-up:
- Keep `progress_report.md` as a local draft for now instead of committing it with implementation changes.

---

## Task: Stage-1 FAN runner for full_scan and partial_scan_no_recovery

Related spec task: `Task C` and `Task D`

### Goal

Build a minimal single-point runner that uses the existing ISCAS'89 assets to emit two real FAN_ATPG result rows in the evaluation-case CSV schema: `full_scan` and `partial_scan_no_recovery`.

### Acceptance Criteria

- [x] One command can run `full_scan` for `s27`
- [x] One command can run a candidate `partial_scan_no_recovery` flow for `s27` at ratio `0.10`
- [x] Both rows are written in the evaluation-case CSV schema
- [ ] `coverage`, `pattern_count`, and `runtime_sec` come from FAN_ATPG `report_statistics`
- [ ] The non-scan FF set is derived from the existing timing-ranking CSV using the same selection rule as the current timing-exclusion flow

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [x] Implement the minimum code change
- [x] Re-run the same check until it passes
- [x] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Runner exists | inspect `scripts/` | a dedicated stage-1 FAN runner script exists | `passed` |
| full_scan row works | `python3 scripts/run_stage1_fan_cases.py --circuit s27 --ratio 0.10 --timing-csv results/timing_exclusion/s27_timing_proxy.csv --out results/stage1_s27_cases.csv` | one CSV row is emitted with real FAN_ATPG values | `passed` |
| candidate no_recovery row works | same command as above | one CSV row is emitted for the candidate no-recovery definition | `passed` |
| Schema matches | inspect `results/stage1_s27_cases.csv` | row shape matches `circuit,case,ratio,depth,coverage,pattern_count,runtime_sec` plus extra context fields if present | `passed` |

### Notes

- Assumptions:
- Stage 1 is being executed on the currently available `ISCAS'89` assets because the local worktree does not contain runnable ITC'99 netlists.
- The current candidate definition for `partial_scan_no_recovery` was `set_nonscan_ff ...` with `build_circuit --frame 1`.
- Risks:
- The older `run_atpg_sweep.py` uses a different benchmark family and CSV schema, so it should not be modified casually for this stage-1 proof point.
- Evidence now shows that `set_nonscan_ff` has no effect when `frame = 1` in the current FAN_ATPG implementation: `s27` full-scan and candidate no-recovery reports are numerically identical.
- Follow-up:
- Decide a revised definition for `partial_scan_no_recovery` before extending the runner to `partial_scan_with_recovery`.

---

## Task: Partial-scan sequential ATPG correctness criteria

Related spec task: `Task C`

### Goal

Define the semantic correctness criteria for partial-scan sequential ATPG before continuing deeper implementation debugging, so later implementation checks are judged against stable model requirements instead of expected numbers alone.

### Decision State

- Current active decision: `correctness criteria before implementation audit`
- Chosen option: `approved by user objective`
- Approval evidence: `user objective: 先訂 correctness critieria，再開始查implementation`

### Acceptance Criteria

- [ ] The criteria distinguish scan FF controllability from non-scan FF controllability
- [ ] The criteria define what `T = 1` and `T > 1` mean in this project
- [ ] The criteria define the role of unknown initial state `X`
- [ ] The criteria define the sequential justification requirement
- [ ] The criteria define expected ordering constraints among full-scan and partial-scan cases

### TDD Plan

- [x] Define the smallest failing check first
- [x] Run the failing check and record the result
- [ ] Implement the minimum code change
- [ ] Re-run the same check until it passes
- [ ] Run adjacent regression checks

### Checks

| Check | Command / Method | Expected Result | Status |
|---|---|---|---|
| Model evidence review | compare `spec.md`, `FAN_s27_partial.rpt`, and `results/stage1_s27_cases_x67.csv` | criteria are based on actual observed mismatch, not only intuition | `passed` |
| Criteria publication | update `spec.md` and `checklist.md` | correctness criteria become explicit project artifacts | `passed` |

### Notes

- Assumptions:
- The current observed mismatch is between intended semantics and current engine behavior, not proof that the intended semantics are wrong.
- Risks:
- If criteria are vague, later implementation work may optimize for expected numbers rather than correct semantics.
- Follow-up:
- After criteria are written down, inspect FAN_ATPG implementation against each criterion one by one.
- Preliminary implementation audit against the criteria:
- Criterion 1 and 2 are partially represented in `circuit.cpp`: non-scan FF names are captured and `PARTIAL_SEQUENTIAL` connects non-scan PPO->next-frame PPI only when `T > 1`.
- Criterion 3 is only approximated for `T = 1`: frame-0 non-scan PPIs are converted to `TIEX`, but observed behavior still matches `full_scan`, so the intended unknown-uncontrollable semantics are not yet reflected at the ATPG result level.
- Criterion 4 is the main open gap: current evidence suggests the engine still does not realize a meaningful sequential-justification penalty at `T = 1`, even after the first boundary/SCOAP patch.
- Criteria 5 and 6 remain the audit oracle for future checks: if a later implementation violates monotonic depth or full-scan dominance, treat that as a correctness bug, not a new model definition.
- Twelfth-round audit finding:
  - `G17 SA1 @ T=4` still returns `AU` almost immediately in single-fault mode.
  - Current strongest root-cause hypothesis: `findFinalObjective()` only turns
    `X` head lines into final objectives and silently skips head lines already
    fixed to `H/L` by fault activation.
  - For multi-frame ATPG this is too aggressive: a decided head line may still
    require upstream justification and must not be dropped from the objective
    flow.
  - Follow-up refinement: in the failing `G17` path, the stronger issue may be
    even earlier: when fault activation fixes a head line before any unjustified
    bound line exists, that head line may never enter `initialObjectives_` at
    all.
