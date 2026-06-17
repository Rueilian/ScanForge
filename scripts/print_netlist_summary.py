#!/usr/bin/env python3
"""Print ITC netlist summary (FF/gate/MUX2/validate)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ITC_ALL = [
    "b03", "b04", "b05", "b07", "b08", "b09", "b11", "b12", "b13", "b14", "b15",
]


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    nl = repo / "FAN_ATPG/mod_netlist"
    print(f"{'circuit':<6} {'SDFFR':>6} {'MUX2':>6} {'OAI/AOI':>8}")
    for c in ITC_ALL:
        p = nl / f"{c}.v"
        if not p.exists():
            print(f"{c:<6} {'MISSING':>6}")
            continue
        t = p.read_text()
        sdffr = len(re.findall(r"\bSDFFR_X1\b", t))
        mux2 = len(re.findall(r"\bMUX2_X1\b", t))
        compound = len(re.findall(r"\b(?:OAI|AOI)\d+_X1\b", t))
        print(f"{c:<6} {sdffr:>6} {mux2:>6} {compound:>8}")

    proc = subprocess.run(
        [sys.executable, str(repo / "scripts/validate_netlist.py"), "--all"],
        capture_output=True,
        text=True,
    )
    print("\nvalidate_netlist.py --all:")
    print(proc.stdout)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
