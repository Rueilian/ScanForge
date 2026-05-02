# ScanForge

**ScanForge** is an open-source scan chain DFT (Design for Testability) flow built on top of [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG).  
It extends FAN_ATPG with a full scan chain insertion module, turning the stub `add_scan_chains` command into a working implementation.

## Features

- **Scan chain insertion** — automatically builds a scan chain from all flip-flops in the circuit
- **Switching activity analysis** — simulates the scan-shift sequence and reports per-FF toggle counts and overall switching activity
- **Multi-circuit support** — tested on ISCAS'89 benchmarks (s27, s208, s1196, …)
- **STIL output** — integrated with FAN_ATPG's existing `write_to_STIL` command

## Repository Structure

```
ScanForge/
├── FAN_ATPG/          # git submodule — Rueilian/FAN_ATPG (fork with scan chain implementation)
├── scripts/           # Example run scripts for ISCAS'89 benchmarks
├── results/           # Sample output: .rpt fault coverage, .stil patterns
├── docs/              # Project report and slides
└── README.md
```

The core implementation lives in the FAN_ATPG submodule:  
[`FAN_ATPG/pkg/fan/src/atpg_cmd.cpp`](FAN_ATPG/pkg/fan/src/atpg_cmd.cpp) — `AddScanChainsCmd::exec()`

## Quick Start

### 1. Clone (with submodule)

```bash
git clone --recurse-submodules https://github.com/Rueilian/ScanForge.git
cd ScanForge
```

### 2. Build

```bash
cd FAN_ATPG
sudo apt install bison flex   # if not installed
make
cd ..
```

### 3. Run

```bash
cd FAN_ATPG
./bin/opt/fan -f ../scripts/atpg_s27.script
```

Expected output (s27 — 3 FFs, 5 patterns):

```
#  Add Scan Chains
#    Number of flip-flops: 3
#    Scan chain (SI → U_G5 → U_G6 → U_G7 → SO)
#    Test patterns:        5
#    Total shift cycles:   15
#    Total toggles:        16
#    Switching activity:   0.3556
#    Per-FF toggle count:
#      [  0] U_G5: 5
#      [  1] U_G6: 6
#      [  2] U_G7: 5
```

## Supported Circuits

All ISCAS'89 Verilog netlists bundled in `FAN_ATPG/mod_netlist/`:

| Circuit | FFs | Gates |
|---------|-----|-------|
| s27     | 3   | 10    |
| s208    | 8   | ~100  |
| s1196   | 18  | ~500  |
| s5378   | 179 | ~2000 |
| s15850  | 534 | ~9000 |

## How It Works

### Scan Chain Flow

```
build_circuit  →  add_fault  →  run_atpg  →  add_scan_chains  →  write_to_STIL
```

The `add_scan_chains` command:
1. Extracts all PPI gates (flip-flops) from the circuit in order
2. Builds a single scan chain: SI → FF[0] → FF[1] → … → FF[N-1] → SO
3. Simulates the scan-shift sequence across all test patterns
4. Reports switching activity (useful for partial scan / chain reordering optimization)

### Switching Activity Calculation

For each test pattern, N shift cycles load the PPI values into the scan chain.  
At each shift, every FF either holds its value or toggles.  
Switching activity = total toggles / (N_FF × total_shift_cycles).

## Based On

- [FAN_ATPG](https://github.com/NTU-LaDS-II/FAN_ATPG) — NTU Laboratory of Dependable Systems, MIT License
- ISCAS'89 benchmark circuits

## License

MIT License — see [LICENSE](LICENSE).
