#!/usr/bin/env python3
"""
Progressive residual multi-frame ATPG fault overlap analysis.
Parses report_fault output with gateID annotations (g=NN l=NN TYPE STATUS).
Computes union coverage across T=1, T=2, T=4.
"""
import re, sys, os
from collections import defaultdict

FAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "FAN_ATPG")

def parse_faults(rpt_path):
    """Parse report_fault output. Returns list of (gate_id, faulty_line, fault_type, status)."""
    faults = []
    with open(rpt_path) as f:
        for line in f:
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01]|STR|STF)\s+(DT|AU|AB|UD|TI|RE|PT)\s', line)
            if m:
                gid = int(m.group(1))
                line_no = int(m.group(2))
                ftype = m.group(3)
                status = m.group(4)
                faults.append((gid, line_no, ftype, status))
    return faults

def fault_key(f):
    return (f[0], f[1], f[2])  # (gateID, faultyLine, faultType)

def analyze(case_name, t1_path, t2_path, t4_path):
    print(f"\n{'='*60}")
    print(f"Case: {case_name}")
    print(f"{'='*60}")
    
    t1_faults = parse_faults(t1_path) if t1_path else []
    t2_faults = parse_faults(t2_path) if t2_path else []
    t4_faults = parse_faults(t4_path) if t4_path else []
    
    for label, faults in [("T=1", t1_faults), ("T=2", t2_faults), ("T=4", t4_faults)]:
        if not faults:
            print(f"  {label}: NO DATA")
            continue
        dt = sum(1 for f in faults if f[3] == 'DT')
        au = sum(1 for f in faults if f[3] == 'AU')
        ab = sum(1 for f in faults if f[3] == 'AB')
        ud = sum(1 for f in faults if f[3] == 'UD')
        total = len(faults)
        fc = dt / total * 100 if total else 0
        print(f"  {label}: FC={fc:.2f}% DT={dt} AU={au} AB={ab} UD={ud} TOTAL={total}")
    
    all_keys = set()
    for faults in [t1_faults, t2_faults, t4_faults]:
        all_keys |= {fault_key(f) for f in faults}
    
    def set_for(faults, status):
        return {fault_key(f) for f in faults if f[3] == status}
    
    D1 = set_for(t1_faults, 'DT')
    D2 = set_for(t2_faults, 'DT')
    D4 = set_for(t4_faults, 'DT')
    
    A1 = set_for(t1_faults, 'AU')
    A2 = set_for(t2_faults, 'AU')
    A4 = set_for(t4_faults, 'AU')
    
    B1 = set_for(t1_faults, 'AB')
    B2 = set_for(t2_faults, 'AB')
    B4 = set_for(t4_faults, 'AB')
    
    denominator = len(all_keys)
    print(f"\n  Unique physical fault keys: {denominator}")
    
    if not D1:
        print("  No T=1 data to analyze.")
        return
    
    # Overlaps
    print(f"\n  --- Fault Overlap ---")
    print(f"  |D1| = {len(D1)}")
    print(f"  |D2| = {len(D2)}" if D2 else "  |D2| = N/A")
    print(f"  |D4| = {len(D4)}" if D4 else "  |D4| = N/A")
    
    if D2:
        print(f"  |D1 ∩ D2| = {len(D1 & D2)}")
        print(f"  |D1 - D2| = {len(D1 - D2)} (T=1 detected, T=2 missed)")
        print(f"  |D2 - D1| = {len(D2 - D1)} (T=2 newly detected)")
    
    if D4:
        print(f"  |D1 ∩ D4| = {len(D1 & D4)}")
        print(f"  |D1 - D4| = {len(D1 - D4)} (T=1 detected, T=4 missed)")
        print(f"  |D4 - D1| = {len(D4 - D1)} (T=4 newly detected)")
    
    # AB explosion check
    if B1 or B4:
        print(f"\n  --- ABORT Analysis ---")
        if B1: print(f"  |AB T=1| = {len(B1)}")
        if B4: print(f"  |AB T=4| = {len(B4)}")
        if B1 and B4:
            lost_to_ab = len(D1 & B4)
            print(f"  T=1 DT → T=4 AB: {lost_to_ab} faults")
    
    # Residual recovery
    if t1_faults:
        unresolved_all = all_keys - D1
        print(f"\n  --- Residual Recovery ---")
        print(f"  |Unresolved after T=1| = {len(unresolved_all)}")
        
        if D2:
            recovered_t2 = len(D2 & unresolved_all)
            union12 = D1 | D2
            fc12 = len(union12) / denominator * 100
            print(f"  Recovered by T=2: {recovered_t2}")
            print(f"  Union(T1∪T2) FC = {fc12:.2f}%")
        
        if D4:
            recovered_t4 = len(D4 & unresolved_all)
            union124 = D1 | (D2 if D2 else set()) | D4
            fc124 = len(union124) / denominator * 100
            print(f"  Recovered by T=4 (from T=1 residual): {recovered_t4}")
            if D2:
                recovered_t4_after_t2 = len(D4 - (D1 | D2))
                print(f"  Recovered by T=4 beyond T=2: {recovered_t4_after_t2}")
            print(f"  Union(T1∪T2∪T4) FC = {fc124:.2f}%")
    
    # Summary table
    print(f"\n  --- Summary ---")
    print(f"  {'Metric':<30} {'Value'}")
    print(f"  {'-'*30} {'-'*10}")
    print(f"  {'FC_naive_T1':<30} {len(D1)/denominator*100:.2f}%")
    if D2: print(f"  {'FC_naive_T2':<30} {len(D2)/denominator*100:.2f}%")
    if D4: print(f"  {'FC_naive_T4':<30} {len(D4)/denominator*100:.2f}%")
    if D2: print(f"  {'FC_union_T1_T2':<30} {len(D1|D2)/denominator*100:.2f}%")
    if D4: print(f"  {'FC_union_T1_T2_T4':<30} {len(D1|(D2 if D2 else set())|D4)/denominator*100:.2f}%")

if __name__ == '__main__':
    base = os.path.join(FAN_DIR, "rpt")
    
    analyze("s27 x=67%",
        os.path.join(base, "s27_x67_t1_faults.txt"),
        os.path.join(base, "s27_x67_t2_faults.txt") if os.path.exists(os.path.join(base, "s27_x67_t2_faults.txt")) else None,
        os.path.join(base, "s27_x67_t4_faults.txt") if os.path.exists(os.path.join(base, "s27_x67_t4_faults.txt")) else None)
    
    analyze("b07 x=20%",
        os.path.join(base, "b07_x20_t1_faults.txt"),
        os.path.join(base, "b07_x20_t2_faults.txt") if os.path.exists(os.path.join(base, "b07_x20_t2_faults.txt")) else None,
        os.path.join(base, "b07_x20_t4_faults.txt"))
    
    analyze("b13 x=20%",
        os.path.join(base, "b13_x20_t1_faults.txt"),
        os.path.join(base, "b13_x20_t2_faults.txt") if os.path.exists(os.path.join(base, "b13_x20_t2_faults.txt")) else None,
        os.path.join(base, "b13_x20_t4_faults.txt"))
