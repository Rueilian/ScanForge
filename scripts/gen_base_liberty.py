#!/usr/bin/env python3
"""Generate NangateOpenCellLibrary_base.lib from typical.lib + allowlist."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def load_allowlist(path: Path) -> list[str]:
    cells: list[str] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            cells.append(line)
    return cells


def extract_cell_blocks(lib_text: str) -> dict[str, str]:
    """Return {cell_name: full cell block including 'cell (...)' line."""
    blocks: dict[str, str] = {}
    for m in re.finditer(r"^\s*cell\s+\(([^)]+)\)\s*\{", lib_text, re.M):
        name = m.group(1).strip()
        start = m.start()
        depth = 0
        i = m.end() - 1
        while i < len(lib_text):
            ch = lib_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks[name] = lib_text[start : i + 1]
                    break
            i += 1
    return blocks


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="in_path",
        default=repo / "FAN_ATPG/techlib/NangateOpenCellLibrary_typical.lib",
    )
    ap.add_argument(
        "--allowlist",
        default=repo / "FAN_ATPG/techlib/base_cells.allowlist",
    )
    ap.add_argument(
        "--out",
        dest="out_path",
        default=repo / "FAN_ATPG/techlib/NangateOpenCellLibrary_base.lib",
    )
    args = ap.parse_args()

    in_path = Path(args.in_path)
    allow_path = Path(args.allowlist)
    out_path = Path(args.out_path)

    allow = load_allowlist(allow_path)
    lib_text = in_path.read_text()
    blocks = extract_cell_blocks(lib_text)

    missing = [c for c in allow if c not in blocks]
    if missing:
        print("ERROR: cells missing from typical.lib:", ", ".join(missing), file=sys.stderr)
        return 1

    header_end = lib_text.find("  cell (")
    if header_end < 0:
        print("ERROR: could not find first cell in liberty", file=sys.stderr)
        return 1
    header = lib_text[:header_end].rstrip() + "\n\n"

    body = "\n\n".join(blocks[c] for c in allow)
    out_text = header + body + "\n\n}\n"
    out_path.write_text(out_text)

    print(f"Wrote {out_path} ({len(allow)} cells)")
    if "MUX2_X1" not in allow:
        print("ERROR: allowlist must include MUX2_X1", file=sys.stderr)
        return 1
    forbidden = [c for c in blocks if re.match(r"^(OAI|AOI)", c)]
    leaked = [c for c in forbidden if c in allow]
    if leaked:
        print("ERROR: OAI/AOI in allowlist:", leaked, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
