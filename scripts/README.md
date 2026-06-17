# Scripts Index

Map of `scripts/` by role. Nothing here is dead code — the experiment runners
are the active pipeline (re-run by the team) and the prep scripts regenerate the
`FAN_ATPG/mod_netlist/*.v` netlists, which are not committed.

## Experiment runners (the pipeline)
| Script | Role |
|--------|------|
| `run_progressive_residual.py` | Core $T{=}1\to T{=}2\to T{=}4$ residual pipeline for one circuit |
| `run_progressive_residual_sweep.py` | ITC'99 sweep driver (calls the core pipeline) |
| `run_progressive_residual_iscas89_sweep.py` | ISCAS'89 sweep driver |
| `run_controlled_experiments.py` | Drives the 5 controlled ablation experiments (Exp 1–5) |
| `run_flag_ablation.py` | ATPG optimization-flag ablation |
| `run_ablation_all.py` | Convenience driver over all ablation conditions |
| `run_experiment_sweep.py` | Generic experiment sweep |
| `run_remaining_circuits.py` | Re-run circuits left over from a partial sweep |
| `run_fullscan_baseline_iscas89.py` | B2 full-scan ceiling (ISCAS'89) |
| `run_fullscan_oracle.py` | Full-scan oracle diagnostic |

## Netlist prep & synthesis (regenerate `mod_netlist/*.v`)
| Script | Role |
|--------|------|
| `synth_itc99.sh`, `synth_iscas89.sh` | Yosys synthesis to NanGate45 |
| `build_itc99_netlists.sh` | Base-gate pipeline: prep RTL → synth → fixup → validate |
| `prep_itc99_rtl.py` + `itc99_prep_rules.yaml` | RTL preparation rules |
| `fixup_verilog.py` | Tie-cell insertion, floating-net fixes |
| `convert_ttu_to_nangate.py` | ISCAS'89 TTU → NanGate45 SDFFR conversion |
| `gen_base_liberty.py` | Generate the base-gate Liberty library |
| `validate_netlist.py`, `print_netlist_summary.py` | Netlist sanity checks |

## Partial-scan masks (OpenSTA timing)
| Script | Role |
|--------|------|
| `sta_extract_slack.tcl` | OpenSTA min-path-slack extraction |
| `gen_mask_from_slack.py` | Rank FFs by slack → non-scan mask |
| `gen_nonscan_masks.sh` | Batch mask generation (run after re-synthesis) |

## Analysis & figures
| Script | Role |
|--------|------|
| `analyze_residual.py` | Per-fault overlap / residual analysis |
| `classify_residual_faults.py`, `rank_residual_faults.py` | Residual fault classification / ranking |
| `generate_figures.py` | Report figures (fig1–5) from result CSVs |

## Utilities
| Script | Role |
|--------|------|
| `atpg_timeouts.py`, `atpg_timeouts.sh` | Per-target timeout experiments |
| `fan_smoke_load.py` | Quick FAN load/smoke check |
