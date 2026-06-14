#!/usr/bin/env python3
"""
Convert TTU-format ISCAS'89 gate-level Verilog to NanGate45 format.

TTU format (pld.ttu.ee):
  dff DFF_n(CK, Q, D);          -- positional: clock, output, input
  and AND_n(Y, A, B[, C, D]);   -- positional: output first, then inputs
  or  OR_n (Y, A, B[, C, D]);
  nand NAND_n(Y, A, B[, C, D]);
  nor  NOR_n (Y, A, B[, C, D]);
  not  NOT_n (Y, A);

Output: NanGate45 named-port instantiations + DFFR_X1 with RN=vdd.
After this, run fixup_verilog.py --full-scan to add SDFFR_X1 scan chain.
"""
import re
import sys
from pathlib import Path

# ---- NanGate45 cell mappings ----------------------------------------
# In NanGate45, ALL logic gates use ZN as the output port name (including AND, OR).
# Only BUF_X1 and LOGIC0/1_X1 use Z.
GATE_PREFIX = {"and": "AND", "or": "OR", "nand": "NAND", "nor": "NOR"}

def gate_cell(kind: str, arity: int) -> tuple[str, str]:
    """Return (cell_name, out_port) for a given gate kind and input count."""
    if kind == "not":
        return "INV_X1", "ZN"
    prefix = GATE_PREFIX[kind]
    return f"{prefix}{arity}_X1", "ZN"


# ---- Parser ----------------------------------------------------------

_GATE_RE = re.compile(
    r'^\s*(and|or|nand|nor|not|dff|buf)\s+'  # gate type
    r'(\w+)\s*\(([^)]+)\)\s*;',              # instance_name(ports)
    re.IGNORECASE
)
_MODULE_RE = re.compile(r'^\s*module\s+(\w+)\s*\(')
_INPUT_RE  = re.compile(r'^\s*input\s+(.*?)\s*;')
_OUTPUT_RE = re.compile(r'^\s*output\s+(.*?)\s*;')
_WIRE_RE   = re.compile(r'^\s*wire\s+(.*?)\s*;')


def parse_ports(s: str) -> list[str]:
    return [p.strip() for p in s.split(',') if p.strip()]


def convert(src: str, circuit_name: str) -> str:
    lines = src.splitlines()
    out_lines: list[str] = []

    module_name = circuit_name
    inputs: list[str] = []
    outputs: list[str] = []
    wires: list[str] = []
    dff_lines: list[str] = []   # DFFR_X1 cells (must appear first for FAN's createCircuitPPI)
    comb_lines: list[str] = []  # all other cells
    preamble_done = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Collect multi-line statements
        while line.rstrip().endswith(',') and not line.rstrip().endswith(');'):
            i += 1
            if i >= len(lines):
                break
            line = line.rstrip() + ' ' + lines[i].strip()
        i += 1

        # Module header
        m = _MODULE_RE.match(line)
        if m:
            module_name = circuit_name  # always use circuit name, not s953_bench etc.
            continue

        # Input ports — strip GND/VDD but keep CK
        m = _INPUT_RE.match(line)
        if m:
            ports = parse_ports(m.group(1))
            clean = [p for p in ports if p not in ('GND', 'VDD')]
            if clean:
                inputs.extend(clean)
            continue

        m = _OUTPUT_RE.match(line)
        if m:
            outputs.extend(parse_ports(m.group(1)))
            continue

        m = _WIRE_RE.match(line)
        if m:
            wires.extend(parse_ports(m.group(1)))
            continue

        m = _GATE_RE.match(line)
        if m:
            kind = m.group(1).lower()
            inst = m.group(2)
            raw_ports = parse_ports(m.group(3))

            if kind == 'dff':
                # TTU format: either dff(CK, Q, D) [3-port] or dff(Q, D) [2-port, implicit CK]
                if len(raw_ports) == 3:
                    clk, q, d = raw_ports[0], raw_ports[1], raw_ports[2]
                else:
                    clk, q, d = 'CK', raw_ports[0], raw_ports[1]
                qn = f'_qn_{inst}_'
                # fixup_verilog Pass 8 is patched to never strip .QN() from FF cells
                # DFF cells go to dff_lines so they appear first in the netlist;
                # FAN's createCircuitPPI() requires DFFs to be the first numPPI_ cells.
                dff_lines.append(
                    f'  DFFR_X1 {inst} (.CK({clk}), .D({d}), .Q({q}), .QN({qn}), .RN(vdd));'
                )
                wires.append(qn)

            elif kind in ('and', 'or', 'nand', 'nor'):
                out_net = raw_ports[0]
                in_nets = raw_ports[1:]
                arity = len(in_nets)
                cell, out_port = gate_cell(kind, arity)
                in_ports = ', '.join(f'.A{j+1}({n})' for j, n in enumerate(in_nets))
                comb_lines.append(
                    f'  {cell} {inst} (.{out_port}({out_net}), {in_ports});'
                )
            elif kind == 'not':
                out_net, in_net = raw_ports[0], raw_ports[1]
                comb_lines.append(
                    f'  INV_X1 {inst} (.ZN({out_net}), .A({in_net}));'
                )
            elif kind == 'buf':
                out_net, in_net = raw_ports[0], raw_ports[1]
                comb_lines.append(
                    f'  BUF_X1 {inst} (.Z({out_net}), .A({in_net}));'
                )
            continue

        if re.match(r'^\s*endmodule', line):
            # Ensure CK is declared as input (needed when DFFs use implicit 2-port form)
            if 'CK' not in inputs and any('.CK(CK)' in gl for gl in dff_lines):
                inputs.insert(0, 'CK')
            # Build clean module now
            all_ports = inputs + outputs
            port_str = ', '.join(all_ports)
            out_lines.append(f'module {module_name}({port_str});')
            out_lines.append('')
            for p in inputs:
                out_lines.append(f'  input {p};')
            for p in outputs:
                out_lines.append(f'  output {p};')
            for w in wires:
                out_lines.append(f'  wire {w};')
            out_lines.append('  wire vdd;')
            out_lines.append('')
            # DFF cells MUST appear before combinational cells so FAN's createCircuitPPI()
            # finds them at indices 0..numPPI_-1 when iterating top->getCell(i).
            out_lines.extend(dff_lines)
            # VDD tie cell (LOGIC1_X1) and combinational logic after all DFFs
            out_lines.append('  LOGIC1_X1 _vdd_tie_ (.Z(vdd));')
            out_lines.extend(comb_lines)
            out_lines.append('endmodule')
            continue

        # Skip comment lines and blank lines / unrecognised
        # (endmodule already handled above)

    return '\n'.join(out_lines) + '\n'


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input.v> <output.v> <circuit_name>")
        sys.exit(1)
    inp, out, name = sys.argv[1], sys.argv[2], sys.argv[3]
    src = Path(inp).read_text()
    result = convert(src, name)
    Path(out).write_text(result)
    ff_count = result.count('DFFR_X1')
    print(f"Converted {inp} → {out}  ({ff_count} DFFs)")


if __name__ == '__main__':
    main()
