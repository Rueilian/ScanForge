#!/usr/bin/env python3
"""Validate FAN full-scan netlists (undriven=0, no OAI/AOI compound)."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ITC_ALL = [
    "b03", "b04", "b05", "b07", "b08", "b09", "b11", "b12", "b13", "b14", "b15",
]

FORBIDDEN_COMPOUND = re.compile(
    r"\b(OAI\d+|AOI\d+|MUX4_|CLKGATE_|FA_X|HA_X)\w*\s+\w+\s*\("
)
BUS_ASSIGN = re.compile(r"assign\s+\w+\s*\[[^\]]+\]\s*=")
MULTI_LITERAL = re.compile(r"\.[A-Z0-9]+\(\s*\d+'[bBhHdDoO]")
CONST_INPUT = re.compile(r"^\s*input\s+_const\d+_\s*;", re.M)
WIRE_AFTER_END = re.compile(r"endmodule\s+wire\s+", re.S)


def drivers_and_wires(text: str) -> tuple[set[str], set[str], set[str], set[str]]:
    inputs = set(re.findall(r"^\s*input\s+(\w+)\s*;", text, re.M))
    outputs = set(re.findall(r"^\s*output\s+(?:reg\s+)?(\w+)\s*;", text, re.M))
    wires = set(re.findall(r"^\s*wire\s+(\w+)\s*;", text, re.M))
    drivers = set()
    for m in re.finditer(r"\.(?:ZN|Z|Q|QN)\(\s*(\w+)\s*\)", text):
        drivers.add(m.group(1))
    for m in re.finditer(r"assign\s+(\w+)\s*=", text):
        drivers.add(m.group(1))
    return inputs, outputs | inputs, wires, drivers


def validate_file(path: Path, fan_smoke: bool, fan_root: Path) -> dict:
    text = path.read_text()
    errors: list[str] = []
    warnings: list[str] = []

    if BUS_ASSIGN.search(text):
        errors.append("V01: bus slice assign remains")
    if MULTI_LITERAL.search(text):
        errors.append("V02: multi-bit literal in port connection")
    if CONST_INPUT.search(text):
        errors.append("V06: orphan _constN_ module input")
    if WIRE_AFTER_END.search(text):
        errors.append("V07: wire declaration after endmodule")
    if FORBIDDEN_COMPOUND.search(text):
        errors.append("V08: forbidden compound cell (OAI/AOI/...)")

    inputs, outputs, wires, drivers = drivers_and_wires(text)
    ref_counts: dict[str, int] = {}
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", text):
        ref_counts[m.group(1)] = ref_counts.get(m.group(1), 0) + 1

    undriven = sorted(w for w in wires if w not in drivers and w not in inputs)
    if undriven:
        errors.append(f"V03: undriven wires ({len(undriven)}): {', '.join(undriven[:8])}")

    unconnected = sorted(
        w
        for w in wires
        if w in drivers
        and w not in inputs
        and w not in outputs
        and ref_counts.get(w, 0) <= 2
    )
    if unconnected:
        errors.append(
            f"V03b: unconnected wires ({len(unconnected)}): {', '.join(sorted(unconnected)[:8])}"
        )

    floating_out = sorted(o for o in outputs if o not in drivers and o not in inputs)
    if floating_out:
        errors.append(f"V04: floating outputs: {', '.join(floating_out[:8])}")

    if path.name.endswith(".v") and "_dffr" not in path.stem and "_reset_tie" not in path.stem:
        if not re.search(r"\bSDFFR_X1\b", text):
            errors.append("V05: no SDFFR_X1 (full-scan)")
        if re.search(r"\bDFFR_X1\b", text):
            errors.append("V05: raw DFFR_X1 remains")
        for port in ("CK", "test_si", "test_se", "test_so"):
            if port not in text:
                errors.append(f"V05: missing scan port {port}")

    mux2 = len(re.findall(r"\bMUX2_X1\b", text))
    result = {
        "file": str(path),
        "pass": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "mux2": mux2,
    }

    if fan_smoke and result["pass"]:
        fan = fan_root / "bin/opt/fan"
        if not fan.exists():
            fan = fan_root / "pkg/fan/bin/opt/fan"
        if fan.exists():
            import tempfile
            script = (
                "read_lib techlib/mod_nangate45.mdt\n"
                f"read_netlist {path.relative_to(fan_root)}\n"
                "build_circuit --frame 1\n"
                "exit\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".script", delete=False) as tf:
                tf.write(script)
                spath = tf.name
            proc = subprocess.run(
                [str(fan), "-f", spath],
                cwd=str(fan_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            Path(spath).unlink(missing_ok=True)
            if proc.returncode != 0:
                errors.append("V09: FAN smoke load failed")
                result["pass"] = False
                result["errors"] = errors
        else:
            warnings.append("V09: fan binary not found; skipped")

    return result


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    nl = repo / "FAN_ATPG/mod_netlist"
    fan_root = repo / "FAN_ATPG"

    ap = argparse.ArgumentParser()
    ap.add_argument("netlist", nargs="?", help="Single netlist path")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", help="Write JSON summary")
    ap.add_argument("--fan-smoke", action="store_true")
    args = ap.parse_args()

    if args.all:
        paths = [nl / f"{c}.v" for c in ITC_ALL]
    elif args.netlist:
        paths = [Path(args.netlist)]
    else:
        ap.error("specify netlist path or --all")

    results = []
    ok = True
    for p in paths:
        if not p.exists():
            print(f"FAIL {p}: missing")
            ok = False
            continue
        r = validate_file(p, args.fan_smoke, fan_root)
        results.append(r)
        status = "PASS" if r["pass"] else "FAIL"
        print(f"{status} {p.name}: mux2={r['mux2']}")
        for e in r["errors"]:
            print(f"  {e}")
        if not r["pass"]:
            ok = False

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=2))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
