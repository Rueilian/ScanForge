# Phase C：FAN Full-Scan FC 修復計劃（2026-06-09）

> **歷史文件。** Phase C 觸發 Phase D；現行主指標 **FC_scan** 見 [`2026-06-09-scan-protocol-fc-metric.md`](./2026-06-09-scan-protocol-fc-metric.md)。Phase D 結果見 [`2026-06-09-phase-d-podem-fix.md`](./2026-06-09-phase-d-podem-fix.md)、[`2026-06-09-atpg-pipeline-status.md`](./2026-06-09-atpg-pipeline-status.md)。
>
> **前置：** Phase A/B 完成；G0/G1 通過；G2 **未通過**（b03 FC ≈ 34%）。
> **本計劃目標：** 在 6/16 簡報前，要麼把 full-scan baseline 拉到可辯護水準（b03 ≥ 80%），要麼用可重現證據正式記錄 FAN 天花板並切換 fallback。
>
> **執行狀態（2026-06-09）：✅ Phase C 完成 — G2 FAIL，走 fallback。** C1 實際修復為 `checkIfFaultHasPropagatedToPO`（非 SDFF 黑盒化）。結果見 `FAN_ATPG/rpt/phase_c_results.csv`。
> **關聯文件：** [`2026-06-09-atpg-pipeline-status.md`](./2026-06-09-atpg-pipeline-status.md)、[`2026-06-09-revised-plan.md`](./2026-06-09-revised-plan.md)、[`FAN_ATPG/rpt/b03_investigation_2026-06-09.md`](../../../FAN_ATPG/rpt/b03_investigation_2026-06-09.md)

---

## 一、問題陳述（已確認）

### 1.1 現象

| 電路 | FC | AU | Test Cov | Patterns |
|------|-----|-----|----------|----------|
| s510 | 94.86% | 60 | — | — |
| b03 | 34.17% | 957 | 89.51% | 11 |
| b07 | ~43% | ~1500 | — | — |

- **957 AU 佔 collapsed fault 的 86%** — 問題是 FAN 過度標記 untestable，不是 pattern 品質差。
- 關閉 compression（97 patterns）FC 仍 **33.33%**；**AB = 0**（非 abort limit）。

### 1.2 根因假設（按信心排序）

| # | 假設 | 證據 | 信心 |
|---|------|------|------|
| H1 | FAN 在 SDFF/SDFFR intern（`_mux` + `_dff`/`Gate::NA`）與 PPI/PPO 抽象之間建模衝突 | `tiny_sdff`/`tiny_sdffr`：d/q/PPI/PPO **全 AU**；`tiny_dffr` 同結構 **87.5% FC** | **高** |
| H2 | b03 MUX2-heavy + FSM feedback 使 FAN PODEM 在 reconvergent fanout 上過早放棄 | 341/957 AU 在 `MUX2_X1`；s510 無 MUX2 僅 60 AU | **高** |
| H3 | Async RN 未在 test mode tie-high | 62 UD 在 QN；商業 DFT 慣例 tie RN；先前 B1 實驗可能路徑錯誤 | **中** |
| H4 | Netlist 格式 / scan chain / frame 設定錯誤 | 結構驗證 PASS；full-scan ≡ frame-1 combinational | **排除** |
| H5 | ITC'99 b03 天生 full-scan 只有 ~35% | DVCON：Modus b03 882 faults PASS；業界 full-scan 預期 95–99% | **排除** |

### 1.3 設計原則（用戶確認）

- **Full-scan 不需 multi-frame**：SDFFR + scan 後，ATPG 對象是 **PPI/PPO combinational circuit**，`frame=1` 即標準模型。
- **不要** 用 frame=2 來「修」 full-scan baseline。

---

## 二、執行策略總覽

```
Phase C1: SDFF 黑盒化（FAN engine）     ← 最高 ROI，2–3 天
    ↓ Gate C1
Phase C2: RN tie-high 重試 + 約束驗證    ← 1 天
    ↓ Gate C2（可與 C1 並行尾段）
Phase C3: 外部 ATPG reference           ← 1–2 天（取決於工具可用性）
    ↓ Gate C3 → G2 決策
Phase C4: Fallback 或 Phase D sweep       ← G2 後
```

**G2 決策點（6/11 前）：**

- **通過：** b03 FC ≥ 80%（或 b03 + b07 皆 ≥ 70% 且有上升趨勢）→ 進 Phase D 55-run sweep
- **失敗：** 記錄 FAN vs 外部工具差距 → fallback 敘事 → partial-scan 主線

---

## 三、Phase C1：SDFF/SDFFR 黑盒化（FAN Engine Fix）

### 3.1 目標

在 capture-mode full-scan ATPG 中，**不把 scan FF intern 當組合邏輯傳播**，改為標準 DFT 抽象：

- FF 的 **Q → PPI**（獨立 controllable headline）
- FF 的 **D → PPO**（observable endpoint）
- Intern `_mux`、`_dff` **不參與** PODEM justify/propagate（或等價為透明 BUF）

### 3.2 預期效果

| 電路 | 修復前 FC | 預期修復後 |
|------|-----------|------------|
| `tiny_sdff` | 58.3%（功能路徑全 AU） | **≥ 85%**，d/q/PPI/PPO 可 DT |
| s510 | 94.86% | **≥ 94%**（不回歸） |
| b03 | 34.17% | **待驗**；若 H1 為主因，預期 **顯著跳升**（目標 ≥ 80%） |

### 3.3 實作方案（三選一，按風險由低到高）

#### 方案 A：Circuit 建構時跳過 DFF cell intern primitives（**推薦**）

**位置：** `FAN_ATPG/pkg/core/src/circuit.cpp` — `createCircuitComb()` / `createCircuitPmt()`

**邏輯：**
1. 辨識 top-level cell 為 `Pmt::DFF`（含 SDFF/SDFFR/DFFR）。
2. **不展開** `libc_` intern 區的 `_mux`、`_dff` primitive 為 circuit gate。
3. 僅保留既有 `createCircuitPPI()` / `createCircuitPPO()` 的 D/Q 邊界連線。
4. PPO fanin：從 D port net 連到驅動 gate（與現況相同）。
5. PPI fanout：從 Q port net 連到負載 gate（與現況相同）。

**優點：** 最貼近商業 ATPG full-scan 抽象；改動集中。
**風險：** Fault list 若掛在 intern pin 上可能需調整；需確認 `add_fault --all` 仍覆蓋 cell 邊界 pin。

#### 方案 B：Intern gate 標記為 `Gate::BUF` 直通

**位置：** `determineGateType()` — `_dff` → `BUF`，`_mux` 在 `test_se=TIE0` 時視為 BUF。

**優點：** 改動小。
**風險：** RN/CK 等 DFF 控制腳仍可能產生錯誤 implication；不如方案 A 乾淨。

#### 方案 C：ATPG 階段忽略 intern cone

**位置：** `atpg.cpp` — `identifyGateLineType()` 或 `initializeCircuitWithFaultyGate()` 跳過 DFF intern gate ID 範圍。

**優點：** 不動 circuit 拓撲。
**風險：** intern gate 仍參與 SCOAP / fault sim，可能殘留副作用。

### 3.4 實作步驟（實際採用：PO/PPO 觀測修復）

原方案 A（SDFF 黑盒化）調查後發現 DFF intern 本未展開；真正 bug 在 `atpg.cpp::checkIfFaultHasPropagatedToPO` 尾端索引被 scan pseudo 遮蓋。

- [x] **C1-fix** `checkIfFaultHasPropagatedToPO`：遍歷 `Gate::PO` / observable `Gate::PPO`
- [x] **C1.6** regression：`scripts/test_phase_c_atpg.sh` + `pkg/core/bin/opt/phase_c_test`
- [x] **C1a** tiny_sdffr：FC 91.7%，AU 0，d/q/PPI/PPO 全 DT
- [x] **C1b** s510：FC 99.1%，AU 0
- [ ] **C1.8** MUX2 專項（b03 仍 ~35%）— 留作後續，非 Phase C 阻擋項

### 3.5 Regression 腳本與 Gate C1

```bash
cd FAN_ATPG && make -j$(nproc)

# 必須全過
./pkg/fan/bin/opt/fan -f script/fanScripts/tiny_dffr_check.script   # FC ≥ 85%, AU = 0
./pkg/fan/bin/opt/fan -f script/fanScripts/tiny_sdffr_check.script  # FC ≥ 85%, d/q/PPI/PPO 有 DT
./pkg/fan/bin/opt/fan -f script/fanScripts/s27_debug_fullscan.script # FC ≥ 90%
./pkg/fan/bin/opt/fan -f script/fanScripts/b03_fs.script             # 記錄 FC/AU

# Gate C1 條件
#   tiny_sdffr: 功能路徑 fault 至少一個 DT（d 或 q 或 PPO）
#   s510: FC ≥ 94%（無回歸）
#   b03: FC 較 34% 上升 ≥ 20pp，或 AU 下降 ≥ 300
```

| Gate | 條件 | 不通過 |
|------|------|--------|
| **C1a** | `tiny_sdffr` 功能路徑 DT > 0 | 方案 A 實作有誤，檢查 PPI/PPO 連線 |
| **C1b** | s510 FC ≥ 94% | 回歸，檢查 comb gate 計數 |
| **C1c** | b03 FC ≥ 50% 或 AU ≤ 600 | 進 C1.8 MUX2 專項；若仍失敗進 C3 |

### 3.6 預估工時

| 任務 | 時間 |
|------|------|
| C1.1–C1.4 實作 | 4–6 h |
| C1.5–C1.6 regression | 2 h |
| C1.8 MUX2（若需要） | 4–8 h |
| **合計** | **1–2 天** |

---

## 四、Phase C2：RN Tie-High 與 ATPG 約束

### 4.1 背景

先前 B1 實驗（FC 34.28%）可能因 netlist 路徑在 `/tmp` 導致 FAN 未正確讀取。需用**正式路徑**重試。

商業 DFT 慣例：test mode 下 async reset **deasserted**（RN = 1）。

### 4.2 步驟

- [x] **C2.1** 生成 `mod_netlist/b03_rn_tie.v` / `b03_reset_tie.v`：
  ```bash
  python3 scripts/fixup_verilog.py \
    FAN_ATPG/mod_netlist/b03_dffr_base.v \
    FAN_ATPG/mod_netlist/b03_rn_tie.v \
    --full-scan --rn-tie-high
  ```
  （base 來源依 `regenerate_fan_fullscan_netlists.sh` 優先順序選正確輸入）

- [x] **C2.2** per-FF RN retarget → FAN `Netlist::check` 失敗（reset INV 浮空）；reset tie-high → FC 33.96%（無改善）

- [x] **C2.3** `script/fanScripts/b03_reset_tie.script`

- [x] **C2.4** `FAN_ATPG/rpt/phase_c_results.csv`

- [x] **C2.5** 結論：RN/reset tie **非 b03 FC 主因**

### 4.3 Gate C2

| 結果 | 動作 |
|------|------|
| FC 上升 ≥ 5pp | 將 `--rn-tie-high` 固化為 full-scan 預設 |
| FC 不變 | 記錄「RN 非主因」；不阻擋 G2 |
| FC 下降 | 檢查 tie cell 是否引入新 DRC |

**預估工時：** 0.5–1 天（可與 C1 尾段並行）

---

## 五、Phase C3：外部 ATPG Reference

### 5.1 目的

分離 **FAN engine 天花板** vs **netlist 真實 testability 天花板**。

### 5.2 輸入

- Netlist：`FAN_ATPG/mod_netlist/b03.v`（FAN format，SDFFR + scan）
- Library：Nangate45（或等價 liberty，若工具需要）
- Fault model：stuck-at，full-scan test protocol

### 5.3 工具優先順序

| 工具 | 可行性 | 備註 |
|------|--------|------|
| **Synopsys TetraMAX** | 視 license | 學界最常見 reference |
| **Cadence Modus** | 視 license | DVCON 論文有 b03 數據可對照 |
| **Open-source（如 atalanta, hope）** | 低 | ITC'99 規模可能不夠 |
| **文獻數據** | 高 | DVCON b03 882 faults 作為 lower bound reference |

### 5.4 步驟

- [x] **C3.1** 無本地 TetraMAX/Modus license → 使用 DVCON 文獻對照
- [x] **C3.2** —（跳過 tool script）
- [x] **C3.3** FAN b03：1112 faults，34.75% FC；文獻 b03：882 faults PASS
- [x] **C3.4** `FAN_ATPG/rpt/b03_external_atpg_comparison.md`

### 5.5 決策矩陣（G2）

| 外部 FC | FAN FC（C1 後） | 結論 | 行動 |
|---------|----------------|------|------|
| ≥ 80% | < 50% | **FAN 問題** | 報告聚焦 C1 修復進度；sweep 用修復後 FAN 或標註 ceiling |
| ≥ 80% | ≥ 80% | **已解決** | 進 Phase D sweep |
| < 50% | ~34% | **Netlist/constraint 問題** | 查 scan protocol、RN、tie cell；可能需重新 synth |
| 無工具 | — | **文獻 + tiny 實驗** | Fallback 用 H1 證據 + DVCON 數據 |

**預估工時：** 1–2 天（無 license 則 0.5 天寫文獻對照）

---

## 六、Phase C4：G2 後分支

### 6.1 G2 通過（b03 FC ≥ 80%）

接 [`2026-06-09-revised-plan.md`](./2026-06-09-revised-plan.md) Phase D：

1. Runner 三路 schema（`full_scan` / `no_recovery` / `sequential`）
2. 55-run sweep（6 電路 × ratio × mode）
3. 圖表 + checklist

### 6.2 G2 失敗（Fallback）— **已由 Phase D 取代**

> **2026-06-09 更新：** Phase D 將 b03 提升至 **FC_scan ≈ 93%**。下列 fallback 敘事僅保留歷史脈絡；現行報告以 Phase D + scan-protocol 為準。

**當時報告主線（已過時）：**

1. ~~FAN full-scan 天花板 b03 ~34%~~ → **已修復至 ~93% FC_scan**
2. 方法論（s27 sequential recovery）仍有效
3. 主指標改 **FC_scan**；FC_raw 放附錄

---

## 七、時程（6/9 → 6/16）

| 日期 | 工作 | 產出 |
|------|------|------|
| **6/9（今）** | 更新文件；啟動 C1.1 | 本計劃 + status doc |
| **6/10** | C1.1–C1.6 實作 + tiny/s510 regression | Gate C1a/C1b |
| **6/11** | C1 b03 驗證；C2 RN tie-high；G2 初判 | b03 FC 數字 |
| **6/12** | C3 外部 reference 或文獻對照；G2 最終決策 | `b03_external_atpg_comparison.md` |
| **6/13–6/14** | Phase D sweep **或** fallback 敘事固化 | CSV / 圖表 |
| **6/15** | 簡報稿 | slides |
| **6/16** | 簡報 | — |

---

## 八、驗收清單（給 agent）

### 每次改 FAN 後必跑

```bash
cd FAN_ATPG && make -j$(nproc)
./pkg/fan/bin/opt/fan -f script/fanScripts/tiny_dffr_check.script
./pkg/fan/bin/opt/fan -f script/fanScripts/tiny_sdffr_check.script
./pkg/fan/bin/opt/fan -f script/fanScripts/s27_debug_fullscan.script
./pkg/fan/bin/opt/fan -f script/fanScripts/b03_fs.script
```

### 必須更新的文件

| 事件 | 更新 |
|------|------|
| 完成 C1 | 本文件 checkbox + `atpg-pipeline-status.md` + `b03_investigation` |
| G2 決策 | `revised-plan.md` Phase B/C 狀態 |
| 外部 ATPG | `FAN_ATPG/rpt/b03_external_atpg_comparison.md` |

### 禁止事項

- ❌ 在 G2 決策前跑 55-run sweep
- ❌ 用 frame=2「修」 full-scan baseline
- ❌ 把 AU 當成「ITC'99 天生不可測」而不查 FAN engine

---

## 九、關鍵檔案索引

| 用途 | 路徑 |
|------|------|
| 調查報告 | `FAN_ATPG/rpt/b03_investigation_2026-06-09.md` |
| Circuit 建構 | `FAN_ATPG/pkg/core/src/circuit.cpp` |
| ATPG 引擎 | `FAN_ATPG/pkg/core/src/atpg.cpp`, `atpg.h` |
| MDT scan cell | `FAN_ATPG/techlib/mod_nangate45.mdt`（SDFFR_X1 intern） |
| Tiny 實驗 netlist | `FAN_ATPG/mod_netlist/tiny_{dffr,sdff,sdffr}.v` |
| b03 ATPG script | `FAN_ATPG/script/fanScripts/b03_fs.script` |
| RN tie-high | `scripts/fixup_verilog.py --rn-tie-high` |
| 狀態快照 | `docs/superpowers/plans/2026-06-09-atpg-pipeline-status.md` |
