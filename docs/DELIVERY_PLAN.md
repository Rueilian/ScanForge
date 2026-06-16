# Final-Project Delivery Plan — Clean Artifacts

> Branch `final-swear`. Standard of truth = `docs/final_report.md`. Authors (co-first):
> Yen-Chu Lo, Rueilian Ting, Ssu-Wei Huang. Deliverable = standalone **zip** bundle.
> Data is being re-run by a classmate — we only **flag** data issues (see
> `results/DATA_ISSUES.md`), never fix data ourselves. Git history is the backstop, so
> steps need not be individually reversible.

## Status legend
`[ ]` todo · `[~]` in progress · `[x]` done · `[blocked:data]` waiting on classmate re-run

---

## Phase 0 — Data alignment (FLAG ONLY)
- [x] Audit all `results/*.csv` against report standard → `results/DATA_ISSUES.md`
- [blocked:data] Classmate re-runs: trim exp1/exp2/exp4 to 10 circuits; rebuild
      `progressive_residual_summary.csv` as clean 10-circuit Two-Phase (Exp 2);
      re-run `ablation_no_tp_T2.csv` + `ablation_uniform_limit.csv` on the 10.
- Canonical circuits (10): b03 b04 b05 b07 b08 b09 s953 s1196 s1238 s5378.
  Excluded: b11, s35932 (crash); b13, s9234, s15850 (timeout @600s).

## Phase 1 — Reproducible binaries (independent of data)
- [x] `FAN_ATPG`: clean staged build (archive `libcore.a` → global lib dir → build per-pkg)
      works around the `libcore.a` link-order bug. `bin/opt/fan` produced & runs.
- [x] `src/` (ScanForge): `make -C src` clean → `src/scanforge` produced & runs.
- [x] Engine smoke: `fan` full-scan ATPG on s27 → DT=104, AU=2, FC 92.86% (merged binary OK).
- [ ] **Repro gap:** canonical-circuit netlists `FAN_ATPG/mod_netlist/{b03,b04,...}.v` are NOT
      materialized (removed from VCS in cleanup; only test netlists like `s27_dffr.v` remain).
      Regenerate via `scripts/synth_itc99.sh` / `synth_iscas89.sh` (Yosys+OpenSTA) before a full
      pipeline run or the zip. Full progressive-residual smoke (b03) blocked until netlists exist.
- Note: README's `cd FAN_ATPG && make -j` is unreliable (the link-order race); document the
  staged build in REPRODUCE.md.

## Phase 2 — IEEE-format LaTeX paper (keep `final_report.md` as-is)
- [x] `paper/`: IEEEtran `conference`; compiler = `tectonic` (auto-fetches IEEEtran). PDF builds.
- [x] Full conversion `docs/final_report.md` → `paper/main.tex` (title, 3 co-first authors
      Lo/Ting/Huang, abstract, keywords, §1–§11 + 2 appendices, all tables via `booktabs`,
      figs 1–5, 16-entry `thebibliography`). Output: 7-page `paper/main.pdf`.
- [x] Build clean (only minor under/overfull hbox warnings; one 3.47pt overfull in §Related Work).
- [blocked:data] Final numeric proofread of tables/figures once canonical data lands
      (numbers currently mirror `final_report.md`, the standard).

## Phase 3 — Code cleanup (refactor allowed; git backstop)
- [x] Merge already removed the big cruft (archive/, FAN_ATPG build artifacts, stale data).
      All noisy dirs (`logs/`, `results/{experiments,fault_status,logs,residual_faults}`,
      `__pycache__`, `scripts/docs`) are untracked & gitignored — repo tree is clean.
- [x] Tightened `.gitignore` (`results/logs/`, `scripts/docs/`, `dist/`, `*.bak`, paper TeX aux).
- [x] Added `scripts/README.md` — index of all scripts by role (runners / netlist prep /
      masks / analysis / utils). No script moved: every `run_*.py` + prep script is referenced
      by the report or README and is actively used by the team re-running data.
- [x] Updated top-level `README.md`: reliable FAN_ATPG staged build (libcore.a workaround) +
      new "Reports, Paper & Slides" section (paper/slides/figures/data-status pointers).
- [x] Verified `backup_divider.tex` is `\input` (kept); slides intentionally track built PDFs.
- Deferred (do NOT do mid re-run): physically reorg `scripts/` into `legacy/` and split
  `results/` into canonical vs raw — would break the classmate's active pipeline paths.

## Phase 4 — Zip packaging
- [ ] `REPRODUCE.md`: (1) build fan+scanforge; (2) regenerate figures; (3) build paper + slides.
- [ ] Assemble `dist/ScanForge_final/`: `paper/main.pdf` + `paper/` sources; `slides/main.pdf`
      (+ light); `docs/final_report.md` + `docs/figures/`; `results/` (canonical + needed raw);
      `src/` + `FAN_ATPG/` sources (exclude build artifacts + `.git`); `README.md` + `REPRODUCE.md`.
- [ ] Produce `ScanForge_final_20260617.zip` (exclude `.git`, `*.o`, binaries, `__pycache__`, TeX aux).
- [ ] Acceptance: unzip to clean dir, follow `REPRODUCE.md`, confirm from-scratch build + PDF.

## Phase 5 — Version control
- [ ] Staged commits (data-flag / paper / cleanup / packaging) on `final-swear`; push.
- [ ] Optional tag `final-submission-20260617`.
