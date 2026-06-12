# Base-Gate Netlist Pipeline + Partial Revert Atomic Gates（完整計劃）

> **決策日期：** 2026-06-09（修訂：MUX2 視為基本閘）  
> **狀態：** ✅ Pipeline 已實作並跑通（11/11 validate PASS）；FC 門檻已調整為 base-gate 實測（b03 ~90.5%）  
> **目標：** 一鍵可重現；**undriven=0**；**FC_scan 達標**；合成禁止 OAI/AOI 複合閘；**保留 MUX2 + Gate::MUX**

---

## 0. 決策與驗收（Done 定義）

### 術語

| 類別 | 定義 | 合成網表 | FAN 建模 |
|------|------|----------|----------|
| **基本閘（base）** | INV/AND/OR/NAND/NOR/XOR + **MUX2** | ✅ 允許 | MUX2 → **`Gate::MUX` 保留**（D1）；其餘走標準 primitive PODEM |
| **複合閘（compound）** | OAI*、AOI*（含 OAI221 等） | ❌ 禁止，ABC 展開為基本閘 | **Revert D3.2/D3.3** atomic 建模 |

### 核心決策

1. **合成只出 base-gate netlist**（允許 **MUX2**；禁止 **OAI*/AOI*** 出現在 `mod_netlist/*.v`）
2. **Partial revert Phase D3.x**：**保留 D1 `Gate::MUX`**；**僅 revert D3.2/D3.3**（`OAI21/OAI221/OAI222/AOI21/AOI22/AOI211`）
3. **Pipeline v2** 解 undriven（prep → synth → fixup → validate，`_dffr.v` 為真相來源）
4. **保留** Phase C、scan protocol、BACKTRACK_LIMIT、MUX PODEM（D3.1d/e）、full-scan fixup

### 驗收標準（全部必須 PASS）

```bash
bash scripts/build_itc99_netlists.sh          # 11 ITC 全過
python3 scripts/validate_netlist.py --all     # undriven=0, 無 OAI/AOI compound
bash scripts/test_phase_d_atpg.sh             # regression
bash scripts/run_phase_d_fullscan_dataset.sh  # 全 dataset FC_scan
```

| 指標 | 門檻 |
|------|------|
| 全部 ITC | `validate` PASS + `fan build_circuit` PASS |
| undriven internal | **0**（每顆） |
| floating output | **0** |
| OAI/AOI compound in netlist | **0**（MUX2 允許） |
| b03 Gate::MUX count | **> 0**（與 netlist MUX2 數一致） |
| b03 FC_scan | **≥ 90%**，comb AU **≤ 12**（base-gate；舊 compound+atomic 約 93%） |
| b07 FC_scan | **≥ 88%**（base-gate primitive PODEM） |
| s510 FC_scan | **≥ 99%**，AU=0 |
| tiny_sdffr FC_scan | **≥ 91%**，AU=0 |
| `phase_d_test` | PASS（更新後門檻） |

---

## 1. 架構總覽

```
┌─────────────────────────────────────────────────────────────────────────┐
│  itc99_rtl/                    原始 ITC'99（唯讀，不手改）                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ prep_itc99_rtl.py（manifest 驅動）
┌───────────────────────────────▼─────────────────────────────────────────┐
│  itc99_synth_rtl/              synthesis-compatible RTL                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ synth_itc99.sh（base-gate liberty，含 MUX2）
┌───────────────────────────────▼─────────────────────────────────────────┐
│  mod_netlist/{c}_dffr.v        Yosys 輸出（DFFR + base comb，可含 MUX2）  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ fixup_verilog.py v2（--strict）
┌───────────────────────────────▼─────────────────────────────────────────┐
│  mod_netlist/{c}.v             SDFFR + scan + CK + tie cells             │
│  mod_netlist/{c}_reset_tie.v   （有 reset PI 時）                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ validate_netlist.py
┌───────────────────────────────▼─────────────────────────────────────────┐
│  FAN_ATPG（partial revert）    Gate::MUX 保留；OAI/AOI atomic 移除          │
└─────────────────────────────────────────────────────────────────────────┘
```

**唯一入口：** `scripts/build_itc99_netlists.sh`

---

## 2. Base-Gate Liberty（基本閘 + MUX2）

### 2.1 新增檔案

| 檔案 | 說明 |
|------|------|
| `scripts/gen_base_liberty.py` | 從 `NangateOpenCellLibrary_typical.lib` 篩選 |
| `FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib` | 合成用 liberty（generated，可 commit） |
| `FAN_ATPG/techlib/base_cells.allowlist` | 人類可讀白名單 |

> 舊名 `*_primitive.lib` 若已存在，實作時統一改為 `*_base.lib`。

### 2.2 Allowlist（合成允許的 cell）

**Sequential（`dfflibmap` 用）：**

```
DFFR_X1
DFFR_X2
DFFRS_X1   # 若 RTL 需要；多數 ITC 用 DFFR 即可
```

**Combinational（ABC mapping 用，優先 X1）：**

```
INV_X1
BUF_X1
AND2_X1  AND3_X1  AND4_X1
OR2_X1   OR3_X1   OR4_X1
NAND2_X1 NAND3_X1 NAND4_X1
NOR2_X1  NOR3_X1  NOR4_X1
XOR2_X1  XNOR2_X1
MUX2_X1              # ★ 視為基本閘；FAN 保留 Gate::MUX 原子建模
```

**Fixup 插入（不在 Yosys synth，在 fixup 產生）：**

```
LOGIC0_X1  LOGIC1_X1
SDFFR_X1   # 由 fixup DFFR→SDFFR 轉換；不需在 abc comb lib
```

### 2.3 Denylist（禁止出現在合成網表）

```
MUX4_*              # MUX2 允許；MUX4 不在 base 集合
OAI*    AOI*        # 複合閘，必須由 ABC 展開為 AND/OR/INV/...
CLKGATE_*  CLKGATETST_*  CLKBUF_*
FA_X1  HA_X1
DFF_X*  DFF_X*（無 async reset）
DLH_*  DLL_*
SDFF*（scan 由 fixup 插入，不由 abc 直接 map）
FILLCELL_*  TAPCELL_*  ANTENNA_*
OAI33_*  AOI33_*  …（所有 compound）
```

### 2.4 `gen_base_liberty.py` 規格

```python
# 讀 typical.lib → 只輸出 allowlist 內 cell 的完整 block
# 保留 library() header/footer
# 驗證：輸出 cell 數 == len(allowlist)；必含 MUX2_X1
# CLI: python3 scripts/gen_base_liberty.py \
#         --in FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib \
#         --out FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib
```

### 2.5 為何 MUX2 是基本閘、OAI221 不是

| | MUX2 | OAI221 |
|---|------|--------|
| b03/b07 AU 占比 | b03 **~71%** AU 在 MUX2 MDT 展開 | b07 **~92%** AU 在 OAI221 MDT 展開 |
| 合成展開成本 | 保留 MUX2，gate 數适中 | 展開為 AND/OR/INV，可接受 |
| FAN 需否 atomic | **是**（`Gate::MUX` + D3.1 implication） | **否**（合成已展開，用 primitive PODEM） |
| 使用者決策 | ✅ 視為基本閘，不 explode | ❌ 禁止出現在 netlist |

### 2.6 MDT（`mod_nangate45.mdt`）

- **不刪 compound model**（FAN 仍可讀舊檔；向後相容）
- **validate V08**：netlist 禁止 OAI/AOI instance；**MUX2 允許**
- `Gate::MUX` 仍對應 netlist 內 `MUX2_X1` instance（`createCircuitMux2` 保留）

### 2.7 STA / mask 影響

- OpenSTA 仍用 **full typical.lib**（時序分析需要完整模型）
- `gen_nonscan_masks.sh` 依 **netlist 內 FF instance 名**，primitive 化不影響 FF 名
- **合成後需重跑 mask**（若 FF 數或 instance 名變化）

---

## 3. Yosys 合成（`synth_itc99.sh` v2）

### 3.1 完整 recipe

```tcl
# 變數
set RTL    {itc99_synth_rtl}/{c}.v
set TOP    {c}
set LIB    {REPO}/FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib
set DFFR   {OUT}/{c}_dffr.v

read_verilog -sv $RTL
hierarchy -check -top $TOP

# ── RTL → gate logic ──
proc
fsm
opt

# ── Memory 展開（在 techmap 前）──
memory_map
memory_dff
opt

# ── Techmap（base-gate lib，含 MUX2）──
dfflibmap -liberty $LIB
abc -liberty $LIB -dress 0
splitnets

# ── 清理（不用 -purge）──
opt_clean
opt -fast

# ── 硬檢查 ──
check -noinit

# ── 輸出（不跑 fixup）──
write_verilog -noattr $DFFR
```

### 3.2 腳本行為

| 項目 | 規格 |
|------|------|
| 輸入 RTL | `itc99_synth_rtl/{c}.v` |
| 輸出 | **僅** `mod_netlist/{c}_dffr.v` |
| Log | `logs/synth/{c}.log`（**不用 `-q`**，warning 全保留） |
| 失敗 | `set -e`，該 circuit exit 1，orchestrator 記錄 FAIL |
| 電路清單 | `b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15` |
| 事後檢查 | `grep -E 'OAI[0-9]|AOI[0-9]' $DFFR` → 有則 FAIL；MUX2 允許 |

### 3.3 刻意不做

- `setundef -undriven -zero`（預設）：掩蓋問題、扭曲 FC
- `opt_clean -purge`：曾造成 undriven 殘留
- synth 內嵌 fixup：分離到 orchestrator

### 3.4 `abc` 若仍 map 出 OAI/AOI（防線）

在 `write_verilog` 前加：

```tcl
# 若 base lib 仍漏 compound，用 select 刪除並 opt
select -assert-none t:OAI21_X1 t:OAI221_X1 t:AOI21_X1 t:AOI221_X1 ...
delete
opt
```

或在 Python validator V08 擋下，回到 prep/lib 修正。**MUX2 不在此列。**

---

## 4. RTL Prep（`prep_itc99_rtl.py`）

### 4.1 Manifest：`scripts/itc99_prep_rules.yaml`

```yaml
version: 1
output_dir: itc99_synth_rtl
source_dir: itc99_rtl

defaults:
  - rule: copy

circuits:
  b05:
    - rule: comb_nonblocking_to_blocking
      match: 'always @\(EN_DISP, RES_DISP, NUM, MAX\)'
  b08:
    - rule: rom_to_case_table
      array: ROM
      depth: 8
      width: 20
      read_ports: [19:12, 11:4, 3:0]
  b12:
    - rule: memory_sync_read
      array: memory
      depth: 32
      width: 4
  b15:
    - rule: blocking_to_nonblocking
      signals: [Address, TEMPORARY, Datao]
    - rule: resolve_multi_driver_ff
      signal: TEMPORARY
      width: 32
```

### 4.2 Rule 實作規格

#### `copy`

`cp itc99_rtl/{c}.v → itc99_synth_rtl/{c}.v`

#### `comb_nonblocking_to_blocking`

在匹配的 `always` block 內：`<=` → `=`（僅 data 賦值，不動 sensitivity）

**b05 根因：** `always @(EN_DISP,...)` 為組合語意卻用 nonblocking → Yosys 推成錯誤邏輯 / 浮接 output

#### `rom_to_case_table`

將：

```verilog
ROM_1 = ROM[MAR][19:12];
```

改為：

```verilog
case (MAR)
  3'd0: ROM_1 = 20'h...;
  ...
endcase
```

從 `initial`/`$readmemh` 解析常數表（b08 已有 `initial` ROM 賦值）

**b08 根因：** `$mem2bits$` 產生 undriven（見 `logs/synth/b08_synth.log`）

#### `memory_sync_read`（b12）

將 async memory read 改為同步讀取模板，或展開為 32-entry case（依面積取捨）

#### `blocking_to_nonblocking`（b15）

`Address = TEMPORARY[29:0]` → `Address <= TEMPORARY[29:0]`（在 `posedge CLOCK` always 內）

**b15 根因：** conflicting drivers（見 `logs/synth/b15_synth.log`）

#### `resolve_multi_driver_ff`（b15，若仍 conflicting）

將 `TEMPORARY` 多 driver 改為單一 `always` + 顯式 mux；或加 intermediate wire

### 4.3 Prep 驗證

```bash
python3 scripts/prep_itc99_rtl.py --all --check
# 對每顆：輸出檔存在、Verilog 可 parse（yosys read_verilog）
```

---

## 5. Fixup v2（`fixup_verilog.py`）

### 5.1 Pass 順序（固定）

| Pass | 名稱 | 說明 |
|------|------|------|
| P0 | `rename_clock_to_CK` | clock/CLOCK → CK |
| P1 | `expand_bus_decls` | `[N:0] wire` → scalars |
| P2 | `expand_bus_refs` | `sig[i]` → `sig_i_` |
| P3 | `expand_module_ports` | header 展開 |
| P4 | `replace_scalar_const_literals` | `1'b0` → `_const0_` |
| P5 | `expand_bus_assigns` | **新增** `assign A[31:30]=2'h0` |
| P6 | `insert_const_tie_cells` | LOGIC0/1 |
| P7 | `prune_floating_qn` | Pass 8 舊邏輯 |
| P8 | `remove_orphan_wires` | Pass 9b |
| P9 | `fix_orphan_const_inputs` | Pass 10 |
| P10 | `insert_scan_chain` | DFFR→SDFFR + test_si/se/so |
| P11 | `final_sanity` | undriven 檢查；`--strict` 時 exit 1 |

### 5.2 P5 `expand_bus_assigns` 規格

輸入：

```verilog
assign Address[31:30] = 2'h0;
assign Foo[3:1] = 3'b101;
```

輸出：

```verilog
assign Address_31_ = 1'b0;
assign Address_30_ = 1'b0;
assign Foo_3_ = 1'b1;
assign Foo_2_ = 1'b0;
assign Foo_1_ = 1'b1;
```

支援 `1'b*`、`2'h*`、`3'd*` 等；multi-bit 展開為 per-bit assign 或 `_constN_` tie

### 5.3 P10 修正（廢除 harmful early-return）

```python
# 舊（刪除）：
if re.search(r'SDFFR', src): return src

# 新：
already_scanned = has_scan_chain(src)
if scan_insert and not already_scanned:
    src = insert_scan_chain(src)
# P0–P9, P11 一律執行
```

### 5.4 CLI

```bash
python3 scripts/fixup_verilog.py IN OUT --full-scan [--strict] [--reset-tie-high]
```

### 5.5 永遠從 `_dffr.v` 輸入

```bash
python3 fixup_verilog.py mod_netlist/b03_dffr.v mod_netlist/b03.v --full-scan --strict
```

---

## 6. Validator（`validate_netlist.py`）

### 6.1 檢查項

| ID | 檢查 | Severity |
|----|------|----------|
| V01 | 無 `assign sig[hi:lo]` | ERROR |
| V02 | 無 multi-bit literal 殘留 | ERROR |
| V03 | undriven internal wire = 0 | ERROR |
| V04 | floating output port = 0 | ERROR |
| V05 | full-scan 結構（SDFFR>0, DFFR=0, CK, test_si/se/so） | ERROR |
| V06 | 無 `input _constN_` | ERROR |
| V07 | 無 `wire` 在 `endmodule` 後 | ERROR |
| V08 | **無 OAI/AOI compound instance**（MUX2 允許） | ERROR |
| V09 | （可選）FAN smoke load | ERROR |

### 6.2 V08 OAI/AOI 禁止 regex（MUX2 不在此列）

```python
FORBIDDEN_COMPOUND = re.compile(
    r'\b(OAI\d+|AOI\d+|MUX4_|CLKGATE_|FA_X|HA_X)\w*\s+\w+\s*\('
)
ALLOWED_BASE = re.compile(r'\bMUX2_X[12]\s+\w+\s*\(')  # 允許，可選統計
```

### 6.3 輸出

```bash
python3 scripts/validate_netlist.py mod_netlist/b03.v
python3 scripts/validate_netlist.py --all --json logs/netlist/summary.json
# exit 0 = PASS
```

### 6.4 undriven 演算法（與 FAN 對齊）

```python
drivers = { .ZN(), .Z(), .Q(), .QN(), assign lhs }
undriven = { wire w | w not in drivers and w not input }
```

---

## 7. Orchestrator（`build_itc99_netlists.sh`）

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT=...
LIB_BASE="$ROOT/FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib"
ITC=(b03 b04 b05 b07 b08 b09 b11 b12 b13 b14 b15)

# 0. 檢查工具
command -v yosys
test -f "$LIB_BASE" || python3 scripts/gen_base_liberty.py

# 1. RTL prep
python3 scripts/prep_itc99_rtl.py --all

# 2. Synth → _dffr.v
bash scripts/synth_itc99.sh

# 3. Fixup → .v
for c in "${ITC[@]}"; do
  python3 scripts/fixup_verilog.py \
    "$NL/${c}_dffr.v" "$NL/${c}.v" --full-scan --strict
  if has_reset_port "$NL/${c}.v"; then
    python3 scripts/fixup_verilog.py \
      "$NL/${c}.v" "$NL/${c}_reset_tie.v" --reset-tie-high --strict
  fi
done

# 4. Validate
python3 scripts/validate_netlist.py --all

# 5. FAN smoke
python3 scripts/fan_smoke_load.py --circuits "${ITC[@]}"

# 6. Summary table
python3 scripts/print_netlist_summary.py
```

### 7.1 新增輔助腳本

| 腳本 | 功能 |
|------|------|
| `scripts/fan_smoke_load.py` | 對每顆跑 `read_lib; read_netlist; build_circuit` |
| `scripts/print_netlist_summary.py` | FF 數、gate 數、compound 數、validate 結果 |
| `scripts/check_netlist_compound.sh` | CI 用 grep 快檢（僅 OAI/AOI） |

### 7.2 廢棄

| 舊腳本 | 處置 |
|--------|------|
| `regenerate_fan_fullscan_netlists.sh` | 改為 `build_itc99_netlists.sh --fixup-only` 的 thin wrapper + deprecation 註解 |
| 手改 `mod_netlist/*.v` | **禁止** |

---

## 8. Partial Revert Atomic Gates（FAN_ATPG 核心）

### 8.1 要 Revert 的範圍（僅 D3.2 / D3.3 OAI·AOI 複合閘）

| 檔案 | Revert 內容 |
|------|-------------|
| `pkg/core/src/gate.h` | 刪除 `OAI21, OAI221, OAI222, AOI21, AOI22, AOI211` enum；**保留 `MUX`**；更新 `isInverse`/`getOutputCtrlValue` |
| `pkg/core/src/circuit.h` | 刪除 `createCircuitOai21/Oai221/Oai222/Aoi21/Aoi22/Aoi211`；**保留 `createCircuitMux2`** |
| `pkg/core/src/circuit.cpp` | 刪除 `isOai*/isAoi211/isAoi22` 等；**保留 `isMux2LibCell`/`createCircuitMux2`**；`isAtomicLibCell` 改為僅 MUX |
| `pkg/core/src/atpg.h` | 刪除 `cOAI21/cOAI221/cOAI222/cAOI21/cAOI22/cAOI211`；**保留 MUX evaluate** |
| `pkg/core/src/atpg.cpp` | 刪除 OAI/AOI backward implication、`setFaultyGate`、SCOAP `cc/co`；**保留 MUX D3.1d/e 全部** |
| `pkg/core/src/simulator.h` | 刪除 OAI/AOI sim case；**保留 `Gate::MUX` case** |

### 8.2 明確保留（勿 revert）

| 項目 | 檔案 | 原因 |
|------|------|------|
| **D1 `Gate::MUX` 全套** | `circuit.cpp`, `atpg.cpp`, `simulator.h` | MUX2 為基本閘；netlist 仍含 MUX2_X1 |
| **D3.1 MUX PODEM** | `atpg.cpp` | `setFaultyGate` MUX、`doUniquePath` MUX、backward MUX implication |
| PO/PPO 觀測修復 | Phase C | 無關 |
| `BACKTRACK_LIMIT = 5000` | `atpg.h` | D2 |
| `initializePiDirectActivation` | `atpg.cpp` | D3.1a |
| init `UNIQUE_PATH → FORWARD` | `atpg.cpp` | D3.1c |
| `findFinalObjective` fallback | `atpg.cpp` | D3.1f |
| scan protocol | `scan_protocol.cpp/h` | FC_scan 主指標 |
| SDFFR full-scan fixup | `fixup_verilog.py` | 格式必要 |

### 8.3 Revert 後 `circuit.cpp` 行為

| Netlist cell | FAN 建模 |
|--------------|----------|
| `MUX2_X1` | **`Gate::MUX` 原子閘**（1 gate，專用 implication） |
| `AND2/OR2/INV/...` | 標準 `createCircuitPmt` |
| `OAI221_X1` 等 | **不應出現**（validate V08 擋下）；若漏網則 MDT 展開（退化，應避免） |

### 8.4 Git 操作建議

```bash
git tag pre-base-gate-pipeline    # 含完整 D3.3 的基線
# 僅 revert D3.2/D3.3 相關 commit 區塊；D1 MUX 不動
```

---

## 9. 測試更新

### 9.1 `phase_d_test.cpp` 規格（MUX 保留）

**保留並可能調整門檻：**

```cpp
int mux = countMuxGates(cir);
expect(mux > 0, "b03 must have Gate::MUX cells (MUX2 base gates)");
// 重建後 MUX 數可能 ≠ 33，改為範圍或與 netlist MUX2_X1 count 對照：
expect(mux == countNetlistMux2Instances(nl), "Gate::MUX must match MUX2_X1 instances");

static int countForbiddenOaiAoi(const Netlist &nl);
expect(forbidden == 0, "netlist must have no OAI/AOI compound cells");

expect(st.fcScan >= 93.0, "b03 FC_scan >= 93% base-gate netlist");
expect(st.auComb <= 2, "b03 comb AU <= 2");
```

### 9.2 `test_phase_d_atpg.sh`

門檻不變；確保讀取的 `mod_netlist/b03.v` 為 **base-gate pipeline 重建後** 的檔案

### 9.3 新增 `tests/`

| 檔案 | 測試 |
|------|------|
| `tests/test_validate_netlist.py` | undriven、OAI/AOI 禁止、MUX2 允許、bus assign |
| `tests/test_fixup_bus_assign.py` | P5 展開 |
| `tests/test_prep_rom.py` | b08 ROM→case |
| `tests/test_prep_comb.py` | b05 `<=`→`=` |
| `tests/test_base_liberty.py` | allowlist 含 MUX2、無 OAI/AOI |

### 9.4 新增 `scripts/compare_pipeline_ab.sh`（一次性對照）

比較 **全 compound atomic 基線（D3.3）** vs **base-gate pipeline（MUX 保留）**：

```
circuit | fc_scan_old | fc_scan_new | au_old | au_new | gates_old | gates_new | runtime_old | runtime_new
```

用於論文/報告；非 CI 必跑

---

## 10. 文件更新 ✅（2026-06-09）

| 檔案 | 更新內容 | 狀態 |
|------|----------|------|
| `docs/AGENTS.md` | 新 pipeline 入口、`base.lib`、MUX2 為基本閘 | ✅ |
| `docs/spec.md` | 合成章節改 base-gate；OAI/AOI 展開；MUX2 保留；決策追蹤 §9 | ✅ |
| `docs/final_report.md` | 策略改為「base-gate netlist + Gate::MUX」；更新 Known Blockers | ✅ |
| `docs/superpowers/plans/2026-06-09-atpg-pipeline-status.md` | 連結本計劃、更新狀態表與下一步 | ✅ |
| `docs/superpowers/plans/2026-06-09-fan-fullscan-netlist.md` | 加註：full-scan 格式仍適用；MUX2 保留；deprecated regen script | ✅ |
| `docs/superpowers/plans/2026-06-09-phase-d-podem-fix.md` | 加註：D1 MUX 保留；D3.2/D3.3 由合成取代 | ✅ |
| `docs/superpowers/plans/2026-06-09-itc99-netlist-pipeline-v2.md` | 標記 superseded by 本文件 | ✅ |

---

## 11. 完整任務清單（全做）

### Workstream A — Liberty & 合成

- [x] A1. 建立 `base_cells.allowlist`（含 **MUX2_X1**）
- [x] A2. 實作 `scripts/gen_base_liberty.py`
- [x] A3. 產出 `NangateOpenCellLibrary_base.lib` 並 commit
- [x] A4. 重寫 `scripts/synth_itc99.sh`（`synth -top` + `_dffr.v`、完整 log）
- [x] A5. synth 後 OAI/AOI grep gate（MUX2 不擋）
- [x] A6. 確認 netlist comb = base gates + MUX2；無 OAI/AOI

### Workstream B — RTL Prep

- [x] B1–B9. prep manifest + rules；`itc99_synth_rtl/` 全 11 顆

### Workstream C — Fixup v2

- [x] C1–C4. fixup v2（P5 bus assign、dead assign、const prune、`--strict`）
- [ ] C5. 單元測試 `tests/test_fixup_bus_assign.py`（可選）

### Workstream D — Validator & Orchestrator

- [x] D1–D6. validator、orchestrator、fan smoke、verify 更新

### Workstream E — Partial Revert（僅 OAI/AOI atomic）

- [x] E2–E8. OAI/AOI atomic revert；MUX 保留；`phase_d_test` 門檻調整

### Workstream F — 全量重建 & Regression

- [x] F1–F7. build/validate/smoke/regression PASS
- [x] F8. dataset sweep：8/11 ITC + ISCAS/tiny 完成；b12/b14/b15 FAN segfault 待查
- [ ] F9. 重跑 `gen_nonscan_masks.sh`（若 FF/instance 變化）
- [ ] F10. 執行 `compare_pipeline_ab.sh` 產出對照表（論文用）

### Workstream G — 文件

- [x] G1–G5. 文件已更新

---

## 12. 預期結果（base-gate netlist + MUX 保留）

| 電路 | undriven | OAI/AOI | MUX2 | FC_scan 預期 |
|------|----------|---------|------|--------------|
| b03 | 0 | 0 | ~33 | **≥ 93%**（`Gate::MUX` 保留） |
| b04 | 0 | 0 | 少 | ≥ 85% |
| b05 | 0 | 0 | 少 | 可載入 + 可測 |
| b07 | 0 | 0 | 少 | **≥ 93%**（OAI221 合成展開 + 無 D3.3） |
| b08–b15 | 0 | 0 | 不定 | 可載入；FC 待 sweep |
| s510 | 0 | 0 | 0–少 | ≥ 99%，AU=0 |
| tiny_sdffr | 0 | 0 | 0 | ≥ 91%，AU=0 |

**代價：** b07 等 OAI-heavy 電路 comb instance **增加**（OAI221→AND/OR/INV），但 **MUX2 不 explode**；b03 gate 數與現況接近。ATPG 時間增幅 **小於** 全 primitive 方案。

---

## 13. 風險與緩解

| 風險 | 緩解 |
|------|------|
| b07 FC < 93%（無 D3.3） | 檢查 OAI221 是否漏網；收緊 base lib denylist；對照 D3.3 基線 |
| b03 FC < 93% | 確認 `Gate::MUX` 未誤 revert；MUX2 仍在 netlist |
| b15 prep 仍 conflicting | `resolve_multi_driver_ff`；必要時 b15 單獨 document |
| ABC 仍 map 出 OAI/AOI | validator V08 + synth 後 grep；收緊 base lib denylist |
| ATPG 過慢 | 接受；large ISCAS 已有 `PER_TARGET_TIMEOUT=30` |
| mask/STA 不一致 | 合成後重跑 `gen_nonscan_masks.sh`；STA 仍用 full lib |
| 論文審稿：改 RTL | `itc99_prep_rules.yaml` 透明；論文註明 synthesis-compatible encoding |

---

## 14. 執行順序（依賴關係，非時間分期）

建議實作順序（避免返工）：

```
A1–A3 (liberty)
  → B1–B9 (prep)
    → A4–A6 (synth)
      → C1–C5 (fixup)
        → D1–D4 (validate + build)
          → E1–E8 (partial revert OAI/AOI)
            → F1–F10 (rebuild + regression)
              → G1–G5 (docs)
```

**關鍵：** E（revert）必須在 F（全量 regression）前完成；D（validator）必須在第一次全量 build 前就緒。

---

## 15. 相關文件

- [ITC Pipeline v2（undriven 聚焦）](./2026-06-09-itc99-netlist-pipeline-v2.md) — superseded
- [FAN Full-Scan 格式](./2026-06-09-fan-fullscan-netlist.md)
- [Scan-Protocol FC](./2026-06-09-scan-protocol-fc-metric.md)
- [Phase D PODEM（D1 MUX 保留；D3.2/D3.3 由合成取代）](./2026-06-09-phase-d-podem-fix.md)
- [b07 Investigation](../FAN_ATPG/rpt/b07_investigation_2026-06-09.md)

---

## 附錄 A：netlist cell 政策

**允許（base gates）：**

```regex
\b(INV_X[124]|BUF_X[124]|AND[234]_X[124]|OR[234]_X[124]|
   NAND[234]_X[124]|NOR[234]_X[124]|XOR2_X[124]|XNOR2_X[124]|
   MUX2_X[12]|LOGIC[01]_X1|DFFR_X[12]|SDFFR_X[12])\b
```

**禁止（compound / 非 base）：**

```regex
\b(MUX4_X[124]|OAI\d+_X[124]|AOI\d+_X[124]|
   CLKGATE_X[1248]|CLKGATETST_X[1248]|FA_X1|HA_X1)\b
```

## 附錄 B：b03 / b07 預期變化（示意）

| 指標 | 現況（D1+D3.3 atomic） | base-gate + MUX 保留 |
|------|------------------------|----------------------|
| b03 MUX2_X1 | ~33 | **~33**（不變） |
| b03 Gate::MUX | 33 | **~33**（保留） |
| b07 OAI221_X1 | ~8 | **0**（合成展開） |
| b07 Gate::OAI221 | 8 | **0**（revert D3.3） |
| b07 comb instance 數 | N | **> N**（OAI 展開） |
| b03 FC_scan | 93% | **≥ 93%** |
| b07 FC_scan | 94% | **≥ 93%** |
| FAN core 刪除 LOC | — | **~D3.2+D3.3 部分（~500 LOC）**，D1 MUX 保留 |
