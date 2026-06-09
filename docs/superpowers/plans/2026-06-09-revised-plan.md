# ScanForge 修訂計劃（2026-06-09）

> **給 agent 用：** 用 checkbox 追蹤；每個 gate 通過前不要進下一階段。舊計劃 `2026-06-09-final-completion.md` 的 `_const0_` 假設已部分推翻，以此文件為準。

**目標：** 在 6/16 簡報前，建立可信的 full-scan baseline，完成 spec 要求的三路比較（`full_scan` / `no_recovery` / `sequential recovery`），並產出可辯護的報告與圖表。

**截止：** 2026-06-16 簡報 · 2026-06-17 最終報告

---

## 一、現況總覽（誠實版）

| 項目 | 狀態 |
|------|------|
| Task 1 根因診斷 | ✅ 完成（但根因假設需更新，見下） |
| Task 2 pipeline + techlib | 🔧 部分完成（能跑、不 hang，**FC 未修**） |
| Task 3 b05 assign 語法 | ❌ 未做 |
| Task 4 重合成全部電路 | ❌ 未做 |
| Task 5 55-run sweep | ❌ 未做（**G2 gate 前禁止**） |
| Task 6 runner 三路 schema | ❌ 未做 |
| Task 7 報告圖表 | ❌ 未做 |
| Task 8 checklist / progress | ❌ 未做 |

**完成度：約 1.5 / 8**

---

## 二、已確認事實（取代舊假設）

### 已修復

1. **`std::cin.get()` hang** — `atpg.cpp` 已移除；需 `make` 重建 FAN
2. **MDT 語法錯誤** — `mod_nangate45.mdt` line ~1582 已修
3. **Pipeline 結構** — `fixup_verilog.py` 分離 full-scan / partial-scan；`verify_fullscan_netlist.sh` / `verify_scan_netlist.sh` 可用

### 已推翻或需修正的假設

| 舊假設 | 實際結果 |
|--------|----------|
| `_const0_` 是主因 | b08/b09/b13 無 `_const0_` 仍低 FC；修 tie cell 後 b03 仍 34.37% |
| DFFR → intern `_dff` 可修 FC | tiny 電路 OK，**b03 完全相同** 34.37% / 950 AU |
| Scan insertion 可修 full-scan FC | SDFFR 版 b03 同樣 34.37% / 950 AU |
| ITC'99 RTL 天生不可觀測 | test coverage ~90%，問題是 **950+ AU**，非 UD |

### 對照實驗（2026-06-09 更新）

| 電路 | FC | AU | 意義 |
|------|-----|-----|------|
| tiny_dffr (DFFR, no scan) | 87.5% | 0 | FAN 基本正常 |
| **tiny_sdff / tiny_sdffr (scan)** | **58.3%** | **8** | **功能路徑全 AU — SDFF intern 問題** |
| s27 / s510 (SDFF + comb) | 94–95% | 0–60 | 有 comb 邏輯時仍可測 |
| **b03 (SDFFR + MUX2 FSM)** | **34.2%** | **957** | **核心 blocker** |

**根因收斂（2026-06-09）：** 不是 frame 或 netlist 格式，而是 FAN 對 SDFF intern（`_mux`+`_dff`）與 PPI/PPO 抽象的建模衝突 + b03 MUX2-heavy 加劇 AU。詳見 [`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)。

### Sequential ATPG（progressive residual）

- **s27**：T=1→T=2→T=4 恢復 +43.9pp → 實作有效
- **b07/b13**：僅 +0.9–1.4pp；殘餘 fault >95% AU → 在現有 baseline 下 recovery 有限是**預期結果**，非方法論失敗

---

## 三、修訂後架構

```
┌─────────────────────────────────────────────────────────────┐
│  Phase B: FAN full-scan netlist（SDFFR + scan，對齊 s510）  │
└─────────────────────────────────────────────────────────────┘
                              ↓ G2 通過或選 fallback
┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│ full_scan        │  │ no_recovery      │  │ sequential      │
│ ratio=0          │  │ ratio>0, T=1     │  │ progressive T   │
│ fixup 預設       │  │ 同 netlist 結構  │  │ 僅在 baseline   │
│ SDFFR+scan chain │  │ +set_nonscan_ff  │  │ 可信後重跑      │
└──────────────────┘  └──────────────────┘  └─────────────────┘
```

**永久規則（2026-06-09 更新）：**

- **FAN full-scan（ratio=0）：** `fixup_verilog.py` **預設** `--full-scan` → SDFFR + scan chain + `CK`（見 `2026-06-09-fan-fullscan-netlist.md`）
- **Partial-scan（ratio>0）：** 相同 netlist 結構 + `set_nonscan_ff` + `PARTIAL_SEQUENTIAL`
- **DFFR-only（`--no-scan`）：** 僅供除錯，不用於 FAN full-scan baseline

---

## 四、分階段執行

### Phase A：解鎖與驗證（~1–2 小時）✅

**目的：** 確認環境可重現，不會再 hang。

- [x] **A1** 重建 FAN：`cd FAN_ATPG && make -j$(nproc)`
- [x] **A2** s27 full-scan：FC = 94.55%，AU = 0
- [x] **A3** b03 full-scan：0.05s 完成，FC = 34.24%，不 hang
- [x] **A4** `bash scripts/verify_fullscan_netlist.sh` — 10 個 ITC netlist 全 PASS

**Gate G0：** FAN 非互動執行不 freeze  
**Gate G1：** s27 FC ≥ 90%

---

### Phase B：b03 AU 診斷（~1–3 天）— ✅ 診斷完成，修復轉 Phase C

**目的：** 找出低 FC 根因。**已完成**；修復工作移至 Phase C。

#### 已完成實驗

| 項目 | 結果 | 結論 |
|------|------|------|
| B1 RN tie-high | FC 34.28% | 無效（C2 將用正式路徑重試） |
| B2 frame=2 | FC 32.23% | 更差；不適用 full-scan |
| B-extra clock→CK + _const | pipeline OK | 必要但不充分 |
| SDFFR format migration | FC 34.17% | 格式正確，FC 不變 |
| Scan-port + MUX fix | FC 34.17% | 必要但不充分 |
| **B4 tiny_sdff 隔離** | d/q/PPI/PPO 全 AU | **確認 SDFF intern 建模問題** |
| **B4 AU 分群** | 341 MUX2, 46 SDFFR | 見 `b03_investigation` §3.3 |
| 關閉 compression | FC 33.33%, 97 patterns | 非 pattern 數量問題 |

#### 已取消 / 降級

- ~~B3 全量 MDT seq3→intern 遷移~~ — DFFR_X1 遷移已證明對 b03 無效；優先改 FAN circuit 抽象
- ~~frame=2 作為 full-scan 修復~~ — 用戶確認不適用

**Gate G2：** ❌ 未通過（b03 FC ≈ 34%）。診斷結論已寫入 `FAN_ATPG/rpt/b03_investigation_2026-06-09.md`。

---

### Phase C：FAN Engine 修復（最高優先，~2–4 天）— **進行中**

> 詳細步驟、gates、時程：[`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)

#### C1. SDFF/SDFFR 黑盒化（FAN `circuit.cpp`）— 未開始

- [ ] C1.1–C1.4：`createCircuitComb()` 跳過 DFF cell intern primitives
- [ ] C1.5–C1.6：tiny_sdffr / s510 / b03 regression
- [ ] C1.8（若需要）：MUX2 implication 強化

**Gate C1：** `tiny_sdffr` 功能路徑 DT > 0；s510 FC ≥ 94%；b03 FC 顯著上升

#### C2. RN tie-high 重試 — 未開始

- [ ] 用 `mod_netlist/b03_rn_tie.v` 正式路徑重跑

#### C3. 外部 ATPG reference — 未開始

- [ ] TetraMAX/Modus 或 DVCON 文獻對照

**Gate G2（6/11 決策）：** b03 FC ≥ 80% → Phase D；否則 fallback

---

### Phase C-pipeline：Pipeline 固化（與 C1 並行或 G2 後）

- [ ] **C1** 確認 `strip_scan_from_netlist.py` 與 full-scan 流程文件化
- [ ] **C2** `synth_itc99.sh` 預設 DFFR + tie cells；`--scan` 僅 partial 用
- [ ] **C3** Task 3：修 b05 `assign` 語法錯誤
- [ ] **C4** Task 4：`bash scripts/synth_itc99.sh`（需 Yosys in PATH）重生成 10 電路
- [ ] **C5** 重跑 `verify_fullscan_netlist.sh` + `verify_scan_netlist.sh`

---

### Phase D：實驗與報告（僅 G2 後）

#### D1. Runner 三路 schema（Task 6）

- [ ] 擴充 `run_atpg_sweep.py` / `run_stage1_fan_cases.py`：
  - `full_scan` — ratio=0, frame=1（或 G2 決定的 frame）
  - `partial_scan_no_recovery` — ratio=R, T=1, non-scan=X
  - `partial_scan_sequential` — progressive residual T=1→2→4（或 spec 定義）
- [ ] 輸出 schema 與 `results/itc99_partial_scan.csv` 欄位對齊 spec

#### D2. 55-run sweep（Task 5）

- [ ] 僅在 G2 通過或 fallback 路徑確認後執行
- [ ] 電路 × ratio × mode；timeout 600s；記錄 DT/AU/FC/runtime
- [ ] 驗證單調性：**full_scan ≥ no_recovery**（至少 3 電路）

**Gate G3：** monotonicity 成立或已解釋例外  
**Gate G4：** sweep 完整、CSV 無缺列

#### D3. 圖表與文件（Task 7–8）

- [ ] 更新 `progress_report.md`、`checklist.md`
- [ ] FC vs ratio 圖、sequential recovery 圖（含 s27 正面 + b07/b13 有限恢復）
- [ ] 若 fallback：明確寫「FAN frame-1 full-scan 在 ITC'99 天花板 ~35–52%，sequential recovery 在 AU-dominated residual 下增益有限」

**Gate G5：** 簡報用表圖齊全

---

### Phase E：Sequential ATPG 重評（baseline 可信後）

- [ ] 用修正後 full-scan baseline 重跑 b07/b13 progressive residual
- [ ] 更新 `results/progressive_residual_summary.csv`
- [ ] 報告 framing：
  - **方法有效：** s27 證明
  - **ITC 增益小：** residual AU-dominated，屬數據特性而非實作 bug

---

## 五、成功標準（Gates）

| Gate | 條件 | 不通過時 |
|------|------|----------|
| **G0** | FAN 非互動不 hang | 禁止任何 sweep |
| **G1** | s27 FC ≥ 90% | 修 FAN/MDT，不碰 ITC |
| **G2** | b03 FC ≥ 80% 或 documented ceiling | 走 Fallback，不假裝 baseline 正常 |
| **G3** | full_scan ≥ no_recovery（≥3 電路） | 修 partial-scan 建模 |
| **G4** | 55-run 完成 | 縮小電路集合仍須報告 |
| **G5** | 圖表 + checklist 更新 | 簡報前至少完成 G2 敘事 |

---

## 六、Fallback 路徑（G2 失敗時）

若 Phase C 後 b03 仍 < 50% 且（外部工具 ≥ 80% **或** tiny_sdff 仍全 AU）：

1. **報告主線改為：** timing-driven partial-scan 在「低 full-scan 天花板」電路上的行為
2. **保留：** s27 sequential recovery 正面結果 + 6 個 partial-scan 電路數據
3. **誠實結論：** FAN SDFF intern 建模缺陷導致 ITC'99 full-scan FC 上限 ~35–55%；非 ITC'99 天生不可測（文獻/DVCON 對照）；progressive residual 對 AU-dominated residual 幫助有限
4. **不做：** 用未修復 FAN baseline 跑完整 55-run 再事後合理化

此路徑仍可滿足「方法驗證 + 評估 + 負面結果」的學術價值。

---

## 七、建議時程（至 6/16）

| 日期 | 工作 |
|------|------|
| **6/9（今）** | Phase B 診斷完成；文件更新；啟動 Phase C1 |
| **6/10–6/11** | C1 SDFF 黑盒化 + C2 RN 重試；G2 決策 |
| **6/12** | C3 外部 reference；Pipeline 固化；若 G2 過則開始 D1 |
| **6/13–6/14** | D2 sweep 或 fallback 敘事固化 |
| **6/15** | D3 圖表、簡報稿 |
| **6/16** | 簡報 |

---

## 八、關鍵檔案

| 用途 | 路徑 |
|------|------|
| 狀態快照 | `docs/superpowers/plans/2026-06-09-atpg-pipeline-status.md` |
| 本計劃 | `docs/superpowers/plans/2026-06-09-revised-plan.md` |
| **Phase C 詳細計劃** | `docs/superpowers/plans/2026-06-09-phase-c-fan-atpg-fix.md` |
| 舊計劃（部分過時） | `docs/superpowers/plans/2026-06-09-final-completion.md` |
| b03 調查報告 | `FAN_ATPG/rpt/b03_investigation_2026-06-09.md` |
| FAN hang 修復 | `FAN_ATPG/pkg/core/src/atpg.cpp` |
| MDT | `FAN_ATPG/techlib/mod_nangate45.mdt` |
| Full-scan fixup | `scripts/fixup_verilog.py`（無 `--scan`） |
| 驗證 | `scripts/verify_fullscan_netlist.sh` |
| Sequential 結果 | `results/progressive_residual_summary.csv` |

---

## 九、立即下一步（給下一個 agent）

1. **Phase C1：SDFF/SDFFR 黑盒化** — 見 [`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md) §3
2. Regression：`tiny_sdffr` 功能路徑必須有 DT（目前全 AU）
3. **不要** 在 G2 決策前跑 55-run sweep
4. **不要** 用 frame=2 修 full-scan baseline
5. 每完成一個 gate，更新本文件 + `atpg-pipeline-status.md`
