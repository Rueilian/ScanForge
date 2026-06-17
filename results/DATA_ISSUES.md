# Data Issues — Audit Against `docs/final_report.md` (Standard)

> **STATUS 2026-06-17 — RESOLVED.** After merging `origin/submit` (final re-run with
> memory columns), `exp1–5.csv` are clean 10-circuit sets. The new run changed b05/b08
> (now T1≈90%, gain 0; old data had b05=29.2→87.68). Per decision *"new data is
> authoritative, full recompute"*, all averages, the §7 tables, the abstract/discussion/
> conclusion of `docs/final_report.md` and `paper/main.tex`, and figures fig1–5 were
> recomputed from the new data. `generate_figures.py` now reads `exp2_two_phase.csv`
> (10 circuits) with B2 from the full-scan data files. The notes below are the original
> audit, kept for history.

---


> **Standard of truth:** `docs/final_report.md`. The report's numbers and narrative are
> canonical; CSV/figure data must be regenerated to match it (not the other way around).
> This file marks every place the committed data disagrees with the report, for the
> classmate re-running experiments. Audited 2026-06-17 against report §6–§8.

## Canonical circuit set (report §6.3, §7)
**10 circuits complete all 5 experiments:**
`b03, b04, b05, b07, b08, b09, s953, s1196, s1238, s5378`

**Excluded (must NOT appear in the 10-circuit tables/figures):**
`b11` (runner crash), `s35932` (runner crash), `b13`, `s9234`, `s15850` (timeout @600s).

Legend: ✅ matches report · ⚠️ values OK but contaminated (dedupe/trim) · 🔴 wrong data, must re-run/regenerate

---

## Per-file status

| File | Status | Problem | Expected (per report) |
|------|--------|---------|-----------------------|
| `exp3_uniform_T1.csv` | ✅ | exactly 10 circuits, FC values match §7.3 Exp 3 | keep |
| `exp5_static_learning.csv` | ✅ | exactly 10 circuits, FC values match §7.3 Exp 5 | keep |
| `exp1_baseline.csv` | ⚠️ | 13 rows — 10 canonical + **extra excluded `b13, s15850, b11`**. Values for the 10 match §7.2. | drop the 3 excluded rows → 10 rows |
| `exp2_two_phase.csv` | ⚠️ | 16 rows — **duplicate rows for `b13, s9234, s15850` (each ×2)** + those 3 are excluded anyway. Values for the 10 match §7.3 Exp 2. | dedupe + drop excluded → 10 rows |
| `exp4_enhanced_backtrace.csv` | ⚠️ | 11 rows — 10 canonical + **extra `s9234`**. Verify the 10 FC values vs §7.3 Exp 4 (note: Exp 4 T1 FC legitimately differs, e.g. b03 41.66%). | drop `s9234` → 10 rows; confirm values |
| **`progressive_residual_summary.csv`** | 🔴 | **THIS FEEDS THE FIGURES** (`scripts/generate_figures.py`). 15 rows / 9 circuits. **Missing 4 canonical circuits: `s953, s1196, s1238, s5378`.** **Contains excluded `s9234, s15850, b11`.** Two concatenated blocks (b03–b09 appear twice) with *different* values and **no column distinguishing the condition**. | Regenerate as the **Two-Phase ON pipeline (Exp 2) on exactly the 10 canonical circuits**. The correct 10-circuit values already exist in `exp2_two_phase.csv` — the figure source should equal that, deduped/trimmed to 10. |
| `ablation_no_tp_T2.csv` | 🔴 | Same broken 9-circuit set as above (b03–b09 dup + `s9234, s15850, b11`). Missing the 4 small ISCAS. | Re-run "Two-Phase OFF at T=2" ablation on the 10 canonical circuits (supports §8.1 "T=2 recovers 7.07pp avg with TP OFF"). |
| `ablation_uniform_limit.csv` | ⚠️ | 8 circuits incl. excluded `s9234, s15850`; missing `s953, s1196, s1238, s5378`. | Align to 10 canonical circuits (supports §8.2 backtrack-limit discussion). |
| `progressive_residual_summary_two_phase.csv` | ℹ️ | Legacy: 8 ITC circuits × 4 ratios, no ISCAS. Not referenced by report §7. | Confirm unused; move to `results/raw/` or delete. |
| `phase_d_fullscan_dataset.csv` (ITC B2) | ✅ | contains b03–b09 full-scan `fc_scan` | source for §7.1 B2 (ITC) |
| `iscas89_fullscan_baseline.csv` (ISCAS B2) | ✅ | contains s953/s1196/s1238/s5378 `FC_fullscan_pct` | source for §7.1 B2 (ISCAS) — all 10 B2 values available |

---

## Highest-priority fix (blocks figures)
🔴 **`progressive_residual_summary.csv`** is the only input to `scripts/generate_figures.py`,
yet it omits 4 of the 10 report circuits and includes 3 excluded ones. **Every figure
(fig1–fig5) is currently inconsistent with the report.** Until this file is the clean
10-circuit Two-Phase (Exp 2) dataset, regenerated figures will not match §7.

## Secondary
- `scripts/generate_figures.py` docstring says **"(17 circuits)"** — should be 10. Either
  trim the input to 10 or have the script filter to the canonical set.
- Minor report-internal inconsistency: b05 T1 FC is **29.10%** in §7.1/§7.2 but **29.20%**
  in §7.3 (Exp 2/3/5). Pick one when re-running (different runs produced 29.1 vs 29.2).

## Definition of done (data)
1. Each of `exp1`,`exp2`,`exp4` trimmed/deduped to exactly the 10 canonical circuits.
2. `progressive_residual_summary.csv` = clean 10-circuit Two-Phase (Exp 2) dataset.
3. `ablation_no_tp_T2.csv` + `ablation_uniform_limit.csv` re-run on the 10.
4. `generate_figures.py` produces fig1–5 whose numbers match report §7 tables.
5. Full-scan B2 already complete — no action.
