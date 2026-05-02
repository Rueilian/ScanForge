# AGENTS.md

## Cursor Cloud specific instructions

### Overview

ScanForge is a C++ CLI tool for scan chain DFT analysis. It has no web UI, no databases, and no runtime services — it is a pure offline binary that reads `.sf` files and produces analysis reports.

### Build

- **ScanForge engine**: `make -C src` (produces `src/scanforge`). Uses g++ with C++14, no external libraries.
- **FAN_ATPG** (optional submodule): `git submodule update --init && make -C FAN_ATPG -j4`. Requires system packages `bison` and `flex`.

### Run

Pre-generated test data exists at `results/s27.sf`. Use it for quick validation:

```
./src/scanforge results/s27.sf              # full scan analysis
./src/scanforge results/s27.sf --sweep      # partial scan sweep
./src/scanforge --coverage results/s27.sf   # coverage estimation
```

See `README.md` for full CLI reference and `docs/flow_and_results.md` for architecture details.

### Test

There is no automated test suite. Validation is done by running the binary against benchmark `.sf` files and comparing output to the expected results in `README.md` and `docs/flow_and_results.md`.

### Lint

Compilation with `-Wall -Wextra` (already in the Makefile) serves as the linter. There is no separate lint command.

### Gotchas

- `make -C FAN_ATPG` emits many warnings and exits with code 2, but the binary (`FAN_ATPG/bin/opt/fan`) is still produced successfully. Check for the binary rather than relying on the exit code.
- The `results/` directory in the repo root contains pre-generated `.sf` files. `FAN_ATPG/results/` is where newly generated files go when running the ATPG pipeline.
- The `scripts/run_all.sh` script runs both FAN_ATPG and ScanForge on all 12 ISCAS'89 benchmark circuits. It expects both binaries to be built first.
