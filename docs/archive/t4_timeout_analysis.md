# T=4 Per-Target-Fault Timeout Analysis

## 1. Instrumentation

FAN_ATPG was extended with an optional per-target-fault wall-clock timeout (`set_per_target_timeout <sec>`, default 0 = disabled). When enabled, the ATPG engine checks elapsed time at each iteration of the main search loop in `generateSinglePatternOnTargetFault()`. If the per-target timeout is exceeded, the fault is marked `TO` (timeout) and the engine moves to the next fault.

Fault statuses are now: DT (detected), AU (untestable), AB (backtrack abort), UD (undetected), **TO (per-target timeout)**. The `TO` count is reported in `report_statistics` and `report_fault`.

The original global 180-second process timeout and 500-backtrack limit remain unchanged.

### Generated FAN script proof

```
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/s27.v
set_nonscan_ff U_G5 U_G6
build_circuit --frame 4
set_fault_type saf
add_fault --all
set_per_target_timeout 0.000001
set_static_compression off
set_dynamic_compression off
run_atpg
report_statistics > rpt/forced_to.rpt
report_fault > rpt/forced_to_faults.txt
exit
```

`set_per_target_timeout` is placed after `build_circuit` and `add_fault`, and before `run_atpg`.

---

## 2. Practical Benchmark Result

All current benchmarks (s27, b07, b13) complete T=4 runs within milliseconds. No run has ever hit the global 180-second process timeout.

| Circuit | Ratio | Flow | Target faults | DT% | AU% | UD% | AB% | TO% | Runtime | Global timeout? |
|---------|------:|------|-------------:|----:|----:|----:|----:|----:|--------:|:--------------:|
| s27 | 67% | T1→T2→T4 residual | 21 | 42.9 | 47.6 | 9.5 | 0 | 0 | 0.01s | No |
| b07 | 20% | T1→T2→T4 residual | 1407 | 1.4 | 93.5 | 5.1 | 0 | 0 | 0.31s | No |
| b07 | 50% | T1→T2→T4 residual | 1510 | 0.6 | 96.4 | 3.0 | 0 | 0 | 0.04s | No |
| b13 | 20% | T1→T2→T4 residual | 1072 | 1.6 | 87.8 | 9.7 | 0.9 | 0 | 0.33s | No |
| b13 | 50% | T1→T2→T4 residual | 1200 | 1.0 | 93.3 | 5.5 | 0.3 | 0 | 0.12s | No |
| b07 | 50% | T4 all-fault | 2598 | 13.7 | 84.4 | 1.8 | 0 | 0 | 0.14s | No |
| b13 | 50% | T4 all-fault | 2300 | 22.5 | 74.5 | 2.9 | 0.1 | 0 | 0.12s | No |

**Interpretation:** In the current benchmark set, T=4 low recovery is not explained by global timeout starvation. The low recovery on b07/b13 is more consistent with AU-dominated residual faults under shallow T=4 expansion. Per-target timeout remains useful as instrumentation and as a safeguard for larger circuits, but the current benchmarks are too fast for meaningful timeout sensitivity.

---

## 3. Forced-Timeout Validation

To verify the instrumentation works end-to-end, we ran a forced-timeout test with `set_per_target_timeout 0.000001` (1 microsecond) on s27 T=4 all-fault mode.

### Results

| Status | Count |
|--------|------:|
| DT | 63 |
| AU | 10 |
| AB | 0 |
| UD | 2 |
| **TO** | **15** |
| Total | 90 |

Report statistics: `fault coverage = 70%`, `TO (timeout) = 15`.

*Note: `report_statistics` counts TO using the engine's internal full (uncollapsed) fault accounting, while `report_fault` emits the collapsed/reportable fault list consumed by the Python parser. The parser-level TO count (11 collapsed vs. 15 full) is the one used for CSV summaries and union coverage analysis.*

Per-fault `report_fault` confirms individual faults marked `TO`:
```
g=0 l=0 SA0  TO  G0 (primary input)
g=3 l=0 SA0  TO  G3 (primary input)
g=4 l=0 SA1  TO  U_G5 (SDFF_X1)
```

Python parser correctly reads `TO` status separate from `AB` and `UD`:
- Parser: DT=41, AU=8, AB=0, UD=2, **TO=11** (collapsed fault count)
- TO not misclassified as AB ✅

### Earlier TO=15 vs Later TO=0 Discrepancy

The earlier forced-timeout test (`TO=15`) used raw FAN_ATPG `add_fault --all` T=4 targeting all 90 faults with 1µs timeout. The later pipeline test (`TO=0`) used `run_progressive_residual.py` which runs T=4 only on the residual fault set R2 (21 faults for s27), and those residual faults complete within the timeout. Both results are correct — the TO count depends on the target fault set and timeout value, not on any implementation bug.

---

## 4. Data Files

| File | Content |
|------|---------|
| `results/t4_timeout_baseline_summary.csv` | T=4 timeout baseline for all benchmark cases |
| `results/progressive_residual_summary.csv` | Full progressive residual results (includes TO columns) |

## Appendix: Forced-Timeout Script

```
# FAN_ATPG/script/fanScripts/forced_to.script
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/s27.v
set_nonscan_ff U_G5 U_G6
build_circuit --frame 4
set_fault_type saf
add_fault --all
set_per_target_timeout 0.000001
set_static_compression off
set_dynamic_compression off
run_atpg
report_statistics > rpt/forced_to.rpt
report_fault > rpt/forced_to_faults.txt
exit
```
