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

    # ---- Pass 5: expand bus slice assigns (e.g. assign Address[31:30] = 2'h0) ----
    src = expand_bus_assigns(src)

    # ---- Pass 6: replace constant port connections with dedicated input wires ----
    # FAN cannot handle constant literals in port connections (e.g. .D(1'h0)).
    # Replace with named module inputs declared in the module header (pre-pass above).
    used_const = set()
    def replace_const(m):
        size_str = m.group(1)
        base = m.group(2).lower()
        val = m.group(3).lower()
        size = int(size_str)
        if any(c in val for c in 'xzXZ?'):
            return m.group(0)
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

    # ---- Pass 8b: drop assign lhs with no fanout (FAN rejects unconnected nets) ----
    src = remove_dead_assigns(src)

    # ---- Pass 9b: remove wire declarations with no connections (e.g. dangling QN nets) ----
    src = remove_orphan_wires(src)

    # ---- Pass 10: orphan _constN_ inputs from prior synth passes ----
    src = fix_orphan_const_inputs(src)
    src = prune_unused_const_ties(src)

    # ---- Pass 11: scan chain insertion (FAN full-scan + partial-scan) ----
    if scan_insert and not has_scan_chain(src):
        src = insert_scan_chain(src)

    return src

def expand_bus_assigns(src):
    """Expand bus-slice and concatenation assigns to per-bit scalar assigns."""

    def lit_to_bits(size, base, val):
        val = val.replace('_', '').lower()
        if any(c in val for c in 'xz?'):
            return None
        if base == 'h':
            ival = int(val, 16)
        elif base == 'd':
            ival = int(val, 10)
        elif base == 'o':
            ival = int(val, 8)
        else:
            ival = int(val, 2)
        bits = []
        for i in range(size - 1, -1, -1):
            bits.append((ival >> i) & 1)
        return bits

    def slice_indices(msb, lsb):
        msb, lsb = int(msb), int(lsb)
        if msb >= lsb:
            return list(range(msb, lsb - 1, -1))
        return list(range(msb, lsb + 1))

    def expand_lhs(expr):
        """Return ordered list of (net, bit_index_or_none) for LHS/RHS concat pieces."""
        expr = expr.strip()
        parts = []
        if expr.startswith('{'):
            inner = expr[1:expr.rfind('}')].strip()
            depth = 0
            cur = []
            for ch in inner:
                if ch == '{':
                    depth += 1
                    cur.append(ch)
                elif ch == '}':
                    depth -= 1
                    cur.append(ch)
                elif ch == ',' and depth == 0:
                    parts.append(''.join(cur).strip())
                    cur = []
                else:
                    cur.append(ch)
            if cur:
                parts.append(''.join(cur).strip())
        else:
            parts = [expr]
        out = []
        for p in parts:
            p = p.strip()
            m = re.fullmatch(r'(\w+)\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]', p)
            if m:
                for b in slice_indices(m.group(2), m.group(3)):
                    out.append(f'{m.group(1)}_{b}_')
                continue
            m = re.fullmatch(r'(\w+)\s*\[\s*(\d+)\s*\]', p)
            if m:
                out.append(f'{m.group(1)}_{m.group(2)}_')
                continue
            m = re.fullmatch(r"(\d+)\s*'([bBhHdDoO])([0-9a-fA-FxXzZ_]+)", p)
            if m:
                bits = lit_to_bits(int(m.group(1)), m.group(2).lower(), m.group(3))
                if bits is None:
                    out.append(p)
                else:
                    out.extend(f"1'b{b}" for b in bits)
                continue
            out.append(p)
        return out

    assign_pat = re.compile(r'^\s*assign\s+(.+?)\s*=\s*(.+?)\s*;\s*$', re.M)

    def repl_assign(m):
        lhs_s, rhs_s = m.group(1), m.group(2)
        if '[' not in lhs_s and '{' not in lhs_s:
            return m.group(0)
        lhs = expand_lhs(lhs_s)
        rhs = expand_lhs(rhs_s)
        if len(lhs) != len(rhs):
            return m.group(0)
        lines = []
        for l, r in zip(lhs, rhs):
            if re.fullmatch(r'\d+\s*\'[bBhHdDoO][0-9a-fA-FxXzZ_]+', l):
                continue
            lines.append(f'assign {l} = {r};')
        return '\n'.join(lines) if lines else m.group(0)

    prev = None
    while prev != src:
        prev = src
        src = assign_pat.sub(repl_assign, src)
    return src

def has_scan_chain(src):
    return bool(re.search(r'\bSDFFR_X1\b|\bSDFFS_X1\b|\bSDFFRS_X1\b', src))

def insert_scan_chain(src):
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

def check_undriven(src):
    """Return list of undriven internal wire names (FAN-aligned heuristic)."""
    inputs = set(re.findall(r'^\s*input\s+(\w+)\s*;', src, re.M))
    wires = set(re.findall(r'^\s*wire\s+(\w+)\s*;', src, re.M))
    drivers = set()
    for m in re.finditer(r'\.(?:ZN|Z|Q|QN)\(\s*(\w+)\s*\)', src):
        drivers.add(m.group(1))
    for m in re.finditer(r'assign\s+(\w+)\s*=', src):
        drivers.add(m.group(1))
    undriven = sorted(w for w in wires if w not in drivers and w not in inputs)
    return undriven

def remove_dead_assigns(src):
    """Remove `assign X = expr` when X has no fanout (wire decl + assign only)."""
    changed = True
    while changed:
        changed = False
        for m in list(re.finditer(r'^\s*assign\s+(\w+)\s*=\s*[^;]+;\s*$', src, re.M)):
            lhs = m.group(1)
            if len(re.findall(rf'\b{re.escape(lhs)}\b', src)) <= 2:
                src = src[:m.start()] + src[m.end():]
                if re.search(rf'^\s*wire\s+{re.escape(lhs)}\s*;', src, re.M):
                    src = re.sub(rf'^\s*wire\s+{re.escape(lhs)}\s*;\s*\n', '', src, flags=re.M)
                changed = True
                break
    return src

def remove_orphan_wires(src):
    """Drop wire declarations that never appear outside their own decl line."""
    wires = re.findall(r'^\s*wire\s+(\w+)\s*;\s*$', src, re.M)
    for name in wires:
        if len(re.findall(rf'\b{re.escape(name)}\b', src)) <= 1:
            src = re.sub(rf'^\s*wire\s+{re.escape(name)}\s*;\s*\n', '', src, flags=re.M)
    return src

def prune_unused_const_ties(src):
    """Remove LOGIC0/1 tie cells when _constN_ has no fanout."""
    for name in set(re.findall(r'_const\d+_', src)):
        refs = len(re.findall(rf'\b{re.escape(name)}\b', src))
        # wire decl + tie only, or orphan tie after wire removal
        if refs <= 2:
            src = re.sub(
                rf'^\s*LOGIC[01]_X1\s+_tie_{re.escape(name)}\s*\(\.Z\({re.escape(name)}\)\)\s*;\s*\n',
                '',
                src,
                flags=re.M,
            )
            src = re.sub(rf'^\s*wire\s+{re.escape(name)}\s*;\s*\n', '', src, flags=re.M)
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

def tie_reset_port_high(src):
    """Convert top-level async reset PI to internal wire tied LOGIC1.

    Matches scan-protocol netlists (e.g. b03_reset_tie.v): reset deasserted
    during shift/capture ATPG; reset stuck-at tested separately.
    """
    for port in ('reset', 'rst', 'nrst', 'arst', 'areset', 'reset_n'):
        if not re.search(rf'^\s*input\s+{re.escape(port)}\s*;', src, re.M):
            continue

        src = re.sub(rf'^\s*input\s+{re.escape(port)}\s*;\s*\n', '', src, flags=re.M)
        if re.search(rf'^\s*wire\s+{re.escape(port)}\s*;', src, re.M) is None:
            src = re.sub(
                r'(module\s+\w+\s*\([^)]*\)\s*;\s*\n)',
                rf'\1  wire {port};\n',
                src,
                count=1,
            )
        src = re.sub(
            rf'module\s+(\w+)\s*\(([^)]*)\)\s*;',
            lambda m, p=port: (
                f'module {m.group(1)}('
                + ', '.join(x.strip() for x in m.group(2).split(',') if x.strip() != p)
                + ');'
            ),
            src,
            count=1,
        )
        tie = f'_tie_{port}'
        if tie not in src:
            src = src.rstrip()
            if src.endswith('endmodule'):
                src = src[:-len('endmodule')] + f'  LOGIC1_X1 {tie} (.Z({port}));\nendmodule'
        break
    return src

def tie_async_controls_high(src):
    """Deassert active-low async controls during test (RN/SN tied to LOGIC1).

    Note: Replacing every .RN(...) leaves reset-distribution INV outputs floating;
    FAN Netlist::check rejects the netlist. Prefer reset-port tie (see b03_reset_tie.v)
    or remove the reset INV cone when using this helper on large designs.
    """
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
        block = '\n'.join(wire_decls + insts) + '\n'
        # Insert after port/wire declarations, before first cell instance.
        cell_start = re.search(
            r'\n\s*(?:[A-Z][A-Z0-9_]*_X\d+\s+\w+\s*\(|assign\s+)',
            src,
        )
        if cell_start:
            pos = cell_start.start() + 1
            src = src[:pos] + block + src[pos:]
        else:
            src = re.sub(r'(module\s+\w+\s*\([^)]*\)\s*;\s*\n)', r'\1' + block, src, count=1)
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
    ap.add_argument('--reset-tie-high', action='store_true',
                    help='Remove reset PI and tie internal reset net to LOGIC1 (scan protocol netlist)')
    ap.add_argument('--strict', action='store_true',
                    help='Exit 1 if undriven wires remain after fixup')
    args = ap.parse_args()
    with open(args.input) as f:
        src = f.read()
    scan_insert = not args.no_scan
    if args.scan or args.full_scan:
        scan_insert = True
    out = process(src, scan_insert=scan_insert)
    if args.reset_tie_high:
        out = tie_reset_port_high(out)
    if args.rn_tie_high:
        out = tie_async_controls_high(out)
    undriven = check_undriven(out)
    if undriven and args.strict:
        print(f'ERROR: undriven wires: {", ".join(undriven)}', file=sys.stderr)
        sys.exit(1)
    with open(args.output, 'w') as f:
        f.write(out)
