#!/usr/bin/env python3
import os
import re
import glob

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RPT_DIR = os.path.join(REPO_ROOT, "FAN_ATPG", "rpt")

def parse_fault_report(filepath):
    results = {
        "targeted": {"DT": 0, "AU": 0, "AB": 0, "TO": 0, "UD": 0, "TI": 0, "RE": 0},
        "untargeted": {"DT": 0, "AU": 0, "AB": 0, "TO": 0, "UD": 0, "TI": 0, "RE": 0}
    }
    total = 0
    if not os.path.exists(filepath):
        return None
        
    with open(filepath) as f:
        for line in f:
            # Match line pattern: #    g=8 l=-4 SA0      UD     _2743_/QN _2743_ (SDFFR_X1)
            m = re.match(r'#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT|TO)\s', line)
            if m:
                total += 1
                gid, fl, ft, st = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
                # PT (possibly testable) maps to UD for our purposes, and TI/RE/etc are mapped as is
                if st == "PT":
                    st = "UD"
                
                category = "targeted" if fl >= 0 else "untargeted"
                if st in results[category]:
                    results[category][st] += 1
                else:
                    results[category][st] = results[category].get(st, 0) + 1
                    
    results["total"] = total
    return results

def main():
    pattern = os.path.join(RPT_DIR, "*_t2_res_faults.txt")
    files = sorted(glob.glob(pattern))
    
    if not files:
        print("No residual fault reports found in", RPT_DIR)
        return
        
    print("| Circuit & Ratio | Total Res Faults | Targeted (l>=0) Status Counts | Untargeted (l<0) Status Counts | Note |")
    print("|---|---|---|---|---|")
    
    for fp in files:
        basename = os.path.basename(fp)
        # Extract circuit name and ratio from b11_x5_t2_res_faults.txt
        m = re.match(r"([a-zA-Z0-9]+)_x(\d+)_t2_res_faults\.txt", basename)
        if not m:
            continue
            
        circuit, ratio = m.group(1), m.group(2)
        tag = f"{circuit}_x{ratio}%"
        
        stats = parse_fault_report(fp)
        if not stats:
            continue
            
        t_stats = stats["targeted"]
        ut_stats = stats["untargeted"]
        
        t_str = f"DT={t_stats['DT']}, AU={t_stats['AU']}, AB={t_stats['AB']}, TO={t_stats['TO']}, UD={t_stats['UD']}"
        ut_str = f"DT={ut_stats['DT']}, AU={ut_stats['AU']}, AB={ut_stats['AB']}, TO={ut_stats['TO']}, UD={ut_stats['UD']}, TI={ut_stats['TI']}"
        
        # Add a note if all UD faults are indeed untargeted
        note = ""
        if t_stats["UD"] == 0 and ut_stats["UD"] > 0:
            note = "All UD are untargeted (l<0)"
        elif t_stats["UD"] == 0 and ut_stats["UD"] == 0:
            note = "Fully resolved targeted/untargeted"
        else:
            note = f"{t_stats['UD']} UD in targeted"
            
        print(f"| {tag} | {stats['total']} | {t_str} | {ut_str} | {note} |")

if __name__ == "__main__":
    main()
