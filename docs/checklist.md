# ScanForge — Final Handoff Checklist

## 1. Timing Analysis & Non-Scan Mask Generation
- [x] Slack-based timing proxy for FF ranking
- [x] STA-slack extraction flow via OpenSTA
- [x] Non-scan mask export for 5%, 10%, 15%, and 20% ratios
- [x] Batch mask generation across all benchmarks

## 2. Partial-Scan Circuit Modeling
- [x] Scan chain routing after non-scan exclusion
- [x] Scan/non-scan controllability separation (T=1 initial state X)
- [x] Scan/non-scan observability separation (non-scan PPO masking at T=1)
- [x] Time-frame unrolling state preservation (`PPI[t+1] <- PPO[t]`)

## 3. Sequential ATPG Design & Engine Verification
- [x] `PARTIAL_SEQUENTIAL` multi-frame unrolling mode
- [x] MUX2 backtrace and propagation logic
- [x] Multi-frame SAF final-observation-frame target mapping
- [x] Scan PPI multi-frame pattern replay and simulation
- [x] Scan protocol auto-TI mapping for async reset pins

## 4. Sweep Automation & Reporting
- [x] Single-run progressive residual pipeline (T=1 -> T=2 -> T=4)
- [x] Custom residual fault-list loading (`add_fault -f`)
- [x] Fixed-denominator union coverage accounting
- [x] Automated progressive sweep script for all Tier A benchmarks
- [x] Final result dataset validation (`progressive_residual_summary.csv`)
- [ ] Final report figures and charts generation

## 5. Handoff Verification
- [x] Non-interactive ATPG execution (no infinite loop or prompt freeze)
- [x] All Tier A netlists validate and load successfully in FAN_ATPG
- [x] Two-Phase State Justification C++ implementation & compile verification
- [x] Clean Git workspace structure
