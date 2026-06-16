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
- [ ] `FAN_ATPG`: `make clean && make`; work around the `libcore.a` link-order bug
      (archive `libcore.a` into the global lib dir, then build `fan`). Produce `bin/opt/fan`.
- [ ] `src/` (ScanForge): clean build → `src/scanforge`.
- [ ] End-to-end smoke on s27 / b03 (partial-scan → progressive-residual) to prove pipeline.

## Phase 2 — IEEE-format LaTeX paper (keep `final_report.md` as-is)
- [ ] `paper/`: vendor `IEEEtran.cls` (+ `IEEEtran.bst`); compiler = `tectonic`
      (`~/.local/bin/tectonic`, auto-fetches packages) else `pdflatex`.
- [ ] Convert `docs/final_report.md` → `paper/main.tex` (IEEEtran `conference`, two-column):
      title + 3 co-first authors, abstract, index terms, §1–§11 + Appendix, tables via
      `booktabs`, figures `docs/figures/fig1–5.png` (`figure*` for wide), references → `refs.bib`.
- [ ] Build `paper/main.pdf`; check overfull boxes, float placement, citation numbering.
- [blocked:data] Final numeric proofread of tables/figures once canonical data lands.

## Phase 3 — Code cleanup (refactor allowed; git backstop)
- [ ] Remove stale/untracked: `logs/`, `results/{experiments,fault_status,logs,residual_faults}`,
      `scripts/__pycache__`, `scripts/docs`, build artifacts (`src/*.o`, `src/scanforge`,
      `slides/*.aux|log|nav|out|snm|toc`); tighten `.gitignore`.
- [ ] `scripts/`: identify orphan/duplicate `run_*.py`; keep canonical pipeline, move rest to
      `scripts/legacy/`; add one-line purpose header to each kept script.
- [ ] `results/`: separate canonical vs raw/appendix (e.g. `results/raw/`).
- [ ] Update top-level `README.md`: build (incl. libcore.a workaround), reproduce, figures, paper.
- [ ] Cross-check doc/script file references still resolve after cleanup.

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
