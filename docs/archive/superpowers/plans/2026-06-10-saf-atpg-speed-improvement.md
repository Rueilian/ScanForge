# SAF ATPG Speed Improvement Plan (2026-06-10)

> **Context:** 8/11 ITC circuits complete full-scan SAF in **< 2 s** (FC_scan 90–98%).
> **b12 / b14 / b15** are deferred from sweeps: b12 segfaults or runs 40+ min;
> b14/b15 scale to hours. **b17+** and mega-ISCAS are out of project scope.
>
> **Scope policy:** [`scripts/itc99_benchmark_scope.sh`](../../../scripts/itc99_benchmark_scope.sh)

---

## 1. Problem Statement

| Tier | Circuits | SDFFR | Observed full-scan SAF | Root issue |
|------|----------|------:|------------------------|------------|
| A (OK) | b03–b11, b13 | 29–88 | 0.002–1.7 s | — |
| B (deferred) | b12, b14, b15 | 220–837 | timeout / segfault | engine + MUX topology |
| C (out) | b17, b18, b20–b22 | 1000+ | not built | project scope limit |

FAN supports **SAF** and **TDF**; ScanForge runs **SAF only** (`set_fault_type saf`, `--frame 1`).

Slowness is **not** inherent to full-scan SAF on small/medium ITC. It concentrates on:

1. **MUX-heavy base-gate netlists** — Yosys keeps MUX2; FAN PODEM backtrace had incomplete MUX paths (`fanoutFreeBacktrace` segfault on b12; partial fix landed 2026-06-10).
2. **Single-threaded academic ATPG** — no parallel fault scheduling; one hard fault can monopolize CPU.
3. **`set_per_target_timeout 120`** — each stubborn target can burn up to 120 s before `TO`; amplifies wall time on Tier B.
4. **High `BACKTRACK_LIMIT` (5000)** — pathological faults backtrack extensively before `AB`.
5. **No fault ordering / learning** — hard faults interleaved with easy ones; no conflict cache across targets.

---

## 2. Goals

| Goal | Target |
|------|--------|
| Tier A sweep latency | Keep **< 5 s** per circuit full-scan |
| Tier B re-entry | b12 full-scan **< 10 min** wall, no crash, FC_scan reported |
| Partial-scan 55-run sweep | **8 circuits × 5 ratios = 40 runs** complete overnight |
| Correctness | `phase_d_test`, `test_phase_d_atpg.sh` stay PASS; FC_scan within ±1% of pre-fix Tier A |

**Non-goals (this phase):** TDF ATPG, multi-thread commercial ATPG replacement, b17+ netlists.

---

## 3. Improvement Roadmap

### Phase S0 — Scope & ops (immediate, **done in docs/scripts**)

- [x] Define `ITC_ACTIVE` / `ITC_DEFERRED` / `ITC_OUT_OF_SCOPE` in `itc99_benchmark_scope.sh`
- [x] ATPG sweeps default to **Tier A only** (8 circuits)
- [x] Document deferred circuits in `spec.md`, `AGENTS.md`, `final_report.md`
- [ ] Kill stray FAN processes before sweeps; log wall time per circuit

### Phase S1 — Quick wins (config, 0–1 day)

**No engine change; unblock Tier A productivity.**

| Action | Rationale | Expected gain |
|--------|-----------|---------------|
| **Per-target timeout = 0 for Tier A** (new default) | 8 active ITC finish in ms–s; 120 s/fault was blowing up Tier B | No artificial 120 s × N stall |
| **Per-target timeout = 30 s for Tier B only** | Cap stubborn faults without hour-scale grind | Bounded diagnostic runs |
| **Tiered wall timeout** | A: 300 s, B: 3600 s | Fail fast on regressions |
| **Default sweep = `ITC_ACTIVE` only** | 40 runs not 55 | ~27% fewer runs |
| **Pre-sweep `pkill` guard** | Zombie FAN ate CPU for days | Restores full single-core throughput |

```bash
# Tier A (default)
bash scripts/run_phase_d_fullscan_dataset.sh

# Tier B diagnostic
ITC_INCLUDE_DEFERRED=1 ATPG_PER_TARGET_TIMEOUT=30 bash scripts/run_phase_d_fullscan_dataset.sh
```

**Acceptance:** Tier A sweep **< 2 min** total.

### Phase S2 — MUX / backtrace correctness (1–3 days)

**Complete Phase D MUX coverage in all ATPG paths.**

| Task | File | Status |
|------|------|--------|
| `fanoutFreeBacktrace` MUX2 branch | `atpg.cpp` | ✅ landed 2026-06-10 |
| `multipleBacktrace` MUX2 (`assignBacktraceValue`, `findEasiestInput`, propagate) | `atpg.cpp` | ✅ landed 2026-06-10 |
| Audit `findFinalObjective`, `uniqueSensitization` for MUX | `atpg.cpp` | TODO |
| NULL / `firstTimeFrameHeadLine_` guards in generic backtrace | `atpg.cpp` | partial |
| Regression: b12 `add_fault` + 60 s ATPG smoke (no segfault) | `test_phase_d_atpg.sh` | TODO |

**Acceptance:** b12 runs **≥ 60 s without SIGSEGV**; report written or clean `AB`/`TO` exit.

### Phase S3 — Engine heuristics (3–7 days)

**Reduce per-fault search cost without changing fault model.**

| Idea | Implementation sketch | Risk |
|------|----------------------|------|
| **Easier faults first** | Sort collapsed FU by level / fanout before `StuckAtFaultATPG` | Low |
| **Static implication learning** | Cache `{gate,val} → conflict` across targets | Medium |
| **Lower `BACKTRACK_LIMIT` for full-scan** | e.g. 500 for `--frame 1`, keep 5000 for T=8 partial-scan | Low–med |
| **Early AU on blocked PPI/TI** | Skip targets already scan-unobservable | Low |
| **Optional `abc` resynth** | `opt -fast` / fewer MUX2 in synth (FC tradeoff) | Netlist change |

**Acceptance:** b12 full-scan **< 10 min**, FC_scan within 5% of best-known; Tier A runtime unchanged.

### Phase S4 — Parallel ATPG (**landed 2026-06-10**)

Fault-partition multi-thread pattern generation in FAN core:

| Feature | Implementation |
|---------|----------------|
| Command | `set_atpg_threads N` (`0` = `hardware_concurrency`) |
| Env (sweeps) | `ATPG_THREADS=4 bash scripts/run_phase_d_fullscan_dataset.sh` |
| Model | Round-robin partition after **easy-first sort**; per-worker `Circuit` copy + `Atpg`; global mutex fault-drop (CI) |
| Default | `1` (sequential, regression-safe) |
| Heuristic | `sortFaultListEasyFirst` — lower gate level first (always on, seq + par) |

**Not yet:** ripple compaction across workers, fan-in-cone ordering, deterministic pattern order across runs.

### Phase S5 — Further structural speedups (optional)

| Idea | Notes |
|------|-------|
| **Fan-in-cone fault ordering** | Replace round-robin with FIC buckets |
| **Two-phase ATPG** | Fast pass + residual retry |
| **Implication cache** | Cross-target learning |
| **Profile-guided hot paths** | `perf record` on b12 |

---

## 4. Measurement Protocol

Every engine change must record:

```bash
# Tier A regression (fast)
bash scripts/run_phase_d_fullscan_dataset.sh   # ITC_ACTIVE only

# Tier B diagnostic (manual)
ITC_INCLUDE_DEFERRED=1 ATPG_PER_TARGET_TIMEOUT=0 \
  bash scripts/run_phase_d_fullscan_dataset.sh

# Engine unit tests
cd FAN_ATPG && make -j$(nproc) && \
  bash ../scripts/test_phase_d_atpg.sh
```

Log to `results/atpg_speed_log.csv`:

```
date,circuit,tier,fc_scan,wall_s,per_target_timeout,git_sha,notes
```

---

## 5. Benchmark Scope (authoritative)

### Tier A — Active (8 circuits)

`b03 b04 b05 b07 b08 b09 b11 b13`

- Full-scan FC_scan: **90.6% – 97.8%** (2026-06-10, base-gate netlists)
- Used for: full-scan baseline, partial-scan 40-run sweep, paper tables

### Tier B — Deferred (3 circuits)

`b12 b14 b15`

- Netlist: built + `validate_netlist.py` PASS
- ATPG: excluded until Phase S2/S3 acceptance
- Known issues:
  - **b12:** `fanoutFreeBacktrace` MUX segfault (partial fix); else 40+ min grind
  - **b14:** segfault or > 10 min
  - **b15:** 837 FF, 12k gates — hours

### Tier C — Out of scope

`b17 b18 b20 b21 b22` and mega-ISCAS (`s35932`, `s38417`, `s38584`)

- Not synthesized in current pipeline
- Document as future work / engine maturity prerequisite

---

## 6. Documentation Updates

| File | Change |
|------|--------|
| `docs/spec.md` §5 | Tier A/B/C; 40-run sweep |
| `docs/AGENTS.md` | Scope + speed plan link |
| `docs/final_report.md` | Limitations + deferred table |
| `docs/checklist.md` | New § SAF speed / scope |
| `scripts/itc99_benchmark_scope.sh` | Single source of truth |
| `scripts/run_phase_d_fullscan_dataset.sh` | Source scope |
| `scripts/run_atpg_sweep.py` | Default `ITC_ACTIVE` |

---

## 7. Engine Parallelism & SIMD Audit (2026-06-10)

### What FAN has today

| Layer | Parallel? | Mechanism | Notes |
|-------|-----------|-----------|-------|
| **ATPG generation** (PODEM/backtrace) | ❌ No | Single target fault, single thread | Main bottleneck on b12+ |
| **Fault simulation** | ✅ Bit-parallel | `ParallelValue = unsigned long` (64-bit word) | Up to **64 faults/patterns per word**, not multi-core |
| **Pattern simulation** | ✅ Bit-parallel | Same `ParallelValue` packing | `parallelPattern*` APIs |
| **Multi-core / OpenMP** | ❌ None | — | `Makefile` has no `-fopenmp` |
| **SIMD (AVX/SSE)** | ❌ None | Plain `& \| ^` on `unsigned long` | Compiler may vectorize marginally; no explicit intrinsics |
| **GPU** | ❌ None | — | — |

Key code: `logic.h` defines `WORD_SIZE = 64` on x86-64; `simulator.h` runs `parallelFaultFaultSimWithOnePattern` after each pattern to drop detected faults in bulk.

**Implication:** FAN's "parallel" is **1970s–90s bit-parallel fault simulation** (concurrent fault simulation), not modern multi-threaded ATPG. Pattern generation remains **O(hard_faults × backtracks)** on one core.

### SAF ATPG best practices vs FAN

| Best practice (commercial / literature) | FAN today | Gap / action |
|----------------------------------------|-----------|--------------|
| **Fault collapsing** | ✅ On extract | Keep |
| **Fault ordering** (easy-first or fan-in-cone) | ❌ FIFO list order | **S3:** sort by level / fanout / control inputs |
| **Abort / backtrack limit** per fault | ✅ `BACKTRACK_LIMIT=5000` + optional `set_per_target_timeout` | Tune: 500 for T=1, 5000 for T=8; default per-target **0** (Tier A), **30 s** (Tier B) |
| **Bit-parallel fault simulation** | ✅ `parallelFaultFaultSim*` | Already used post-pattern |
| **Dynamic compaction** | ✅ `set_dynamic_compression on` | Keep |
| **Static compaction** | ✅ `set_static_compression on` | Keep |
| **Static / dynamic learning** (implications) | ❌ Not implemented | **S3:** implication cache |
| **Recursive / conflict-driven learning** | ❌ | Optional S4 |
| **Multi-core ATPG** (fault partitions) | ❌ | S4: partition collapsed FU across threads |
| **MUX / complex gate handling in backtrace** | ⚠️ Partial (Phase D) | **S2 priority** |
| **Two-pass flow** (fast → residual) | ❌ | S3: abort-low then retry-hard |
| **Scan protocol / TI exclusion** | ✅ Auto on `add_fault --all` | Keep |

Commercial tools (TetraMAX, Modus) additionally use: multiple ATPG engines (basic vs fast sequential), capture-cycle tuning, test points, and distributed farm runs — out of scope for academic FAN but explains the 100× gap on b15.

### Engine improvement priority (user-aligned)

1. **S2 — MUX correctness** in all backtrace / implication paths (blocks Tier B)
2. **S3 — Heuristics** (fault order, lower backtrack for T=1, implication cache)
3. **S4 — Structural** (multi-core fault batches, profiling hot loops)
4. **Not near-term:** explicit AVX-512 fault sim — only worth it after algorithm path is fixed

---

## 8. Decision Log

| Date | Decision |
|------|----------|
| 2026-06-10 | Defer b12/b14/b15 from ATPG sweeps; active set = 8 ITC |
| 2026-06-10 | b17+ explicitly out of scope for this project phase |
| 2026-06-10 | SAF only; TDF not on roadmap |
| 2026-06-10 | `fanoutFreeBacktrace` MUX fix — first S2 deliverable |
| 2026-06-14 | Tier B pilot: b12/b14 progressive @20% PASS (16–28 min); b15 T=1 TIMEOUT @2h; requires clean FAN rebuild |

---

## Related

- [`2026-06-09-atpg-pipeline-status.md`](./2026-06-09-atpg-pipeline-status.md)
- [`2026-06-09-primitive-netlist-pipeline-complete.md`](./2026-06-09-primitive-netlist-pipeline-complete.md)
- [`docs/t4_timeout_analysis.md`](../../t4_timeout_analysis.md)
