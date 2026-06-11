#!/usr/bin/env python3
"""Prepare ITC'99 RTL for base-gate Yosys synthesis (manifest-driven)."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ITC_ALL = [
    "b03", "b04", "b05", "b07", "b08", "b09", "b11", "b12", "b13", "b14", "b15",
]


def load_manifest(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def rule_copy(src: Path, dst: Path, _rule: dict) -> None:
    shutil.copy2(src, dst)


def rule_comb_nonblocking_to_blocking(text: str, rule: dict) -> str:
    match_pat = rule["match"]
    idx = text.find(match_pat)
    if idx < 0:
        return text
    begin = text.find("begin", idx)
    if begin < 0:
        return text
    depth = 0
    i = begin
    end = len(text)
    while i < len(text):
        if text.startswith("begin", i):
            depth += 1
            i += 5
            continue
        if text.startswith("end", i) and not text[i + 3 : i + 4].isalnum():
            depth -= 1
            if depth == 0:
                end = i + 3
                break
            i += 3
            continue
        i += 1
    block = text[begin:end]
    fixed = re.sub(r"(?<![<>=!])<=(?=(?![=]))", "=", block)
    return text[:begin] + fixed + text[end:]


def parse_rom_initial(text: str, array: str, depth: int) -> list[int]:
    """Parse ROM[i] = 20'b...; from initial block."""
    values: list[int | None] = [None] * depth
    for m in re.finditer(
        rf"{re.escape(array)}\s*\[\s*(\d+)\s*\]\s*=\s*(\d+)\s*'([bBhHdDoO])([^;]+);",
        text,
    ):
        idx = int(m.group(1))
        base = m.group(3).lower()
        val = m.group(4).strip().replace("_", "")
        if base == "b":
            values[idx] = int(val, 2)
        elif base == "h":
            values[idx] = int(val, 16)
        elif base == "d":
            values[idx] = int(val, 10)
        else:
            values[idx] = int(val, 8)
    if any(v is None for v in values):
        raise ValueError(f"incomplete ROM table for {array}")
    return [int(v) for v in values]


def slice_bits(value: int, msb: int, lsb: int) -> int:
    lo, hi = min(msb, lsb), max(msb, lsb)
    width = hi - lo + 1
    return (value >> lo) & ((1 << width) - 1)


def rule_rom_to_case_table(text: str, rule: dict) -> str:
    array = rule["array"]
    depth = int(rule["depth"])
    width = int(rule.get("width", 20))
    ports = rule["read_ports"]
    table = parse_rom_initial(text, array, depth)

    # Remove array declaration and initial block.
    text = re.sub(
        rf"^\s*reg\s+\[[^\]]+\]\s+{re.escape(array)}\s*\[[^\]]+\]\s*;\s*\n",
        "",
        text,
        flags=re.M,
    )
    text = re.sub(r"initial\s+begin.*?end\s*\n", "", text, flags=re.S)

    addr = "MAR"
    case_blocks: list[str] = []
    for port in ports:
        sig = port["signal"]
        msb, lsb = int(port["msb"]), int(port["lsb"])
        pw = msb - lsb + 1 if msb >= lsb else lsb - msb + 1
        lines = [f"    case ({addr})"]
        for i, val in enumerate(table):
            bits = slice_bits(val, msb, lsb)
            lines.append(f"      {i}: {sig} = {pw}'d{bits};")
        lines.append("      default: ;")
        lines.append("    endcase")
        case_blocks.append("\n".join(lines))

    replacement = "\n".join(case_blocks)
    patterns = [
        rf"{re.escape(ports[0]['signal'])}\s*=\s*{re.escape(array)}\[[^\]]+\]\[[^\]]+\]\s*;",
        rf"{re.escape(ports[1]['signal'])}\s*=\s*{re.escape(array)}\[[^\]]+\]\[[^\]]+\]\s*;",
        rf"{re.escape(ports[2]['signal'])}\s*=\s*{re.escape(array)}\[[^\]]+\]\[[^\]]+\]\s*;",
    ]
    for pat in patterns:
        text = re.sub(pat, replacement, text, count=1)
        replacement = ""  # only inject once
    return text


def rule_memory_sync_read(text: str, rule: dict) -> str:
    array = rule["array"]
    depth = int(rule["depth"])
    width = int(rule["width"])
    addr = rule["addr_signal"]
    dout = rule["data_out_signal"]

    text = re.sub(
        rf"^\s*reg\s+\[[^\]]+\]\s+{re.escape(array)}\s*\[[^\]]+\]\s*;\s*\n",
        "",
        text,
        flags=re.M,
    )

    decls = "\n".join(f"  reg [{width - 1}:0] {array}_{i}_;" for i in range(depth))
    if decls not in text:
        text = re.sub(r"(endmodule)", decls + "\n\\1", text, count=1)

    read_lines = [f"        case ({addr})"]
    for i in range(depth):
        read_lines.append(f"          {i}: {dout} <= {array}_{i}_;")
    read_lines.append("          default: ;")
    read_lines.append("        endcase")
    read_block = "\n".join(read_lines)

    text = re.sub(
        rf"{re.escape(dout)}\s*<=\s*{re.escape(array)}\s*\[\s*{re.escape(addr)}\s*\]\s*;",
        read_block,
        text,
    )

    reset_lines = []
    for i in range(depth):
        reset_lines.append(f"         {array}_{i}_ <= 0;")
    reset_block = "\n".join(reset_lines)
    text = re.sub(
        rf"for\s*\(\s*mar\s*=\s*0\s*;\s*mar\s*<=\s*SIZE_MEM\s*-\s*1\s*;\s*mar\s*=\s*mar\s*\+\s*1\s*\)\s*begin\s*\n\s*"
        rf"{re.escape(array)}\s*\[\s*mar\s*\]\s*<=\s*0;\s*\n\s*end",
        reset_block,
        text,
    )

    write_lines = ["        if(wr == 1'b1) begin", f"          case ({addr})"]
    for i in range(depth):
        write_lines.append(f"            {i}: {array}_{i}_ <= data_in;")
    write_lines.append("            default: ;")
    write_lines.append("          endcase")
    write_lines.append("        end")
    write_block = "\n".join(write_lines)

    text = re.sub(
        rf"if\s*\(\s*wr\s*==\s*1\s*'b1\s*\)\s*begin\s*\n\s*"
        rf"{re.escape(array)}\s*\[\s*{re.escape(addr)}\s*\]\s*<=\s*data_in;\s*\n\s*end",
        write_block,
        text,
    )
    return text


def rule_blocking_to_nonblocking(text: str, rule: dict) -> str:
    signals = rule.get("signals", [])
    for sig in signals:
        # Only inside clocked always blocks: blocking assign to output reg.
        text = re.sub(
            rf"(\b{re.escape(sig)}\s*)=(?![=])",
            r"\1<=",
            text,
        )
    return text


def rule_resolve_multi_driver_ff(text: str, rule: dict) -> str:
    # b15 uses TEMPORARY as scratch in combinational sections; ensure declared as reg.
    sig = rule["signal"]
    width = int(rule.get("width", 32))
    if re.search(rf"reg\s+.*\b{re.escape(sig)}\b", text) is None:
        decl = f"  reg signed [{width - 1}:0] {sig};"
        text = re.sub(r"(endmodule)", decl + "\n\\1", text, count=1)
    return text


RULES = {
    "copy": rule_copy,
    "comb_nonblocking_to_blocking": rule_comb_nonblocking_to_blocking,
    "rom_to_case_table": rule_rom_to_case_table,
    "memory_sync_read": rule_memory_sync_read,
    "blocking_to_nonblocking": rule_blocking_to_nonblocking,
    "resolve_multi_driver_ff": rule_resolve_multi_driver_ff,
}


def apply_rules(text: str, rules: list[dict]) -> str:
    for rule in rules:
        name = rule["rule"]
        if name == "copy":
            continue
        fn = RULES[name]
        if name in ("comb_nonblocking_to_blocking", "rom_to_case_table", "memory_sync_read",
                    "blocking_to_nonblocking", "resolve_multi_driver_ff"):
            text = fn(text, rule)
    return text


def prep_circuit(repo: Path, manifest: dict, circuit: str, check: bool) -> bool:
    src_dir = repo / manifest.get("source_dir", "itc99_rtl")
    out_dir = repo / manifest.get("output_dir", "itc99_synth_rtl")
    out_dir.mkdir(parents=True, exist_ok=True)

    src = src_dir / f"{circuit}.v"
    dst = out_dir / f"{circuit}.v"
    if not src.exists():
        print(f"SKIP {circuit}: missing {src}")
        return False

    rules = manifest.get("circuits", {}).get(circuit, manifest.get("defaults", [{"rule": "copy"}]))
    if not rules:
        rules = manifest.get("defaults", [{"rule": "copy"}])

    text = src.read_text()
    text = apply_rules(text, rules)
    dst.write_text(text)
    print(f"OK prep {circuit} -> {dst}")

    if check:
        yosys = shutil.which("yosys")
        if not yosys:
            print("WARN: yosys not in PATH; skip parse check")
            return True
        proc = subprocess.run(
            [yosys, "-p", f"read_verilog -sv {dst}; hierarchy -check -top {circuit}"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            return False
    return True


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=repo / "scripts/itc99_prep_rules.yaml")
    ap.add_argument("--circuit", action="append", dest="circuits")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true", help="Yosys read_verilog smoke parse")
    args = ap.parse_args()

    manifest = load_manifest(Path(args.manifest))
    circuits = args.circuits or (ITC_ALL if args.all else [])
    if not circuits:
        ap.error("specify --circuit NAME or --all")

    ok = True
    for c in circuits:
        if not prep_circuit(repo, manifest, c, args.check):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
