#!/usr/bin/env python3
"""FAN smoke: read_lib + read_netlist + build_circuit for each circuit."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ITC_ALL = [
    "b03", "b04", "b05", "b07", "b08", "b09", "b11", "b12", "b13", "b14", "b15",
]


def fan_bin(root: Path) -> Path | None:
    for rel in ("bin/opt/fan", "pkg/fan/bin/opt/fan"):
        p = root / rel
        if p.exists():
            return p
    return None


def smoke(circuits: list[str], fan_root: Path) -> int:
    fan = fan_bin(fan_root)
    if fan is None:
        print("ERROR: fan binary not found", file=sys.stderr)
        return 1
    fail = 0
    for c in circuits:
        nl = f"mod_netlist/{c}.v"
        script = (
            "read_lib techlib/mod_nangate45.mdt\n"
            f"read_netlist {nl}\n"
            "build_circuit --frame 1\n"
            "exit\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".script", delete=False) as tf:
            tf.write(script)
            script_path = tf.name
        try:
            proc = subprocess.run(
                [str(fan), "-f", script_path],
                cwd=str(fan_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            print(f"FAIL {c} (timeout)")
            fail += 1
            continue
        finally:
            Path(script_path).unlink(missing_ok=True)
        if proc.returncode == 0:
            print(f"OK {c}")
        else:
            print(f"FAIL {c}")
            print(proc.stderr or proc.stdout, file=sys.stderr)
            fail += 1
    return 1 if fail else 0


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuits", nargs="*", default=ITC_ALL)
    args = ap.parse_args()
    return smoke(args.circuits, repo / "FAN_ATPG")


if __name__ == "__main__":
    raise SystemExit(main())
