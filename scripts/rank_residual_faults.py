#!/usr/bin/env python3
"""
Fault priority scoring for residual multi-frame ATPG.
Parses a synthesized Verilog netlist and FAN_ATPG fault report to compute
testability features and rank residual faults for budget-aware targeting.
"""
import re, os, sys, random
from collections import defaultdict, deque

class Netlist:
    """Parse a flat gate-level Verilog netlist."""
    def __init__(self, path):
        self.gates = {}      # name -> {type, inputs: [names], output: name, fanouts: [names]}
        self.pis = set()     # primary input port names
        self.pos = set()     # primary output port names
        self.wires = set()   # all wire names
        self.dffs = set()    # DFF instance names
        self._parse(path)
        self._build_graph()

    def _parse(self, path):
        with open(path) as f:
            text = f.read()

        # Find module ports to identify PIs/POs
        m = re.search(r'module\s+\w+\s*\(([^)]+)\)', text)
        if m:
            ports = [p.strip() for p in m.group(1).split(',')]

        # Input declarations
        for m in re.finditer(r'input\s+(\w+)\s*;', text):
            self.pis.add(m.group(1))
        # Output declarations
        for m in re.finditer(r'output\s+(\w+)\s*;', text):
            self.pos.add(m.group(1))

        # Wire declarations
        for m in re.finditer(r'wire\s+(\w+)\s*;', text):
            self.wires.add(m.group(1))

        # Cell instantiations: TYPE name (.PORT(net), ...);
        cell_pat = r'^\s+([A-Z]\w+)\s+(\w+)\s*\((.*?)\)\s*;'
        for cm in re.finditer(cell_pat, text, re.MULTILINE | re.DOTALL):
            ctype, cname, conns = cm.group(1), cm.group(2), cm.group(3)
            gate = {'type': ctype, 'inputs': [], 'output': None, 'fanouts': [], 'name': cname}
            # Extract .PORT(net) connections
            for pm in re.finditer(r'\.(\w+)\((\w+)\)', conns):
                port, net = pm.group(1), pm.group(2)
                if port in ('CK', 'clock', 'CLOCK', 'reset', 'RN', 'SN', 'SE', 'SI'):
                    continue  # skip control/scan pins
                if port in ('Q', 'QN', 'ZN', 'Z'):
                    gate['output'] = net
                else:
                    gate['inputs'].append(net)
            # DFF detection
            if 'DFF' in ctype:
                # D input is the one that's not Q/QN
                for pm in re.finditer(r'\.(\w+)\((\w+)\)', conns):
                    port, net = pm.group(1), pm.group(2)
                    if port == 'D':
                        gate['inputs'].append(net)  # Ensure D is an input
                        break
            self.gates[cname] = gate
            if 'DFF' in ctype:
                self.dffs.add(cname)

        # Identify output-nets (nets driven by gates)
        for g in self.gates.values():
            if g['output']:
                self.wires.add(g['output'])

    def _build_graph(self):
        """Build forward (driver->loads) and reverse (load->drivers) edges."""
        self.driver_of = {}   # net -> gate_name
        self.loads_of = defaultdict(list)  # net -> [gate_names that use it as input]
        self.fanout_of = defaultdict(set)  # gate -> [downstream gate names]
        self.fanin_of = defaultdict(set)   # gate -> [upstream gate names]

        for name, g in self.gates.items():
            if g['output']:
                self.driver_of[g['output']] = name
            for inp in g['inputs']:
                self.loads_of[inp].append(name)

        for name, g in self.gates.items():
            if g['output']:
                for load in self.loads_of.get(g['output'], []):
                    self.fanout_of[name].add(load)
                    self.fanin_of[load].add(name)

    def dist_to_pos(self, gate_name, max_depth=50):
        """BFS distance from gate to nearest PO/PPO (observability)."""
        if not gate_name:
            return max_depth
        visited = set()
        q = deque([(gate_name, 0)])
        while q:
            n, d = q.popleft()
            if d > max_depth: return max_depth
            if n in visited: continue
            visited.add(n)
            g = self.gates.get(n)
            if g and g['output'] and g['output'] in self.pos:
                return d + 1
            for fo in self.fanout_of.get(n, []):
                q.append((fo, d + 1))
        return max_depth

    def dist_from_pis(self, gate_name, max_depth=50):
        """BFS distance from nearest PI/scan-FF to gate (controllability)."""
        if not gate_name:
            return max_depth
        visited = set()
        q = deque([(gate_name, 0)])
        while q:
            n, d = q.popleft()
            if d > max_depth: return max_depth
            if n in visited: continue
            visited.add(n)
            g = self.gates.get(n)
            # PI: gate has no fanins and its inputs are PI wires, or it IS a PI wire
            if not self.fanin_of.get(n) and g:
                if any(inp in self.pis for inp in g.get('inputs', [])):
                    return d + 1
            # Check if any input wire is a PI
            if g:
                for inp in g.get('inputs', []):
                    if inp in self.pis:
                        return d + 1
            for fi in self.fanin_of.get(n, []):
                q.append((fi, d + 1))
        return max_depth

    def local_cone_size(self, gate_name, direction='fanin', max_depth=3):
        """Count gates in local cone within max_depth."""
        visited = set()
        q = deque([(gate_name, 0)])
        count = 0
        while q:
            n, d = q.popleft()
            if d > max_depth: continue
            if n in visited: continue
            visited.add(n)
            count += 1
            nb = self.fanin_of.get(n, []) if direction == 'fanin' else self.fanout_of.get(n, [])
            for nn in nb:
                q.append((nn, d + 1))
        return count


def score_fault(gid, line, ftype, status, gname, netlist):
    """Score a residual fault for priority ordering."""
    score = 0.0
    
    if status == 'AB':
        score += 3.0
    
    if gname and gname in netlist.gates:
        obs_dist = netlist.dist_to_pos(gname)
        score += max(0, 5 - obs_dist) * 0.5
        
        ctrl_dist = netlist.dist_from_pis(gname)
        score += max(0, 5 - ctrl_dist) * 0.5
        
        fanin_size = netlist.local_cone_size(gname, 'fanin', 3)
        fanout_size = netlist.local_cone_size(gname, 'fanout', 3)
        if fanin_size <= 5: score += 1.0
        if fanout_size <= 3: score += 1.0
        if fanin_size > 20: score -= 2.0
        if fanout_size > 10: score -= 1.0
        
        nfo = len(netlist.fanout_of.get(gname, []))
        if nfo <= 2: score += 1.0
        elif nfo > 10: score -= 1.0
    
    return score


def build_fault_gate_map(netlist_path, fault_report_path):
    """Parse fault report and try to map faults to netlist gate names."""
    netlist = Netlist(netlist_path)
    
    with open(fault_report_path) as f:
        text = f.read()
    
    faults = []
    fault_by_gate = {}
    
    for m in re.finditer(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT)\s+(.*)', text):
        gid = int(m.group(1))
        line_no = int(m.group(2))
        ftype = m.group(3)
        status = m.group(4)
        rest = m.group(5).strip()
        
        # Extract gate/cell name: "start (primary input)" or "_505_ (DFFR_X1)"
        gname = rest.split()[0] if rest else None
        
        faults.append((gid, line_no, ftype, status, gname))
        fault_by_gate[(gid, line_no, ftype)] = gname
    
    return faults, fault_by_gate, netlist


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--netlist', required=True)
    ap.add_argument('--faults', required=True)
    ap.add_argument('--out', default='/dev/stdout')
    args = ap.parse_args()
    
    faults, _, netlist = build_fault_gate_map(args.netlist, args.faults)
    
    # Identify residual faults (not DT)
    residual = [(gid, line, ft, st, gn) for gid, line, ft, st, gn in faults if st != 'DT']
    dt_faults = [(gid, line, ft, st, gn) for gid, line, ft, st, gn in faults if st == 'DT']
    
    # Score residual faults
    scored = []
    for gid, line, ft, st, gn in residual:
        s = score_fault(gid, line, ft, st, gn, netlist)
        scored.append((s, gid, line, ft, st, gn))
    
    # Sort by score descending
    scored.sort(key=lambda x: -x[0])
    
    print(f"Total faults: {len(faults)}")
    print(f"DT faults: {len(dt_faults)}")
    print(f"Residual (AU+AB+UD): {len(residual)}")
    print(f"  AU: {sum(1 for s in scored if s[4] == 'AU')}")
    print(f"  AB: {sum(1 for s in scored if s[4] == 'AB')}")
    print(f"  UD: {sum(1 for s in scored if s[4] == 'UD')}")
    print()
    print(f"Top 20 prioritized residual faults:")
    print(f"{'Score':>8} {'gID':>6} {'Line':>5} {'Type':>5} {'Status':>6} {'Gate':>15}")
    for s, gid, line, ft, st, gn in scored[:20]:
        print(f"{s:8.2f} {gid:>6} {line:>5} {ft:>5} {st:>6} {gn or '?':>15}")
    
    print()
    print(f"Score distribution: min={scored[-1][0]:.1f} max={scored[0][0]:.1f}")
    buckets = [0]*5
    for s, *rest in scored:
        if s >= 4: buckets[0] += 1
        elif s >= 2: buckets[1] += 1
        elif s >= 0: buckets[2] += 1
        elif s >= -2: buckets[3] += 1
        else: buckets[4] += 1
    print(f"  >=4: {buckets[0]},  2-4: {buckets[1]},  0-2: {buckets[2]},  -2-0: {buckets[3]},  <-2: {buckets[4]}")


if __name__ == '__main__':
    main()
