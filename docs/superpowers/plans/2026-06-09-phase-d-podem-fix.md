# Phase D：FAN PODEM 放寬修復計劃（2026-06-09）

> **前置：** Phase C 完成（PO/PPO 觀測修復）；b03 FC 仍 ~35%（948 AU）。
> **目標：** 不大改 PODEM 架構，透過局部放寬與 MUX2 建模，把 b03 full-scan FC 拉到可辯護水準（≥ 80%），對齊商用 ATPG 行為。
> **關聯：** [`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)
>
> **2026-06-09 遷移註記（base-gate pipeline）：**
> - **保留 D1** `Gate::MUX` + D3.1 MUX implication（MUX2 為 base gate，永久保留）
> - **Revert D3.2/D3.3** OAI/AOI atomic gates — 改由 [`2026-06-09-primitive-netlist-pipeline-complete.md`](./2026-06-09-primitive-netlist-pipeline-complete.md) 的 base.lib 合成展開 OAI/AOI
> - D3.2/D3.3 實作仍有效至 pipeline 驗收完成；revert 後 b03/b07 FC_scan 回歸門檻不變（≥93%）

---

## 一、問題陳述

| 現象 | 根因 |
|------|------|
| 10/10 PI fault 全 AU | `initializeForSinglePatternGeneration` init unique path 失敗 → 直接 `return NULL` |
| 354 MUX2 AU（71.5%） | MDT 拆成 AND/OR/INV，無 `Gate::MUX` implication |
| Test coverage 89.7% on non-AU | PODEM 對 reachable fault 有效；AU 分類過寬 |
| 商用 b03 ~99% FC | FAN 演算法過早放棄，非 netlist 不可測 |

---

## 二、修復項目（按實作順序）

### D1 — MUX2_X1 原子 Gate::MUX（P4）✅ 已實作

**檔案：** `FAN_ATPG/pkg/core/src/circuit.cpp` + `circuit.h`

**改動：**
1. `calculateNumGate`：MUX2_X1/X2 只分配 1 gate
2. `createCircuitComb`：呼叫 `createCircuitMux2`（A,B,S → MUX）
3. `createCircuitPmt` / `createCircuitPO` / `createCircuitPPO`：MUX2 輸出 fanin 不加重 primitive offset

**Gate D1：** b03 `Gate::MUX` 數量 = 33；FC **75.39%**（fan CLI）/ **80.14%**（phase_d_test）；AU **189** / **113**（原 948）

**實測（2026-06-09）：** MUX2 原子建模為 Phase D 主要收益；**G2' 在 C++ regression 達標（≥80%）**。

---

### D2 — BACKTRACK_LIMIT 提高（P6）✅ 已實作

**檔案：** `pkg/core/src/atpg.h`、`include/core/atpg.h`

**改動：** `500` → `5000`

---

### D3 — PI PODEM 放寬（P1/P2）⏸ 延後

**原計劃：** init unique path 失敗不 AU；PI 跳過 `setFreeLineFaultyGate`。

**實測：** 實作後 `tiny_sdffr` 從 91.7% 跌至 75%（AU 4）；`request1` 單 fault 仍 AU 或長時間 backtrack。

**決策：** Phase D 先交付 **D1+D2**；PI 放寬需更窄條件（例如僅 reconvergent MUX 扇入錐）另開 D3.1。

---

### D3.1 — AU 削減（2026-06-09 進行中）✅ 部分完成

**檔案：** `FAN_ATPG/pkg/core/src/atpg.cpp`

| Patch | 說明 | 效果 |
|-------|------|------|
| **D3.1a** | `initializePiDirectActivation`：PI 直達 D-frontier（跳過 `setFreeLineFaultyGate`） | `request1/4` 在 compression 下由 AU→DT；`reset` 仍 AU |
| **D3.1b** | `xPathTracing` 改為結構性 PO/PPO 可達（移除 `atpgVal==X` 前提） | 無顯著變化（D-frontier 已非主瓶頸） |
| **D3.1c** | init `UNIQUE_PATH_SENSITIZE_FAIL` → `FORWARD`（非 PI 亦進主迴圈） | 減少 init 早退 AU |
| **D3.1d** | `setFaultyGate` 新增 `Gate::MUX` 輸入 fault 激活（A/B/S 三路） | MUX AU 大幅下降 |
| **D3.1e** | `doUniquePathSensitization` MUX 專用：S 非 AND-control；依 select 跳過 don't-care 腳 | MUX unique path 不再誤判 |
| **D3.1f** | 主迴圈 single D-frontier `UNIQUE_PATH_SENSITIZE_FAIL` → `findFinalObjective` fallback | 小幅 FC/AU 改善 |

**b03 實測（compression on，2026-06-09）：**

| 指標 | Phase D 基線 | D3.1 後 |
|------|-------------|---------|
| FC（collapsed） | 80.14% | **81.50%** |
| AU（collapsed，`phase_d_test`） | 113 | **101** |
| AU（full，`fan` stats） | 189 | **175** |
| DT | 706 | **718** |
| PI AU（collapsed） | 4 | **2**（僅 `reset`） |
| MUX AU（collapsed） | 52 | **~30** |
| SDFFR AU（collapsed） | 7 | **0** |

**Regression：** `tiny_sdffr` 91.67% AU=0；`s510_fs_quick` 99.14% AU=0。

**仍待處理（D3.2 後）：** 僅 **4 collapsed AU（raw）** — `reset` PI×2、`AOI211 _157_` SA0×1、`NOR4 _159_/A3` SA0×1。

**Scan-protocol 主指標（2026-06-09）：** 見 [`2026-06-09-scan-protocol-fc-metric.md`](./2026-06-09-scan-protocol-fc-metric.md)。`reset` PI → TI + `b03_reset_tie.v`；**FC_scan ≈ 93%**，comb AU ≤ 2。

---

### D3.2 — 原子複合閘 + MUX implication（2026-06-09）✅ → ⏳ 待 revert

> **過渡期實作。** Pipeline 驗收後移除 OAI/AOI atomic 建模；**D3.1 MUX 與本節 MUX implication 保留**。

**檔案：** `circuit.cpp`、`gate.h`、`atpg.cpp`、`atpg.h`、`simulator.h`

| Patch | 說明 |
|-------|------|
| **D3.2a** | `OAI21_X*` / `AOI21_X*` / `AOI211_X*` 改為單一 `Gate::OAI21/AOI21/AOI211`（同 MUX2 原子建模） |
| **D3.2b** | `setFaultyGate` + backward implication + SCOAP + parallel sim 支援複合閘 |
| **D3.2c** | MUX：S=X 且 output=D/B 時依 data path justify select；S-pin fault 直接設 `FaultyValue` |

**b03 實測（compression on）：**

| 指標 | D3.1 後 | D3.2 後 |
|------|---------|---------|
| FC（collapsed） | 81.50% | **92.26%** |
| AU（collapsed） | 101 | **4** |
| AU（full，`fan` stats） | 175 | **4** |
| collapsed faults | 881 | **853** |
| MUX AU | ~30 | **0** |
| OAI/AOI AU | ~50+ | **1** |

**Regression：** `tiny_sdffr` 91.67% AU=0；`s510` 99.14% AU=0；`scripts/test_phase_d_atpg.sh` PASS。

**AU dump：** `script/fanScripts/b03_au_dump_fs.script` → `rpt/b03_au_fs.rpt`

---

## 三、測試計劃

### 3.1 C++ 單元測試 — `phase_d_test`

**路徑：** `FAN_ATPG/pkg/core/src/phase_d_test.cpp`  
**執行：** `cd FAN_ATPG && ./pkg/core/bin/opt/phase_d_test .`

| 測試 | 條件 |
|------|------|
| `tiny_sdffr` 回歸 | FC ≥ 85%，AU = 0（Phase C 不退化） |
| `b03` MUX 計數 | atomic MUX gate 數 = 33 |
| `b03`（auto scan protocol） | **FC_scan ≥ 93%**；comb AU ≤ 2 |

### 3.2 Shell regression — `scripts/test_phase_d_atpg.sh`

**執行：** `bash scripts/test_phase_d_atpg.sh`

| Case | Gate |
|------|------|
| `phase_d_test` | 全過 |
| `tiny_sdffr` / `tiny_sdff` | FC ≥ 85%，AU = 0 |
| `s510` | FC ≥ 94%，AU = 0 |
| `s27` | FC ≥ 90% |
| `b03` scan-protocol | **FC_scan ≥ 93%**，comb AU ≤ 2 |

### 3.3 結果記錄

- `FAN_ATPG/rpt/phase_d_results.csv`
- 更新 `b03_investigation_2026-06-09.md` §5

---

## 四、Gate 決策

| Gate | 條件 | 不通過 |
|------|------|--------|
| **D1** | MUX=33, b03 FC ≥ 70% | 檢查 circuit 建構 |
| **G2'** | b03 FC ≥ 80% | **PASS**（phase_d_test 80.14%）；fan CLI 75.39% |
| **Regression** | s510/s27/tiny 不退化 | 回滾衝突改動 |

---

## 五、時程

| 任務 | 時間 |
|------|------|
| D1–D2 atpg.cpp | 1–2 h |
| D3 circuit.cpp | 2–3 h |
| D4 + tests | 1–2 h |
| Regression + 文件 | 1 h |
| **合計** | **~1 天** |

---

## 六、不做的事

- 不重寫 PODEM 主迴圈
- 不用 frame=2 修 full-scan
- 不換 netlist format
- 不把搜尋失敗與 formal untestability 混為一談（後續可再加 AB vs AU 分類）
