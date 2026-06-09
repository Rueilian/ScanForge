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

### 對照實驗（cin.get 修復後）

| 電路 | FC | AU | 意義 |
|------|-----|-----|------|
| tiny_dff / tiny_dffr / tiny_loop | 84–87% | 0 | FAN + mdt 基本正常 |
| s27 (SDFF + scan chain) | 94.6% | 0 | 參考基準 |
| **b03（任何 mdt / DFFR / SDFFR）** | **34.4%** | **950** | **核心 blocker** |

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

### Phase B：修 b03 AU 問題（最高優先，~1–3 天）

**目的：** FC ≥ 80%（至少 b03 + 一個較大電路如 b07），**或** 用證據記錄 FAN 在此 netlist 上的天花板。

依序嘗試，**任一實驗 FC 明顯跳升即停止並固化設定**：

#### B1. RN tie-high（async reset 測試模式）❌ 無效

- [x] `fixup_verilog.py --rn-tie-high` 已實作
- [x] b03：FC 34.28%，AU 954（與 baseline 相同）

#### B2. Frame=2 CAPTURE baseline ❌ 更差

- [x] b03 frame=2：FC 32.23%，AU 941

#### B-extra. clock→CK + orphan _const 修復 ✅ pipeline

- [x] `clock`→`CK`：b03 PI 6→5，FC 不變
- [x] `fix_orphan_const_inputs()`：修復 b07/b09/b11/b15 的 `input _const0_;` parse error

#### B3. 完成 MDT 遷移

- [ ] 將剩餘 `seq3` 的 DFFR_X2、DFFS、DFF、SDFFR、SDFF_X2 改為 `intern + _dff` / `_mux + _dff`
- [ ] tiny_dffr + b03 回歸
- **已知：** 僅 DFFR_X1 遷移無效；全量遷移仍值得一次驗證

#### B4. 拓撲診斷

- [ ] 比對 b03 vs s27：combinational loop、clock gating、feedback 結構
- [ ] 匯出 AU fault 清單，按 cone / FF / PI 分群
- [ ] 檢查 `circuit.cpp` PI 排除、`CK` 建模是否讓 ITC 電路整體 AU

#### B5. 外部參考（若 B1–B4 仍 ~34%）

- [ ] 同一 `b03.v` 用 TetraMAX / 其他 ATPG 跑 full-scan FC
- [ ] 若外部工具 >80% → FAN 建模問題；若也 ~35% → netlist/constraint 問題

**Gate G2：** b03 FC ≥ 80% **或** 完成 B1–B5 並寫入 `b03_root_cause_analysis.md` 最終結論（含 fallback 決策）

---

### Phase C：Pipeline 固化（與 B 並行或緊接 B）

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

若 Phase B 後 b03 仍 ~34% 且外部工具亦低 FC：

1. **報告主線改為：** timing-driven partial-scan 在「低 full-scan 天花板」電路上的行為
2. **保留：** s27 sequential recovery 正面結果 + 6 個 partial-scan 電路數據
3. **誠實結論：** ITC'99 + FAN frame-1 模型下 full-scan FC 上限 ~35–52%；progressive residual 對 AU-dominated residual 幫助有限
4. **不做：** 用錯誤 baseline 跑完整 55-run 再事後合理化

此路徑仍可滿足「方法驗證 + 評估 + 負面結果」的學術價值。

---

## 七、建議時程（至 6/16）

| 日期 | 工作 |
|------|------|
| **6/9（今）** | Phase A 完成；啟動 B1 RN tie-high |
| **6/10–6/11** | B2–B4；G2 決策 |
| **6/12** | Phase C（b05、synth）；若 G2 過則開始 D1 |
| **6/13–6/14** | D2 sweep 或 fallback 敘事固化 |
| **6/15** | D3 圖表、簡報稿 |
| **6/16** | 簡報 |

---

## 八、關鍵檔案

| 用途 | 路徑 |
|------|------|
| 狀態快照 | `docs/superpowers/plans/2026-06-09-atpg-pipeline-status.md` |
| 本計劃 | `docs/superpowers/plans/2026-06-09-revised-plan.md` |
| 舊計劃（部分過時） | `docs/superpowers/plans/2026-06-09-final-completion.md` |
| b03 分析 | `FAN_ATPG/rpt/b03_root_cause_analysis.md` |
| FAN hang 修復 | `FAN_ATPG/pkg/core/src/atpg.cpp` |
| MDT | `FAN_ATPG/techlib/mod_nangate45.mdt` |
| Full-scan fixup | `scripts/fixup_verilog.py`（無 `--scan`） |
| 驗證 | `scripts/verify_fullscan_netlist.sh` |
| Sequential 結果 | `results/progressive_residual_summary.csv` |

---

## 九、立即下一步（給下一個 agent）

1. 執行 Phase A（重建 + G0/G1）
2. **Phase B1：RN tie-high on b03** — 目前最高 ROI 實驗
3. **不要** 在 G2 解決前跑 55-run sweep
4. 每完成一個 gate，更新本文件 checkbox 與 `2026-06-09-atpg-pipeline-status.md`
