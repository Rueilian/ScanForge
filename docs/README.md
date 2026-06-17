# ScanForge Documentation

## Active (authoritative)

| Document | Purpose |
|----------|---------|
| [`spec.md`](spec.md) | Project definition, RQs, two-baseline method |
| [`final_report.md`](final_report.md) | Course report + Tier A @ **10%** results |
| [`figures/`](figures/) | Report charts (`generate_figures.py`) |
| [`../AGENTS.md`](../AGENTS.md) | Agent rules — **read first** |

**Partial-scan ratio:** **10% only** (`ratio=0.10`, `masks/<circuit>_x10.mask`).

## Three-way comparison (B1 → Experiment → B2)

| Role | Metric | File |
|------|--------|------|
| **B1** — partial-scan T=1 | `FC_T1` | `results/progressive_residual_summary.csv` |
| **Experiment** — T=1→T=2→T=4 | `FC_T1_T2_T4` | same |
| **B2** — full-scan | `FC_scan_coll` | `results/phase_d_fullscan_dataset.csv` |

| Derived | Formula |
|---------|---------|
| Exp−B1 | `total_gain_pp` |
| B2−Exp | `remaining_gap_pp` |
| B2−B1 | `partialscan_gap_pp` |

Results tables must include **all three coverage columns** in this order.

## Evaluation protocol

```bash
# All 15 circuits, no per-target timeout:
python3 scripts/run_ablation_all.py

# Full-scan baselines (B2):
python3 scripts/run_fullscan_baseline_iscas89.py

python3 scripts/generate_figures.py
```

## Archived (do not use for active work)

Historical multi-ratio material lives under `*/archive/` (see [`.cursorignore`](../.cursorignore)). Agents must not grep or cite archive paths unless the user explicitly asks.
