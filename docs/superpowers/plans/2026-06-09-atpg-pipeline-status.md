# ATPG Pipeline Status (2026-06-09)

> **Phase C 完成。** G2 **FAIL**（b03 FC 34.75% < 80%）→ **fallback** 敘事。詳見 [`2026-06-09-phase-c-fan-atpg-fix.md`](./2026-06-09-phase-c-fan-atpg-fix.md)。

---

## Phase C 結果摘要

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

### G2 決策

**FAIL** — 進 fallback：partial-scan 主線 + 誠實記錄 FAN full-scan 天花板 ~35% on b03。

---

## 測試

```bash
# C++ unit test
cd FAN_ATPG && ./pkg/core/bin/opt/phase_c_test .

# Full Phase C regression
bash scripts/test_phase_c_atpg.sh
```

---

## 關鍵檔案

| 用途 | 路徑 |
|------|------|
| C1 修復 | `FAN_ATPG/pkg/core/src/atpg.cpp` |
| C++ test | `FAN_ATPG/pkg/core/src/phase_c_test.cpp` |
| Shell regression | `scripts/test_phase_c_atpg.sh` |
| 結果 CSV | `FAN_ATPG/rpt/phase_c_results.csv` |
| 外部對照 | `FAN_ATPG/rpt/b03_external_atpg_comparison.md` |
| 調查報告 | `FAN_ATPG/rpt/b03_investigation_2026-06-09.md` |

---

## 下一步（Phase D / Fallback）

1. 更新 revised-plan Phase D — partial-scan sweep 敘事
2. 不重跑 55-run 直到 fallback 報告 framing 固化
3. MUX2 PODEM 強化（C1.8）留作可選後續，非簡報阻擋項
