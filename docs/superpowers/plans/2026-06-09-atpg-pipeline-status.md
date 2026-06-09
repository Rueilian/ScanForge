# ATPG Pipeline Status (2026-06-09)

## Fixes Landed

### 1. FAN ATPG hang (`std::cin.get`) — **ROOT CAUSE OF "HANG"**
- `FAN_ATPG/pkg/core/src/atpg.cpp`: removed blocking `std::cin.get()` in `storeCurrentAtpgVal()`
- Without this, any `Bug: storeCurrentAtpgVal...` message **freezes** non-interactive runs
- Rebuild required: `cd FAN_ATPG && make -j$(nproc)`

### 2. MDT syntax error
- `mod_nangate45.mdt` had orphaned lines after `SDFFS_X2` (syntax error at line 1582)
- Prevented `read_lib` from loading → all ATPG silently failed

### 3. `fixup_verilog.py`
- `--scan` flag: scan insertion **only for partial-scan** runs (default off for full-scan)
- `test_si/test_se/test_so` declared immediately after module header
- `_constN_` removed from module ports; LOGIC0/LOGIC1 tie cells used instead
- `scripts/verify_scan_netlist.sh` for structural checks

### 4. Minimal experiments (`FAN_ATPG/mod_netlist/tiny_*.v`)
| Circuit | FC | AU |
|---------|-----|-----|
| tiny_dff (SDFF_X1) | 87.5% | 0 |
| tiny_dffr (DFFR_X1 intern) | 87.5% | 0 |
| tiny_loop (2x SDFFR) | 84.6% | 0 |
| s27 | 94.6% | 0 |
| b03 (DFFR, any mdt) | **34.4%** | **950** |

## What Did NOT Fix b03 Coverage

Changing DFFR_X1 from `seq3_2` → `intern + _dff` gives **identical** 34.37% / 950 AU.

Scan insertion (SDFFR) also gives **identical** numbers when ATPG completes.

**Conclusion:** b03 low FC is NOT fixed by mdt cell-model swap alone.

## FAN Design Notes

- `test_si` / `test_se` are **intentionally excluded** from PI count (`circuit.cpp:140`)
- Full-scan uses PPI controllability; scan ports are for shift mode only
- AU on b03 still spans all PIs + most FFs → FAN views most faults as structurally untestable

## Phase A/B Results (2026-06-09 execution)

### Gates passed
| Gate | Result |
|------|--------|
| G0 | ✅ FAN 不 hang（b03 <0.06s） |
| G1 | ✅ s27 FC = 94.55% |
| G2 | ❌ b03 FC 仍 ~34%（見下） |

### Phase B experiments on b03
| Experiment | FC | AU | Verdict |
|------------|-----|-----|---------|
| Baseline (post-fixup) | 34.24% | 956 | — |
| B1 RN tie-high | 34.28% | 954 | 無效 |
| B2 frame=2 | 32.23% | 941 | 更差 |
| clock→CK rename | 34.24% | 956 | PI 6→5，FC 不變 |

### fixup_verilog.py 新增（已套用全部 b*.v）
1. `clock` → `CK`（FAN 只排除名為 CK 的 clock port）
2. `fix_orphan_const_inputs()`：`input _const0_;` → `wire` + LOGIC0 tie cell（修復 b07/b09/b11/b15 parse error）
3. `--rn-tie-high`：FF .RN/.SN 接 LOGIC1

### 全電路 FC 快取（fixup 後，frame=1 full-scan）
| Circuit | FC | AU |
|---------|-----|-----|
| b03 | 34.24% | 956 |
| b04 | 42.25% | 2186 |
| b07 | 44.06% | 1492 |
| b08 | 41.09% | 936 |
| b09 | 34.67% | 1014 |
| b13 | 54.87% | 1050 |

**結論：** G2 未達（b03 < 80%）。AU-dominated 模式不變；pipeline 修復後數字與先前一致，確認是 FAN frame-1 建模天花板，非單一 netlist bug。

## FAN Full-Scan Netlist 格式更新（2026-06-09）

**決策：** ITC full-scan netlist 改為 FAN 標準格式（對齊 `s510`/`s27`），不再使用裸 `DFFR`。

| 項目 | 舊格式 | 新格式（FAN standard） |
|------|--------|------------------------|
| FF | `DFFR_X1` | `SDFFR_X1` + scan chain |
| Ports | 無 scan | `test_si`, `test_se`, `test_so` |
| Clock | `clock` | `CK` |
| fixup | 預設無 scan | **預設 `--full-scan`** |

詳見 [`2026-06-09-fan-fullscan-netlist.md`](./2026-06-09-fan-fullscan-netlist.md)

```bash
bash scripts/regenerate_fan_fullscan_netlists.sh   # PASS (10/10)
bash scripts/verify_fullscan_netlist.sh              # PASS
```

**ATPG（FAN format, frame=1, 2026-06-09 FAN 修復後）：**

| 電路 | FC | AU | 備註 |
|------|-----|-----|------|
| s510 | 94.86% | 60 | 回歸驗證通過 |
| b03 | 34.17% | 957 | `add_scan_chains` ✅；FC 仍低 |
| b07 | ~43% | — | 待重跑 |

**根因分析：** 見 `FAN_ATPG/rpt/b03_investigation_2026-06-09.md`
- `add_scan_chains` segfault：`calSCOAP` 未重置 + PPI 索引錯位
- 低 FC：`CK`/`test_se`/`test_si` 的 `portIndexToGateIndex_` 預設為 0 → 與 `reset`（gate 0）錯接；已修復但仍 ~34%
- **Full-scan 不需討論 frame**：SDFFR+scan 下 full-scan 等價單一 combinational circuit（PPI/PPO），`frame=1` 即標準模型；低 FC 是 combinational 可觀測性 + FAN 限制，非 multi-frame 問題

## Next Investigation Steps

1. ~~RN tied to LOGIC1~~ — 無效
2. ~~frame=2 CAPTURE~~ — 更差
3. ~~clock→CK~~ — 必要但單獨不足
4. ~~DFFR-only full-scan~~ — 改為 SDFFR+scan（本步）
5. 重跑 b03/b07 FC，確認是否接近 s510 水準
6. External ATPG reference — 若 FAN 仍低 FC

## Commands

```bash
# Rebuild FAN
cd FAN_ATPG && make -j$(nproc)

# Structural check (with --scan netlists)
bash scripts/verify_scan_netlist.sh

# Full-scan sanity
cd FAN_ATPG
./bin/opt/fan -f script/fanScripts/b03_dffr_test.script
./bin/opt/fan -f script/fanScripts/s27_debug_fullscan.script

# Regenerate netlist (no scan)
python3 scripts/fixup_verilog.py FAN_ATPG/mod_netlist/b03.v out.v

# Regenerate netlist (partial-scan)
python3 scripts/fixup_verilog.py FAN_ATPG/mod_netlist/b03.v out.v --scan
```
