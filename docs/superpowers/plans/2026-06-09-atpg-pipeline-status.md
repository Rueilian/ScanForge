# ATPG Pipeline Status (2026-06-09)

> **最新（netlist pipeline）：** 實作中 — [`2026-06-09-primitive-netlist-pipeline-complete.md`](./2026-06-09-primitive-netlist-pipeline-complete.md)（base-gate synth + MUX2 保留 + revert OAI/AOI atomic）。  
> **Phase D + scan-protocol：** b03 **FC_scan ≈ 93%**；b07 **≈ 94%**。主指標見 [`2026-06-09-scan-protocol-fc-metric.md`](./2026-06-09-scan-protocol-fc-metric.md)。  
> **歷史（Phase C）：** G2 **FAIL** → 觸發 Phase D。見 [`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)。

---

## Phase D + Scan-Protocol 結果摘要（2026-06-09）

| 項目 | 狀態 |
|------|------|
| PODEM 修復（MUX2 原子 Gate::MUX） | ✅ b03 FC_raw 34% → **~93%** |
| Compound OAI/AOI 原子（D3.2/D3.3） | ⏳ 過渡期；pipeline 完成後 **revert**，改靠 base-gate synth |
| Base-gate netlist pipeline | ✅ `build_itc99_netlists.sh`；11/11 validate PASS；OAI/AOI=0 |
| FAN D3.2/D3.3 revert | ✅ 僅保留 Gate::MUX；b03 FC_scan ~90.5%（base-gate） |
| Scan-protocol 主指標 | ✅ 自動（`add_fault --all`）+ `b03_reset_tie.v` |
| Regression | ✅ `phase_d_test`、`test_phase_d_atpg.sh` PASS |
| 40-run sweep (Tier A) | ✅ `scripts/run_phase_d_fullscan_dataset.sh`（8 ITC × 5 ratios） |
| Tier B (b12/b14/b15) | ⏸ deferred — see `2026-06-10-saf-atpg-speed-improvement.md` |

| 電路 | FC_scan（主） | FC_raw（附錄） | AU_comb | 備註 |
|------|--------------|---------------|---------|------|
| b03 | **93.03%** | 92.83% | 2 | `b03.v`（auto scan protocol） |
| b04 | **94.62%** | — | 25 | base-gate pipeline |
| b05 | **93.72%** | — | — | base-gate pipeline |
| b07 | **92.98%** | — | 52 | base-gate pipeline |
| b08 | **95.47%** | — | 1 | base-gate pipeline |
| b11 | **97.80%** | — | 40 | base-gate pipeline |
| b03_reset_tie | 92.97% | 92.97% | 2 | Level 3 netlist |
| s510 | 99.14% | 99.14% | 0 | 無 async PI |
| tiny_sdffr | 91.67% | 91.67% | 0 | regression |

**標準 script：** `add_fault --all` → `run_atpg` → `report_statistics`（首行 FC_scan；async PI 自動 TI）。

---

## Phase C 結果摘要（歷史）

### C1：PO/PPO 觀測修復（`atpg.cpp`）

**根因：** `checkIfFaultHasPropagatedToPO` 從 gate array 尾端索引，scan pseudo gates（CK/test_si/test_se）遮蓋真實 PO/PPO。

| 電路 | FC（修復前→後） | AU（前→後） |
|------|----------------|------------|
| tiny_sdffr | 58.3% → **91.7%** | 8 → **0** |
| s510 | 94.9% → **99.1%** | 60 → **0** |
| b03 | 34.2% → **34.8%** | 957 → 948 |

### C2：RN / reset tie-high

| 實驗 | FC | 結論 |
|------|-----|------|
| b03_reset_tie.v | 33.96% | 無改善 |
| b03_rn_tie.v (per-FF RN) | parse fail | reset INV 浮空 |

### C3：外部對照

- DVCON Modus b03：**882 faults PASS**（商業 full-scan）
- FAN b03：**34.75% FC** → 差距為 **FAN engine on MUX2-heavy FSM**，非 ITC'99 天生限制
- 報告：`FAN_ATPG/rpt/b03_external_atpg_comparison.md`

### G2 決策（當時）

**FAIL** — 觸發 Phase D（見上）。**不再**宣稱 b03 full-scan 天花板 ~35%。

---

## 測試

```bash
# Phase D（現行）
cd FAN_ATPG && ./pkg/core/bin/opt/phase_d_test .
bash scripts/test_phase_d_atpg.sh

# Phase C（歷史 regression，仍須 PASS）
cd FAN_ATPG && ./pkg/core/bin/opt/phase_c_test .
bash scripts/test_phase_c_atpg.sh
```

---

## 關鍵檔案

| 用途 | 路徑 |
|------|------|
| **Netlist pipeline（主計劃）** | `docs/superpowers/plans/2026-06-09-primitive-netlist-pipeline-complete.md` |
| Scan-protocol 定義 | `docs/superpowers/plans/2026-06-09-scan-protocol-fc-metric.md` |
| Phase D 計劃 | `docs/superpowers/plans/2026-06-09-phase-d-podem-fix.md` |
| Netlist 驗證 | `scripts/validate_netlist.py`（待實作） |
| 一鍵建置 | `scripts/build_itc99_netlists.sh`（待實作） |
| `set_scan_protocol` / auto TI | `FAN_ATPG/pkg/core/src/scan_protocol.cpp` |
| 主 dataset CSV | `results/phase_d_fullscan_dataset.csv` |
| Raw 附錄 CSV | `results/appendix_phase_d_fullscan_raw.csv` |
| C1 修復 | `FAN_ATPG/pkg/core/src/atpg.cpp` |
| C++ test | `FAN_ATPG/pkg/core/src/phase_d_test.cpp` |
| 外部對照 | `FAN_ATPG/rpt/b03_external_atpg_comparison.md` |
| 調查報告 | `FAN_ATPG/rpt/b03_investigation_2026-06-09.md` |

---

## ITC FC_scan（base-gate pipeline，2026-06-10）

| 電路 | FC_scan | 狀態 |
|------|---------|------|
| b03 | 90.59% | OK |
| b04 | 94.62% | OK |
| b05 | 95.47% | OK |
| b07 | 92.98% | OK |
| b08 | 95.47% | OK |
| b09 | 94.58% | OK |
| b11 | 97.80% | OK |
| b12 | — | **deferred** — MUX `fanoutFreeBacktrace` crash / 40+ min |
| b13 | 91.54% | OK |
| b14 | — | **deferred** — segfault or > 10 min |
| b15 | — | **deferred** — hours-scale |

## 下一步

1. **SAF speed plan S1–S3** — [`2026-06-10-saf-atpg-speed-improvement.md`](./2026-06-10-saf-atpg-speed-improvement.md)
2. **40-run partial-scan sweep** — Tier A only (`ITC_ACTIVE`)
3. 論文正文用 FC_scan（8 ITC）；Tier B / b17+ 放 limitations
