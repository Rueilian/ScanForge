# ITC'99 Netlist Pipeline v2（一勞永逸方案）

> **⚠️ SUPERSEDED** — 請改用 [`2026-06-09-primitive-netlist-pipeline-complete.md`](./2026-06-09-primitive-netlist-pipeline-complete.md)（base-gate synth + MUX2 保留 + partial revert OAI/AOI atomic gates）。
>
> **決策日期：** 2026-06-09  
> **狀態：** 📋 已取代（本文件僅留作 undriven 調查參考）  
> **取代：** 零散手修、`strip→re-fixup`、逐顆 netlist 調試

## 決策摘要

**不再**逐顆修 `mod_netlist/*.v`，也**不**指望單調 Yosys 參數解決全部問題。

改為 **四層可重現 pipeline**，一鍵從 RTL 產出 FAN 可載入、full-scan 合格、FC_scan 可量的 netlist：

```
itc99_rtl/          (原始 benchmark，唯讀)
    ↓ prep_itc99_rtl.py      ← 自動修正合成難點（可重現）
itc99_synth_rtl/
    ↓ synth_itc99.sh v2      ← 統一 Yosys recipe，輸出 _dffr.v
mod_netlist/{c}_dffr.v
    ↓ fixup_verilog.py v2    ← 結構正規化 + scan chain
mod_netlist/{c}.v
    ↓ validate_netlist.py    ← 硬 gate：undriven / 語法 / scan
    ↓ fan smoke load
合格 netlist → ATPG sweep
```

**驗收標準（Done 定義）：**

1. `bash scripts/build_itc99_netlists.sh` 一鍵跑完 11 顆 ITC（b03–b15 缺 b06/b10）
2. `validate_netlist.py` 對全部輸出 **PASS**
3. `fan read_netlist + build_circuit` 對全部 **PASS**
4. `scripts/test_phase_d_atpg.sh` regression **PASS**（b03/s510/tiny 不退化）
5. `run_phase_d_fullscan_dataset.sh` 全 ITC 有 FC_scan 數據（無 empty/timeout 除非 documented）

---

## 問題根因（調查結論）

| 類別 | 根因 | 電路 | Yosys 參數 alone？ |
|------|------|------|-------------------|
| A. RTL 合成難點 | memory/ROM blocking read、blocking/nonblocking 混用、combinational `always` 用 `<=` | b05, b08, b12, b15 | ❌ 需 RTL prep |
| B. Yosys 輸出缺陷 | 合成時即 `used but has no driver`（見 `logs/synth/b08_synth.log` 等） | b08, b12, b15 | ⚠️ 部分（recipe 改善） |
| C. fixup 缺口 | bus slice `assign`、multi-bit literal、SDFFR early-return 跳過修復 | b15, b04(已修) | ❌ 需 fixup v2 |
| D. 流程缺口 | b05 未進 regen、從壞 netlist strip 重跑、無 validator | b05, 全體 | ❌ 需 orchestrator |

**結論：** 一勞永逸 = **A+B 用統一 recipe 壓到最少 + C+D 用工具化 fixup/validate 封死回歸**。

---

## 架構設計

### 目錄結構（新增/變更）

```
itc99_rtl/                    # 原始 ITC'99，不手改
itc99_synth_rtl/              # prep 輸出（git tracked 或 .gitignore + CI 生成）
FAN_ATPG/mod_netlist/
  {c}_dffr.v                  # Yosys 原始輸出（永遠保留）
  {c}.v                       # fixup + full-scan 最終檔
  {c}_reset_tie.v             # 有 reset PI 時自動產生
logs/synth/{c}.log            # 完整 warning（不用 -q）
logs/netlist/{c}.validate.json
scripts/
  build_itc99_netlists.sh     # ★ 唯一入口
  prep_itc99_rtl.py           # RTL 自動預處理
  synth_itc99.sh              # v2 recipe
  fixup_verilog.py            # v2（模組化 pass）
  validate_netlist.py         # ★ 新增
  verify_fullscan_netlist.sh  # 改為呼叫 validator 子集
```

### 原則

1. **`_dffr.v` 為單一真相來源** — fixup 永遠從此出發，禁止 `strip(壞檔)→fixup` 路徑
2. **fail-fast** — validate 不過就不寫入「合格」標記、不進 sweep
3. **可重現** — prep 規則 declarative（YAML/JSON manifest），不手改 gate-level
4. **FC 正確性優先** — 不用 `setundef -zero` 默認綁死 undriven（僅 `--allow-tie-undriven` 除錯用）

---

## Layer 0：RTL Prep（`prep_itc99_rtl.py`）

針對 **Yosys/ABC 無法穩定處理** 的 ITC'99 慣用寫法，用可重現的自動轉換修復。

### Manifest：`scripts/itc99_prep_rules.yaml`

```yaml
# 範例結構
circuits:
  b05:
    - rule: comb_nonblocking_to_blocking
      pattern: "always @(EN_DISP, RES_DISP, NUM, MAX)"
  b08:
    - rule: rom_to_case_table
      array: ROM
      depth: 8
      width: 20
  b15:
    - rule: blocking_to_nonblocking
      signals: [Address, TEMPORARY]
      scope: always_blocks
```

### 具體規則

| 規則 | 目的 | 電路 |
|------|------|------|
| `comb_nonblocking_to_blocking` | `always @(*)` 內 `<=` → `=` | b05 |
| `rom_to_case_table` | `reg [W:0] ROM [0:D]` + `ROM[i]` read → `case(i)` 常數表 | b08 |
| `memory_sync_read` | `memory[addr]` 同步讀寫語意整理 | b12 |
| `blocking_to_nonblocking` | 時序 block 內 `signal = expr` → `signal <= expr` | b15 |
| `split_multi_driver_temp` | 多 driver 暫存器加 mux 顯式化 | b15（若仍 conflicting） |

### 輸出

- 輸入：`itc99_rtl/{c}.v`
- 輸出：`itc99_synth_rtl/{c}.v`
- 無規則的電路：`cp` 原檔（零開銷）

**不修改** `itc99_rtl/` 原始檔；論文可註明「synthesis-compatible RTL derived from ITC'99」。

---

## Layer 1：Yosys Synthesis v2（`synth_itc99.sh`）

### 統一 recipe（取代現行）

```tcl
read_verilog -sv {synth_rtl};
hierarchy -check -top {top};

# 標準化 procedural logic
proc; fsm; opt;

# Memory 展開（在 techmap 前）
memory_map;
memory_dff;          # 若需要
opt;

# Technology mapping
dfflibmap -liberty {lib};
abc -liberty {lib};

# Net 清理（不用 -purge）
splitnets;
opt_clean;           # 移除 -purge
opt;

# 硬檢查（fail = 非零退出）
check -noinit;

write_verilog -noattr {out_dffr};
```

### 變更要點

| 項目 | 舊 | 新 |
|------|----|----|
| 輸入 RTL | `itc99_rtl/` | `itc99_synth_rtl/` |
| 輸出 | 直接 `{c}.v` | **`{c}_dffr.v` only** |
| `opt_clean` | `-purge` | **無 purge** |
| logging | `-q`，多數 log 空 | **完整 log** 到 `logs/synth/{c}.log` |
| fixup | synth 內嵌 | **分離**到 orchestrator |
| 失敗處理 | 繼續下一顆 | **`set -e`**，整批標記失敗 |

### 刻意不做（預設）

- ~~`setundef -undriven -zero`~~ — 會掩蓋問題、扭曲 FC；僅 debug flag 保留

### 電路清單（完整）

```bash
ITC=(b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15)
```

b05 **納入**；與 synth/regen/verify/sweep 對齊。

---

## Layer 2：Fixup v2（`fixup_verilog.py` 重構）

### 模組化 pass 順序

```
P0   rename_clock_to_CK
P1   expand_bus_decls
P2   expand_bus_refs
P3   expand_module_ports
P4   replace_scalar_const_literals
P5   expand_bus_assigns          ★ 新增
P6   insert_const_tie_cells
P7   prune_floating_qn
P8   remove_orphan_wires
P9   fix_orphan_const_inputs
P10  insert_scan_chain            （--no-scan 跳過）
P11  final_wire_sanity
```

### 新增 pass 規格

#### P5 `expand_bus_assigns`

處理 Yosys 輸出、FAN 不支援的語法：

```verilog
assign Address[31:30] = 2'h0;
assign Foo[3:1] = 3'b101;
```

展開為：

```verilog
assign Address_31_ = 1'b0;
assign Address_30_ = 1'b0;
```

multi-bit literal 走既有 `_constN_` / tie cell 路徑。

#### P10 掃描鏈（修正 early-return）

```python
# 舊：見 SDFFR 就 return（跳過 P5–P9）
# 新：僅 skip scan insertion；其餘 pass 一律執行
if scan_insert and not already_has_scan_chain(src):
    src = insert_scan_chain(src)
```

#### P11 `final_wire_sanity`

- 呼叫與 `validate_netlist.py` 相同的 undriven 分析
- `--strict` 模式下 undriven > 0 則 **非零退出**

### CLI 擴充

```bash
python3 fixup_verilog.py IN OUT --full-scan [--strict] [--reset-tie-high]
```

---

## Layer 3：Validator（`validate_netlist.py`）★ 新增

### 檢查項目

| ID | 檢查 | 嚴重度 |
|----|------|--------|
| V01 | 無 `assign sig[hi:lo]` 殘留 | ERROR |
| V02 | 無 multi-bit literal 殘留（`2'h0` 等） | ERROR |
| V03 | 無 undriven internal wire | ERROR |
| V04 | 無 floating output port | ERROR |
| V05 | full-scan：SDFFR>0, DFFR=0, CK, test_si/se/so | ERROR |
| V06 | 無 `input _constN_` orphan | ERROR |
| V07 | 無 `wire` 在 `endmodule` 之後 | ERROR |
| V08 | （可選）`fan -c "read_netlist; build_circuit"` smoke | ERROR |

### 輸出

```bash
python3 scripts/validate_netlist.py FAN_ATPG/mod_netlist/b08.v --json logs/netlist/b08.json
# exit 0 = PASS, 1 = FAIL
```

批次模式：

```bash
python3 scripts/validate_netlist.py --all --glob 'b{03,04,05,07,08,09,11,12,13,14,15}.v'
```

---

## Layer 4：Orchestrator（`build_itc99_netlists.sh`）★ 唯一入口

```bash
#!/usr/bin/env bash
set -euo pipefail
# 1. prep_itc99_rtl.py --all
# 2. synth_itc99.sh
# 3. for c in ITC: fixup {c}_dffr.v → {c}.v [--strict]
# 4. optional reset_tie for reset PI circuits
# 5. validate_netlist.py --all
# 6. verify_fullscan_netlist.sh (thin wrapper)
# 7. print summary table
```

### 摘要表格式

```
circuit | prep | synth | fixup | validate | fan_load | FFs
b03     |  ok  |  ok   |  ok   |   PASS   |   OK     | 30
...
```

---

## 實作階段

### Phase 1 — 骨架（1–2 天）

- [ ] **P1.1** 新增 `scripts/itc99_prep_rules.yaml`（先列 b05/b08/b15 規則）
- [ ] **P1.2** 實作 `prep_itc99_rtl.py`（rule: `comb_nonblocking_to_blocking`）
- [ ] **P1.3** 實作 `validate_netlist.py`（V01–V07）
- [ ] **P1.4** 新增 `build_itc99_netlists.sh` 骨架
- [ ] **P1.5** 更新 `synth_itc99.sh` v2（輸出 `_dffr.v`、新 recipe、完整 log）

**驗收：** 對 b04（已知好）跑通 orchestrator，validate PASS。

### Phase 2 — Fixup v2（1 天）

- [ ] **P2.1** 重構 `fixup_verilog.py` 為 pass 函數
- [ ] **P2.2** 實作 `expand_bus_assigns`（解 b15）
- [ ] **P2.3** 修正 SDFFR early-return
- [ ] **P2.4** `--strict` 整合 validate 邏輯
- [ ] **P2.5** 廢棄 `regenerate_fan_fullscan_netlists.sh` 的 strip 路徑（改為 deprecated wrapper 呼叫 build）

**驗收：** b15 validate PASS + fan load OK。

### Phase 3 — RTL Prep 擴充（1–2 天）

- [ ] **P3.1** `rom_to_case_table` for b08
- [ ] **P3.2** b05 P2 always 修正（已在 P1 若完成則驗證）
- [ ] **P3.3** b15 blocking→nonblocking + 必要時 multi-driver 修復
- [ ] **P3.4** b12 memory 規則（若 synth v2 仍 warning）

**驗收：** b05/b08/b12/b15 全部 validate PASS。

### Phase 4 — 全量重建 + ATPG smoke（1 天）

- [ ] **P4.1** `build_itc99_netlists.sh` 跑完全部 11 顆
- [ ] **P4.2** 更新 `verify_fullscan_netlist.sh` 納入 b05
- [ ] **P4.3** 更新 `run_phase_d_fullscan_dataset.sh` 電路清單
- [ ] **P4.4** 每顆 quick ATPG：`add_fault --all; run_atpg; report_statistics` 取 FC_scan
- [ ] **P4.5** `test_phase_d_atpg.sh` + `phase_d_test` regression

**驗收：** 全 ITC fan load OK；b03≥93% FC_scan 不退化；b07≥94%（D3.3 後）。

### Phase 5 — 文件與 CI（0.5 天）

- [ ] **P5.1** 更新 `docs/AGENTS.md`、`docs/spec.md` pipeline 章節
- [ ] **P5.2** 更新 `docs/final_report.md` Known Blockers（移除已解項）
- [ ] **P5.3** 新增 `docs/superpowers/plans/2026-06-09-atpg-pipeline-status.md` 交叉連結
- [ ] **P5.4** （可選）CI job：`build_itc99_netlists.sh && validate --all`

---

## 測試計劃

### 單元

| 測試 | 檔案 |
|------|------|
| bus assign 展開 | `tests/test_fixup_bus_assign.py` |
| undriven 偵測 | `tests/test_validate_netlist.py` |
| ROM→case | `tests/test_prep_rom.py` |
| comb `<=`→`=` | `tests/test_prep_comb.py` |

### 整合

```bash
# Gate 0: 結構
bash scripts/build_itc99_netlists.sh
python3 scripts/validate_netlist.py --all

# Gate 1: FAN
for c in b03 b04 b05 ...; do
  fan -c "read_lib ...; read_netlist mod_netlist/$c.v; build_circuit --frame 1"
done

# Gate 2: Regression
bash scripts/test_phase_d_atpg.sh

# Gate 3: FC_scan smoke（可併入 sweep）
bash scripts/run_phase_d_fullscan_dataset.sh
```

### 不退化指標

| 電路 | FC_scan 下限 |
|------|-------------|
| b03 | ≥ 93% |
| b07 | ≥ 94% |
| s510 | ≥ 99%，AU=0 |
| tiny_sdffr | ≥ 91%，AU=0 |

---

## 風險與對策

| 風險 | 對策 |
|------|------|
| RTL prep 改變邏輯 | 每條 rule 有 unit test；prep 前後 simulation 比對（可選 formal equiv） |
| b15 太複雜 | 分階段：先能 load，再追 FC；必要時 b15 單獨 document 為 hard circuit |
| 無 Yosys 環境 | AGENTS.md 明確 `~/local/bin/yosys`；build script 開頭檢查 |
| prep 後 FF 數變化 | 重跑 `gen_nonscan_masks.sh`（已在 spec 提及） |
| 論文審稿問「改 RTL」 | manifest 透明；強調 synthesis-compatible encoding，非改功能 |

---

## 廢棄 / 不再維護

| 項目 | 處置 |
|------|------|
| `regenerate_fan_fullscan_netlists.sh` strip 路徑 | deprecated → 呼叫 `build_itc99_netlists.sh --fixup-only` |
| 手改 `mod_netlist/*.v` | 禁止；改 prep rule 或 fixup pass |
| `opt_clean -purge` | 移除 |
| synth 內嵌 fixup | 分離到 orchestrator |
| 逐顆 netlist 調查流程 | 由 validate JSON 取代 |

---

## 時程估計

| Phase | 時間 | 累計 |
|-------|------|------|
| P1 骨架 | 1–2 天 | 2 天 |
| P2 Fixup v2 | 1 天 | 3 天 |
| P3 RTL Prep | 1–2 天 | 5 天 |
| P4 全量 + smoke | 1 天 | 6 天 |
| P5 文件/CI | 0.5 天 | **~6.5 天** |

可並行：P2 fixup 與 P3 prep 不同人/不同 session。

---

## 實作優先順序（若時間壓縮）

**最小可行一勞永逸（3 天）：**

1. `synth v2` + `_dffr.v` 分離
2. `expand_bus_assigns`（b15）
3. `validate_netlist.py`
4. `build_itc99_netlists.sh`
5. b05 加入清單 + b08 `rom_to_case` + b05 comb fix

其餘電路（b09/b11/b13/b14）預期被 **synth v2 去掉 -purge** + **validate 強制** 自動修好；若未修復再補 prep rule。

---

## 相關文件

- [FAN Full-Scan Netlist 規格](./2026-06-09-fan-fullscan-netlist.md)
- [Scan-Protocol FC 指標](./2026-06-09-scan-protocol-fc-metric.md)
- [Phase D PODEM](./2026-06-09-phase-d-podem-fix.md)
- [ATPG Pipeline Status](./2026-06-09-atpg-pipeline-status.md)
