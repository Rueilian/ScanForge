# Scan-Protocol FC 指標定義（2026-06-09）

> **狀態：已實作** — 報告層、fault 分類層、netlist 層三合一。  
> **關聯：** [`2026-06-09-phase-d-podem-fix.md`](./2026-06-09-phase-d-podem-fix.md)、[`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)

---

## 一、為何要改主指標？

商用 full-scan stuck-at ATPG 的標準假設（Cummings, *SNUG 2002*；DFT `scan_mode` 慣例）：

1. **Shift / capture 期間 async reset 保持在 inactive（deasserted）**，否則 scan chain 資料會被清掉。
2. Reset stuck-at **不在同一套 combinational ATPG 向量裡測**；商用流程常另加 reset test sequence。

因此把 functional `reset` PI 當自由可控 fault 計入 FC，會 **低估引擎、高估 AU**，與業界報告的 FC 語意不一致。

---

## 二、主指標（正文用）

| 指標 | 定義 | FAN 輸出欄位 |
|------|------|--------------|
| **FC_scan**（主） | `DT / (FU_full − TI_scan_async)` | `fault coverage (scan protocol)` |
| **FC_scan_coll** | `DT_collapsed / (FU_collapsed − TI_scan_collapsed)` | `fault coverage (scan, collapsed)` |
| **TestCov_scan** | `DT / (UD+DT+PT+AB+TO − TI_scan_async)` | `test coverage (scan protocol)` |
| **AU_comb** | collapsed AU 中 **非** async-control PI 者 | `report_fault -s au` 過濾 |
| **TI_scan** | async reset/control PI 標為 TI 的 equivalent 數 | `TI (scan async control)` |

> **注意：** PPI QN 等 **UD** fault 仍計入分母（與 TetraMAX 等工具一致）。b03 在排除 reset 後 **FC_scan ≈ 93%**；殘差主要來自 QN UD + 2 comb AU，不是 reset 協定問題。

**Scan-protocol 對象：** top-level PI 名稱為  
`reset`, `rst`, `nrst`, `arst`, `areset`, `reset_n`, `RN`, `SN`（大小寫敏感，與 netlist 一致）。

**標準 full-scan 流程（FAN 預設，2026-06-09 起）：**

```text
add_fault --all        # 自動偵測 reset/rst/RN/SN 等 async PI → TI
run_atpg               # 若尚未套用，run 前再補一次
report_statistics      # FC_scan 為首行
```

附錄 raw 對照：`set_scan_protocol off` 後再 `add_fault --all`（見 `b03_raw_fs.script`）。

---

## 三、附錄指標（對照用）

| 指標 | 說明 |
|------|------|
| **FC_raw** | 舊定義：`DT / FU_full`（含 reset PI fault） |
| **TestCov_raw** | 舊 test coverage |
| **AU_reset** | reset PI 仍為 AU 的數量（raw netlist 對照） |

附錄 CSV：`results/appendix_phase_d_fullscan_raw.csv`  
Raw netlist script 範例：`FAN_ATPG/script/fanScripts/b03_raw_fs.script`

---

## 四、三層實作

### Level 1 — 報告層 ✅

- `ReportStatsCmd`：首行輸出 **FC_scan / TestCov_scan**；raw 標 `(appendix)`
- `scripts/parse_fan_scan_stats.py`：解析報告
- `scripts/run_phase_d_fullscan_dataset.sh`：主表 `results/phase_d_fullscan_dataset.csv`

### Level 2 — Fault list 層 ✅

- **自動套用**（預設）：`add_fault --all` / `run_atpg` 時呼叫 `applyScanProtocol()`
- 關閉：`set_scan_protocol off`（附錄 raw 模式）
- 實作：`FAN_ATPG/pkg/core/src/scan_protocol.cpp`
- 行為：async-control PI 的 SA0/SA1 → `Fault::TI`；`hasConstraint_=1`, `constraint_=PARA_H`

### Level 3 — Netlist 層 ✅

- `mod_netlist/b03_reset_tie.v`：`reset` 非 PI，內部 `LOGIC1` tie（結構性 deassert）
- 產生：`scripts/fixup_verilog.py --reset-tie-high`
- 批次：`scripts/regenerate_fan_fullscan_netlists.sh` 自動產 `*_reset_tie.v`
- **主線 script** 使用 `b03_reset_tie.v`（`b03_fs.script`, `b03_phase_d_fs.script`）

---

## 五、b03 預期結果（Phase D 後）

| 設定 | FC_scan | AU_comb | TI_scan | 備註 |
|------|---------|---------|---------|------|
| `b03.v`（auto scan protocol） | **~93.0%** | **2** | **2** | **Level 2 主報告** |
| `b03_reset_tie.v`（auto） | **~93.0%** | **2–3** | 0 | **Level 3 結構對齊** |
| `b03.v` raw（附錄） | ~92.8% | 4（含 reset×2） | 0 | 舊語意對照 |

殘餘 comb AU（`_157_` AOI211、`_159_/A3` NOR4）視為 FSM 內 UD 候選，不再追 PODEM。

---

## 六、Regression

```bash
cd FAN_ATPG && make -j$(nproc)
./pkg/core/bin/opt/phase_d_test .
bash scripts/test_phase_d_atpg.sh
```

Gate：`b03.v` + scan protocol **FC_scan ≥ 93%**、**AU_comb ≤ 2**；`b03_reset_tie` **FC_scan ≥ 92.5%**。

---

## 七、文獻對照

- Cummings, *SNUG 2002*：ATPG 期間 reset 保持 non-reset；reset vectors 另測。
- DFT 實務：`scan_mode` OR-gate 將 RN 維持 inactive。
- 本專案：Level 2（TI 分類）+ Level 3（netlist tie）對齊上述假設；Level 1 統一報告語意。
