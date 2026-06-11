# FAN Full-Scan Netlist 規格（對齊 s510）

> **決策日期：** 2026-06-09  
> **狀態：** 格式規格已完成；**建置流程**遷移至 [`2026-06-09-primitive-netlist-pipeline-complete.md`](./2026-06-09-primitive-netlist-pipeline-complete.md)（`build_itc99_netlists.sh`）  
> **MUX2：** 視為 **base gate**，允許出現在 netlist；FAN 保留 `Gate::MUX`（Phase D1）。OAI/AOI 複合閘禁止，由合成展開。

## 背景

FAN ATPG 在 ISCAS'89 參考電路（`s510`、`s953`、`s27`）上可達 **>97% fault coverage**，但 ITC'99 用 Yosys `DFFR` netlist 僅 ~34–52%。

對照發現：**FAN 驗證過的 full-scan 格式不是「裸 DFFR + PPI 可控」**，而是：

| 項目 | s510 / s27（FC >94%） | 舊 ITC pipeline（FC ~34%） |
|------|----------------------|---------------------------|
| FF 型態 | `SDFF_X1` / `SDFFR_X1` | `DFFR_X1` |
| Scan chain | `test_si` → FF → … → `test_so` | 無 |
| Scan enable | `test_se` | 無 |
| Clock port | `CK` | `clock` |
| `.QN()` | 不接（或僅用於有負載者） | 31 個浮空 QN |
| Constant | 無 `input _const0_` | 有 orphan const |

## FAN Full-Scan 標準格式（ratio=0 亦適用）

```
module b03(..., test_si, test_so, test_se);
  input CK;          // 必須叫 CK，FAN 才排除 clock PI
  input test_si;
  input test_se;
  output test_so;
  ...
  SDFFR_X1 _237_ (
    .CK(CK),
    .D(...),
    .Q(...),
    .RN(...),        // 或 --rn-tie-high 實驗用
    .SE(test_se),
    .SI(test_si)     // 或前一顆 FF 的 Q
  );
  ...
  assign test_so = <last_ff_q>;
endmodule
```

**要點：**

1. `fixup_verilog.py --full-scan`（預設）將 `DFFR` → `SDFFR` 並串 scan chain
2. `clock` / `CLOCK` / `clk` / `CLK` → `CK`
3. `_constN_` → `LOGIC0/LOGIC1` tie cell
4. 浮空 `.QN()` 移除；有接線的 `.QN()` 保留
5. MDT 使用 `SDFFR_X1` 的 `intern(_mux + _dff)` 模型（已遷移）

## Pipeline 分工

| 模式 | fixup 旗標 | Netlist 特徵 | ATPG 用途 |
|------|-----------|-------------|-----------|
| **FAN full-scan** | `--full-scan`（預設） | SDFFR + scan chain | `ratio=0` baseline |
| **Partial-scan** | `--scan`（同 full-scan 結構） | SDFFR + scan chain | `ratio>0` + `set_nonscan_ff` |

> 注意：`--scan` 與 `--full-scan` 產生相同 netlist 結構；差異在 ATPG 腳本（是否 `set_nonscan_ff`）。

## 驗證

```bash
bash scripts/verify_fullscan_netlist.sh   # FAN full-scan 結構檢查
bash scripts/regenerate_fan_fullscan_netlists.sh
```

來源優先序：`{c}_dffr.v` → `{c}_dffr_only.v` → `{c}_ck.v` → strip 現有 `{c}.v`（避免 strip→re-scan 破壞仍接在邏輯上的 `.QN()` net）。

## ATPG 驗證結果（FAN format, frame=1, Phase D 後）

> **主指標：** **FC_scan**（scan-protocol）。定義見 [`2026-06-09-scan-protocol-fc-metric.md`](./2026-06-09-scan-protocol-fc-metric.md)。

| 電路 | FC_scan | FC_raw（附錄） | AU_comb | 備註 |
|------|---------|---------------|---------|------|
| s510 | 99.14% | 99.14% | 0 | 參考 |
| b03 | **93.03%** | 92.83% | 2 | Phase D PODEM + auto scan protocol |
| b07 | ~89% | ~89% | — | 待完整 sweep |

**結論：** 格式遷移（SDFFR+scan）為必要條件；Phase D 修復 PODEM 後 b03 可達業界對齊的 **FC_scan ~93%**。殘差主要為 QN UD + 2 comb AU，非 netlist 格式問題。

## 參考 FAN script（scan-protocol 標準）

```
read_lib techlib/mod_nangate45.mdt
read_netlist mod_netlist/b03_reset_tie.v
build_circuit --frame 1
set_fault_type saf
add_fault --all
set_static_compression on
set_dynamic_compression on
set_X-Fill on
run_atpg
add_scan_chains -o results/b03.sf
report_statistics
exit
```

有 `reset` PI 的 netlist 用 `mod_netlist/b03.v` 時引擎會自動 TI（Level 2）；結構性 tie 用 `*_reset_tie.v`（Level 3）。

## 相關檔案

- `scripts/build_itc99_netlists.sh` — **推薦**一鍵建置（prep → synth → fixup → validate）
- `scripts/fixup_verilog.py` — `--full-scan` 實作（v2：`expand_bus_assigns`、SDFFR early-return 修復）
- `scripts/synth_itc99.sh` — Yosys 合成（將改用 `NangateOpenCellLibrary_base.lib`）
- `scripts/validate_netlist.py` — undriven=0、無 OAI/AOI、full-scan 結構
- `scripts/verify_fullscan_netlist.sh` — 結構驗證（legacy）
- `scripts/regenerate_fan_fullscan_netlists.sh` — **deprecated**；改用 `build_itc99_netlists.sh`
- `FAN_ATPG/techlib/mod_nangate45.mdt` — `SDFFR_X1` intern 模型
