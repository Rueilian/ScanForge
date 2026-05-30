#!/usr/bin/env python3
"""
Full progressive residual multi-frame ATPG analysis with priority scoring.
Parses fault reports, computes priority scores from netlist graph,
and evaluates top-K recovery for priority vs random ordering.
"""
import re, os, sys, random
from collections import defaultdict, deque


# ── Netlist parsing (from rank_residual_faults.py) ──

class Netlist:
    def __init__(self, path):
        self.gates = {}
        self.pis = set()
        self.pos = set()
        self.wires = set()
        self.fanout_of = defaultdict(set)
        self.fanin_of = defaultdict(set)
        self._parse(path)
        self._build_graph()

    def _parse(self, path):
        with open(path) as f:
            text = f.read()
        for m in re.finditer(r'input\s+(\w+)\s*;', text):
            self.pis.add(m.group(1))
        for m in re.finditer(r'output\s+(\w+)\s*;', text):
            self.pos.add(m.group(1))
        for m in re.finditer(r'wire\s+(\w+)\s*;', text):
            self.wires.add(m.group(1))
        cell_pat = r'^\s+([A-Z]\w+)\s+(\w+)\s*\((.*?)\)\s*;'
        for cm in re.finditer(cell_pat, text, re.MULTILINE | re.DOTALL):
            ctype, cname, conns = cm.group(1), cm.group(2), cm.group(3)
            gate = {'type': ctype, 'inputs': [], 'output': None, 'name': cname}
            for pm in re.finditer(r'\.(\w+)\((\w+)\)', conns):
                port, net = pm.group(1), pm.group(2)
                if port in ('CK', 'CLOCK', 'clock', 'reset', 'RN', 'SN', 'SE', 'SI'):
                    continue
                if port in ('Q', 'QN', 'ZN', 'Z'):
                    gate['output'] = net
                else:
                    gate['inputs'].append(net)
            self.gates[cname] = gate

    def _build_graph(self):
        driver_of = {}
        loads_of = defaultdict(list)
        for name, g in self.gates.items():
            if g['output']:
                driver_of[g['output']] = name
            for inp in g['inputs']:
                loads_of[inp].append(name)
        for name, g in self.gates.items():
            if g['output']:
                for load in loads_of.get(g['output'], []):
                    self.fanout_of[name].add(load)
                    self.fanin_of[load].add(name)

    def dist_to_pos(self, gate_name, max_depth=50):
        if gate_name not in self.gates: return max_depth
        visited = set(); q = deque([(gate_name, 0)])
        while q:
            n, d = q.popleft()
            if d > max_depth: return max_depth
            if n in visited: continue
            visited.add(n)
            g = self.gates.get(n)
            if g and g['output'] and g['output'] in self.pos: return d + 1
            for fo in self.fanout_of.get(n, []): q.append((fo, d + 1))
        return max_depth

    def dist_from_pis(self, gate_name, max_depth=50):
        if gate_name not in self.gates: return max_depth
        visited = set(); q = deque([(gate_name, 0)])
        while q:
            n, d = q.popleft()
            if d > max_depth: return max_depth
            if n in visited: continue
            visited.add(n)
            g = self.gates.get(n)
            if g:
                for inp in g['inputs']:
                    if inp in self.pis: return d + 1
            for fi in self.fanin_of.get(n, []): q.append((fi, d + 1))
        return max_depth

    def local_cone_size(self, gate_name, direction='fanin', max_depth=3):
        visited = set(); q = deque([(gate_name, 0)]); count = 0
        while q:
            n, d = q.popleft()
            if d > max_depth: continue
            if n in visited: continue
            visited.add(n); count += 1
            nb = self.fanin_of.get(n, []) if direction == 'fanin' else self.fanout_of.get(n, [])
            for nn in nb: q.append((nn, d + 1))
        return count


# ── Fault parsing ──

def parse_faults(path):
    """Parse report_fault output. Returns list of (gid, line, ftype, status, gname)."""
    faults = []
    with open(path) as f:
        for line in f:
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT)\s+(.*)', line)
            if m:
                gid = int(m.group(1)); line_no = int(m.group(2))
                ftype = m.group(3); status = m.group(4)
                rest = m.group(5).strip()
                gname = rest.split()[0] if rest else None
                if gname and gname.startswith('('): gname = None
                faults.append((gid, line_no, ftype, status, gname))
    return faults

def fault_key(f):
    return (f[0], f[1], f[2])


def score_fault(gid, line, ftype, status, gname, netlist):
    s = 0.0
    if status == 'AB': s += 3.0
    if gname and gname in netlist.gates:
        obs_d = netlist.dist_to_pos(gname)
        ctrl_d = netlist.dist_from_pis(gname)
        s += max(0, 5 - obs_d) * 0.5
        s += max(0, 5 - ctrl_d) * 0.5
        fi_sz = netlist.local_cone_size(gname, 'fanin', 3)
        fo_sz = netlist.local_cone_size(gname, 'fanout', 3)
        if fi_sz <= 5: s += 1.0
        if fo_sz <= 3: s += 1.0
        if fi_sz > 20: s -= 2.0
        if fo_sz > 10: s -= 1.0
        nfo = len(netlist.fanout_of.get(gname, []))
        if nfo <= 2: s += 1.0
        elif nfo > 10: s -= 1.0
    return s


# ── Analysis ──

def analyze_case(name, netlist_path, t1_path, t2_path, t4_path):
    print(f"\n{'='*70}")
    print(f"Case: {name}")
    print(f"{'='*70}")
    
    t1 = parse_faults(t1_path) if t1_path and os.path.exists(t1_path) else []
    t2 = parse_faults(t2_path) if t2_path and os.path.exists(t2_path) else []
    t4 = parse_faults(t4_path) if t4_path and os.path.exists(t4_path) else []
    
    for label, faults in [("T=1", t1), ("T=2", t2), ("T=4", t4)]:
        if not faults: continue
        dt = sum(1 for f in faults if f[3] == 'DT')
        au = sum(1 for f in faults if f[3] == 'AU')
        ab = sum(1 for f in faults if f[3] == 'AB')
        fc = dt/len(faults)*100 if faults else 0
        print(f"  {label}: FC={fc:.2f}% DT={dt} AU={au} AB={ab} TOTAL={len(faults)}")
    
    all_keys = set()
    for faults in [t1, t2, t4]:
        all_keys |= {fault_key(f) for f in faults}
    denom = len(all_keys)
    
    D1 = {fault_key(f) for f in t1 if f[3] == 'DT'}
    D2 = {fault_key(f) for f in t2 if f[3] == 'DT'}
    D4 = {fault_key(f) for f in t4 if f[3] == 'DT'}
    
    # Build netlist for priority scoring
    netlist = None
    if netlist_path and os.path.exists(netlist_path):
        netlist = Netlist(netlist_path)
    
    # Score residual faults from T=1
    residual = [f for f in t1 if f[3] != 'DT']
    scored = []
    for f in residual:
        s = score_fault(f[0], f[1], f[2], f[3], f[4], netlist) if netlist else 0
        scored.append((s, f))
    scored.sort(key=lambda x: -x[0])
    
    top_scores = scored[:min(20, len(scored))]
    if netlist:
        print(f"\n  Priority scores: min={scored[-1][0]:.1f} max={scored[0][0]:.1f}")
        print(f"  Top 10 prioritized residual:")
        for s, f in top_scores[:10]:
            print(f"    score={s:.1f} g={f[0]} l={f[1]} {f[2]} {f[3]} {f[4] or '?'}")
    
    # Top-K recovery analysis
    if D2 or D4:
        residual_keys = [fault_key(f) for _, f in scored]
        
        # Priority ordering
        for label, D, fault_list in [("T=2", D2, t2), ("T=4", D4, t4)]:
            if not D: continue
            print(f"\n  {label} Top-K recovery (priority order):")
            for K_pct in [10, 25, 50, 100]:
                K = max(1, int(len(residual_keys) * K_pct / 100))
                topK_keys = set(residual_keys[:K])
                recovered = len(D & topK_keys)
                total_D = len(D)
                hit_rate = recovered / total_D * 100 if total_D else 0
                coverage = recovered / K * 100 if K else 0
                print(f"    top {K_pct:>3}% (K={K:>4}): recovered={recovered}/{total_D} ({hit_rate:.0f}%), "
                      f"coverage={coverage:.1f}%")
            
            # Random baseline
            random.seed(42)
            random_keys = residual_keys[:]
            random.shuffle(random_keys)
            print(f"  {label} Top-K recovery (random order):")
            for K_pct in [10, 25, 50, 100]:
                K = max(1, int(len(random_keys) * K_pct / 100))
                topK_keys = set(random_keys[:K])
                recovered = len(D & topK_keys)
                total_D = len(D)
                hit_rate = recovered / total_D * 100 if total_D else 0
                coverage = recovered / K * 100 if K else 0
                print(f"    top {K_pct:>3}% (K={K:>4}): recovered={recovered}/{total_D} ({hit_rate:.0f}%), "
                      f"coverage={coverage:.1f}%")
    
    # AU vs AB split
    au_keys = {fault_key(f) for f in t1 if f[3] == 'AU'}
    ab_keys = {fault_key(f) for f in t1 if f[3] == 'AB'}
    if au_keys or ab_keys:
        print(f"\n  AU vs AB recovery:")
        for label, D in [("T=2", D2), ("T=4", D4)]:
            if not D: continue
            au_recovered = len(D & au_keys)
            ab_recovered = len(D & ab_keys)
            au_rate = au_recovered / len(au_keys) * 100 if au_keys else 0
            ab_rate = ab_recovered / len(ab_keys) * 100 if ab_keys else 0
            print(f"    {label}: AU recovered={au_recovered}/{len(au_keys)} ({au_rate:.1f}%), "
                  f"AB recovered={ab_recovered}/{len(ab_keys)} ({ab_rate:.1f}%)")
    
    # Union coverage
    print(f"\n  --- Union Coverage ---")
    fc_t1 = len(D1)/denom*100 if denom else 0
    union12 = D1 | D2
    union124 = D1 | D2 | D4
    print(f"  FC_T1          = {fc_t1:.2f}%")
    print(f"  FC_union_T1_T2 = {len(union12)/denom*100:.2f}% (+{len(union12-D1):d} faults)")
    print(f"  FC_union_T1_T2_T4 = {len(union124)/denom*100:.2f}% (+{len(union124-union12):d} faults beyond T=2)")
    
    # Naive loss
    print(f"\n  --- Naive Loss ---")
    if D4:
        lost = len(D1 - D4)
        print(f"  T=1 detected but naive T=4 missed: {lost}")
    if D2:
        lost2 = len(D1 - D2)
        print(f"  T=1 detected but naive T=2 missed: {lost2}")


if __name__ == '__main__':
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "FAN_ATPG", "rpt")
    
    for name, netlist, t1f, t2f, t4f in [
        ("b07 x=20%", "../FAN_ATPG/mod_netlist/b07.v", "b07_faults_t1.txt", "b07_x20_t2_faults.txt", "b07_faults_t4.txt"),
        ("b13 x=20%", "../FAN_ATPG/mod_netlist/b13.v", "b13_x20_t1_faults.txt", "b13_x20_t2_faults.txt", "b13_x20_t4_faults.txt"),
    ]:
        netlist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", netlist)
        analyze_case(name, netlist_path,
            os.path.join(base, t1f),
            os.path.join(base, t2f) if os.path.exists(os.path.join(base, t2f)) else None,
            os.path.join(base, t4f) if os.path.exists(os.path.join(base, t4f)) else None)
