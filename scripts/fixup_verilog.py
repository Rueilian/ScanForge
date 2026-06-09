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

def process(src, scan_insert=False):
    # FAN treats only port name "CK" as clock (excluded from PI). Yosys uses clock/CLOCK.
    for clk_name in ('clock', 'CLOCK', 'clk', 'CLK'):
        src = re.sub(rf'\binput\s+{clk_name}\s*;', 'input CK;', src)
        src = re.sub(rf'\bwire\s+{clk_name}\s*;', 'wire CK;', src)
        src = re.sub(rf'\b{clk_name}\b', 'CK', src)

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

    # ---- Pass 4: expand module header; drop _constN_ ports (tie cells in Pass 7) ----
    def expand_module(m):
        ports = [p.strip() for p in m.group(2).split(',')]
        expanded = []
        for p in ports:
            if re.fullmatch(r'_const\d+_', p):
                continue
            if p in bus_decls:
                expanded.extend(f'{p}_{b}_' for b in bus_decls[p])
            else:
                expanded.append(p)
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

    # ---- Pass 7: wire const nets + LOGIC0/LOGIC1 tie cells (not module inputs) ----
    if used_const:
        wire_decls = []
        insts = []
        for name, val in sorted(used_const):
            wire_decls.append(f'  wire {name};')
            if val == 0:
                insts.append(f'  LOGIC0_X1 _tie_{name} (.Z({name}));')
            elif val == 1:
                insts.append(f'  LOGIC1_X1 _tie_{name} (.Z({name}));')
        src = re.sub(r'\n\s*input\s+_const\d+_;\s*\n', '\n', src)
        src = src.rstrip()
        if src.endswith('endmodule'):
            block = '\n'.join(wire_decls + insts)
            src = src[:-len('endmodule')] + '\n' + block + '\nendmodule'

    # ---- Pass 8: drop .QN() only when the net is otherwise unused ----
    for m in list(re.finditer(r'\.QN\(\s*(\w+)\s*\)', src)):
        net = m.group(1)
        if len(re.findall(rf'\b{re.escape(net)}\b', src)) <= 2:
            src = re.sub(rf',\s*\.QN\(\s*{re.escape(net)}\s*\)', '', src)
            src = re.sub(rf'^\s*wire\s+{re.escape(net)}\s*;\s*\n', '', src, flags=re.M)

    # ---- Pass 9: ensure wires exist for LOGIC tie cells ----
    src = re.sub(r'\nendmodule\s+wire\s+(_const\d+_);\s*$', r'\nendmodule', src)
    for name in sorted(set(re.findall(r'\.Z\((_const\d+_)\)', src))):
        if re.search(rf'\bwire\s+{re.escape(name)}\s*;', src) is None:
            src = src.rstrip()
            if src.endswith('endmodule'):
                src = src[:-len('endmodule')] + f'  wire {name};\nendmodule'

    # ---- Pass 10: orphan _constN_ inputs from prior synth passes ----
    src = fix_orphan_const_inputs(src)

    # ---- Pass 11: scan chain insertion (FAN full-scan + partial-scan) ----
    if not scan_insert:
        return src
    if re.search(r'\bSDFFR_X1\b|\bSDFFS_X1\b|\bSDFFRS_X1\b', src):
        return src

    ff_types = {'DFFR_X1', 'DFFS_X1', 'DFFRS_X1', 'DFFR_X2', 'DFFS_X2', 'DFFRS_X2'}
    ff_type_re = '|'.join(ff_types)
    ff_pattern = re.compile(
        r'(\b(?:' + ff_type_re + r'))\s+(\w+)\s*\((.*?)\)\s*;',
        re.DOTALL
    )

    ff_list = []
    for m in ff_pattern.finditer(src):
        cell_type = m.group(1)
        inst_name = m.group(2)
        body = m.group(3)
        pins = {}
        for pm in re.finditer(r'\.(\w+)\(([^)]*)\)', body):
            pins[pm.group(1)] = pm.group(2).strip()
        if 'Q' in pins:
            ff_list.append({
                'cell_type': cell_type,
                'inst_name': inst_name,
                'q_signal': pins['Q'],
                'full_match': m.group(0),
                'body': body,
            })

    if ff_list:
        ff_list.sort(key=lambda x: x['inst_name'])

        for i, ff in enumerate(ff_list):
            si_signal = 'test_si' if i == 0 else ff_list[i - 1]['q_signal']
            ff['si_signal'] = si_signal

        last_q = ff_list[-1]['q_signal']

        for ff in ff_list:
            scan_type = 'S' + ff['cell_type']
            old_body = ff['body']
            new_body = old_body.rstrip()
            new_body += ',\n    .SE(test_se),\n    .SI(' + ff['si_signal'] + ')\n  '
            new_inst = scan_type + ' ' + ff['inst_name'] + ' (' + new_body + ');'
            src = src.replace(ff['full_match'], new_inst, 1)

        def add_test_ports(m):
            ports = m.group(2).rstrip()
            return (
                f'module {m.group(1)}({ports}, test_si, test_so, test_se);\n'
                '  input test_si;\n'
                '  input test_se;\n'
                '  output test_so;'
            )
        src = re.sub(r'module\s+(\w+)\s*\(([^)]+)\)\s*;', add_test_ports, src, count=1)

        src = re.sub(
            r'(endmodule)',
            '  assign test_so = ' + last_q + ';\n\\1',
            src,
            count=1,
        )

    return src

def fix_orphan_const_inputs(src):
    """Replace stray `input _constN_;` with wire + LOGIC0/LOGIC1 tie cells."""
    orphans = []
    for m in re.finditer(r'^\s*input\s+(_const(\d+)_)\s*;\s*$', src, re.M):
        orphans.append((m.group(1), int(m.group(2))))

    if not orphans:
        return src

    wire_decls = []
    insts = []
    for name, val in orphans:
        src = re.sub(rf'^\s*input\s+{re.escape(name)}\s*;\s*\n', '', src, flags=re.M)
        if re.search(rf'\bwire\s+{re.escape(name)}\s*;', src) is None:
            wire_decls.append(f'  wire {name};')
        tie = '_tie_' + name.strip('_')
        if tie not in src:
            cell = 'LOGIC1_X1' if val == 1 else 'LOGIC0_X1'
            insts.append(f'  {cell} {tie} (.Z({name}));')

    if wire_decls or insts:
        src = src.rstrip()
        if src.endswith('endmodule'):
            block = '\n'.join(wire_decls + insts)
            src = src[:-len('endmodule')] + '\n' + block + '\nendmodule'
    return src

def tie_async_controls_high(src):
    """Deassert active-low async controls during test (RN/SN tied to LOGIC1)."""
    wire_decls = []
    insts = []

    if re.search(r'\.RN\(', src):
        wire_decls.append('  wire _rn_tie_;')
        insts.append('  LOGIC1_X1 _tie_rn (.Z(_rn_tie_));')
        src = re.sub(r'\.RN\([^)]+\)', '.RN(_rn_tie_)', src)

    if re.search(r'\.SN\(', src):
        wire_decls.append('  wire _sn_tie_;')
        insts.append('  LOGIC1_X1 _tie_sn (.Z(_sn_tie_));')
        src = re.sub(r'\.SN\([^)]+\)', '.SN(_sn_tie_)', src)

    if wire_decls:
        src = src.rstrip()
        if src.endswith('endmodule'):
            block = '\n'.join(wire_decls + insts)
            src = src[:-len('endmodule')] + '\n' + block + '\nendmodule'
    return src

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--no-scan', action='store_true',
                    help='Skip scan chain (DFFR only; not valid for FAN full-scan ATPG)')
    ap.add_argument('--scan', action='store_true',
                    help='Insert SDFF scan chain (same as default)')
    ap.add_argument('--full-scan', action='store_true',
                    help='Alias for default scan insertion (FAN standard format)')
    ap.add_argument('--rn-tie-high', action='store_true',
                    help='Tie FF .RN/.SN to LOGIC1 (deassert async controls for test)')
    args = ap.parse_args()
    with open(args.input) as f:
        src = f.read()
    scan_insert = not args.no_scan
    if args.scan or args.full_scan:
        scan_insert = True
    out = process(src, scan_insert=scan_insert)
    if args.rn_tie_high:
        out = tie_async_controls_high(out)
    with open(args.output, 'w') as f:
        f.write(out)
