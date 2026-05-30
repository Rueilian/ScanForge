#!/usr/bin/env python3
"""
Post-process Yosys-generated Verilog for FAN_ATPG compatibility.
1. Rename escaped identifiers: \\name[n]  -> name_n_
2. Expand bus port/wire declarations: [N:0] name -> individual scalars
3. Replace constant literals (1'b0, 1'h0, etc.) with named input wires
Usage: python3 fixup_verilog.py input.v output.v
"""
import re
import sys

def bits_of(msb, lsb):
    lo, hi = min(msb, lsb), max(msb, lsb)
    return list(range(lo, hi + 1))

def compute_const_names(src):
    """Pre-pass: discover which _constN_ wires will be needed."""
    needed = set()
    for m in re.finditer(r"(\d+)'([bBhHdDoO])([0-9a-fA-FxXzZ_]+)", src):
        size = int(m.group(1))
        base = m.group(2).lower()
        val  = m.group(3).lower()
        if size != 1:
            continue
        if base == 'h':
            int_val = int(val.replace('_',''), 16)
        elif base == 'd':
            int_val = int(val.replace('_',''), 10)
        elif base == 'o':
            int_val = int(val.replace('_',''), 8)
        else:
            int_val = int(val.replace('_',''), 2)
        needed.add((f'_const{int_val}_', int_val))
    return needed

def process(src):
    # ---- Pre-pass: find const nets needed so they can go in module header ----
    needed_const = compute_const_names(src)

    # ---- Pass 1: collect bus signals ----
    bus_decls = {}
    for m in re.finditer(r'\b(input|output|wire)\s+\[(\d+):(\d+)\]\s+(\w+)\s*;', src):
        name = m.group(4)
        msb, lsb = int(m.group(2)), int(m.group(3))
        bus_decls[name] = bits_of(msb, lsb)

    # ---- Pass 2: expand bus declarations ----
    def expand_decl(m):
        kw = m.group(1)
        msb = int(m.group(2))
        lsb = int(m.group(3))
        name = m.group(4)
        bits = bits_of(msb, lsb)
        return '\n'.join(f'  {kw} {name}_{b}_;' for b in bits)

    src = re.sub(r'\b(input|output|wire)\s+\[(\d+):(\d+)\]\s+(\w+)\s*;', expand_decl, src)

    # ---- Pass 3: rename indexed references: name[n] -> name_n_ ----
    if bus_decls:
        names_pat = '|'.join(re.escape(n) for n in bus_decls)
        src = re.sub(r'\b(' + names_pat + r')\[(\d+)\]',
                     lambda m: f'{m.group(1)}_{m.group(2)}_', src)

    # ---- Pass 4: expand module header (const ports are no longer needed — see Pass 7) ----
    def expand_module(m):
        ports = [p.strip() for p in m.group(2).split(',')]
        expanded = []
        for p in ports:
            if p in bus_decls:
                expanded.extend(f'{p}_{b}_' for b in bus_decls[p])
            else:
                expanded.append(p)
        # Append const input ports to module header (REMOVED — use LOGIC0/LOGIC1 cells instead)
        return f'module {m.group(1)}({", ".join(expanded)});'
    src = re.sub(r'module\s+(\w+)\s*\(([^)]+)\)\s*;', expand_module, src)

    # ---- Pass 5: handle escaped identifiers \\name[n] ----
    src = re.sub(r'\\([^\s]+) ', lambda m: m.group(1).replace('[','_').replace(']','_'), src)

    # ---- Pass 6: replace constant port connections with dedicated input wires ----
    # FAN cannot handle constant literals in port connections (e.g. .D(1'h0)).
    # Replace with named module inputs declared in the module header (pre-pass above).
    used_const = set()
    def replace_const(m):
        size_str = m.group(1)
        base = m.group(2).lower()
        val = m.group(3).lower()
        size = int(size_str)
        if base == 'h':
            int_val = int(val.replace('_',''), 16)
        elif base == 'd':
            int_val = int(val.replace('_',''), 10)
        elif base == 'o':
            int_val = int(val.replace('_',''), 8)
        else:
            int_val = int(val.replace('_',''), 2)
        if size == 1:
            name = f'_const{int_val}_'
            used_const.add((name, int_val))
            return name
        return m.group(0)  # leave multi-bit as-is for now
    src = re.sub(r"(\d+)'([bBhHdDoO])([0-9a-fA-FxXzZ_]+)", replace_const, src)

    # ---- Pass 7: instantiate tie cells for constants instead of module inputs ----
    # LOGIC0_X1 / LOGIC1_X1 from NanGate45 provide proper constant sources
    # that FAN_ATPG recognizes as TIEL/TIEH gates, avoiding free-PI issues.
    if used_const:
        insts = []
        for name, val in sorted(used_const):
            if val == 0:
                insts.append(f'  LOGIC0_X1 _tie_{name} (.Z({name}));')
            elif val == 1:
                insts.append(f'  LOGIC1_X1 _tie_{name} (.Z({name}));')
        # Insert just before endmodule
        src = src.rstrip()
        if src.endswith('endmodule'):
            src = src[:-len('endmodule')] + '\n' + '\n'.join(insts) + '\nendmodule'

    return src

if __name__ == '__main__':
    in_path, out_path = sys.argv[1], sys.argv[2]
    with open(in_path) as f:
        src = f.read()
    out = process(src)
    with open(out_path, 'w') as f:
        f.write(out)
