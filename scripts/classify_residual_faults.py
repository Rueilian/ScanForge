#!/usr/bin/env python3
"""
Classify residual faults by their T=1 status and whether T=4 recovers them.

Outputs:
- per-fault classification CSV under results/fault_status/
- per-case summary CSV that shows recovery rate by T=1 status
"""
import argparse
import csv
import os
import re


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "results", "fault_status")
DEFAULT_SUMMARY = os.path.join(REPO_ROOT, "results", "residual_classification_summary.csv")
STATUSES = ("DT", "AU", "AB", "UD", "PT", "TI", "RE", "TO")


def parse_faults(path):
    faults = {}
    with open(path) as f:
        for line in f:
            m = re.match(r"#\s+g=(\d+)\s+l=(-?\d+)\s+(SA[01])\s+(DT|AU|AB|UD|TI|RE|PT|TO)\s*(.*)", line)
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)), m.group(3))
            faults[key] = {
                "gate_id": int(m.group(1)),
                "faulty_line": int(m.group(2)),
                "fault_type": m.group(3),
                "status": m.group(4),
                "location": m.group(5).strip(),
            }
    return faults


def classify_fault(t1_status, later_status):
    if t1_status == "DT":
        return "detected_at_t1"
    if later_status == "DT":
        return f"recovered_from_{t1_status.lower()}"
    if t1_status == "AU":
        return "persistent_au"
    if t1_status == "AB":
        return "persistent_ab"
    if t1_status == "UD":
        return "persistent_ud"
    if t1_status == "TO":
        return "persistent_to"
    return f"persistent_{t1_status.lower()}"


def write_per_fault_csv(rows, path):
    fields = [
        "case",
        "gate_id",
        "faulty_line",
        "fault_type",
        "location",
        "t1_status",
        "t4_status",
        "classification",
        "recovered_by_t4",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_summary(path, row):
    fields = [
        "case",
        "residual_total",
        "t1_au",
        "t1_ab",
        "t1_ud",
        "t1_other",
        "t4_recovered_total",
        "t4_recovered_from_au",
        "t4_recovered_from_ab",
        "t4_recovered_from_ud",
        "t4_recovery_rate_total",
        "t4_recovery_rate_from_au",
        "t4_recovery_rate_from_ab",
        "t4_recovery_rate_from_ud",
        "recommended_filter",
        "note",
    ]
    existed = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not existed:
            writer.writeheader()
        writer.writerow(row)


def pct(numer, denom):
    return round((numer / denom * 100.0), 2) if denom else 0.0


def recommend_filter(n_au, n_ab, n_ud, rec_au, rec_ab, rec_ud):
    au_rate = pct(rec_au, n_au)
    abud_rate = pct(rec_ab + rec_ud, n_ab + n_ud)
    if n_ab + n_ud == 0:
        return "all"
    if au_rate == 0 and abud_rate > 0:
        return "ab-ud-only"
    if au_rate < abud_rate * 0.5:
        return "drop-au"
    return "all"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="Case label, for example b07_x20")
    ap.add_argument("--t1", required=True, help="Path to T=1 fault report")
    ap.add_argument("--t4", required=True, help="Path to T=4 fault report")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Directory for per-fault CSV")
    ap.add_argument("--summary-csv", default=DEFAULT_SUMMARY, help="Summary CSV path")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.summary_csv), exist_ok=True)

    t1 = parse_faults(args.t1)
    t4 = parse_faults(args.t4)

    rows = []
    residual_total = 0
    t1_au = t1_ab = t1_ud = t1_other = 0
    rec_total = rec_au = rec_ab = rec_ud = 0

    for key in sorted(t1.keys()):
        t1_status = t1[key]["status"]
        t4_status = t4.get(key, {}).get("status", "MISSING")
        if t1_status == "DT":
            continue
        residual_total += 1
        if t1_status == "AU":
            t1_au += 1
        elif t1_status == "AB":
            t1_ab += 1
        elif t1_status == "UD":
            t1_ud += 1
        else:
            t1_other += 1

        recovered = t4_status == "DT"
        if recovered:
            rec_total += 1
            if t1_status == "AU":
                rec_au += 1
            elif t1_status == "AB":
                rec_ab += 1
            elif t1_status == "UD":
                rec_ud += 1

        rows.append({
            "case": args.case,
            "gate_id": key[0],
            "faulty_line": key[1],
            "fault_type": key[2],
            "location": t1[key]["location"],
            "t1_status": t1_status,
            "t4_status": t4_status,
            "classification": classify_fault(t1_status, t4_status),
            "recovered_by_t4": int(recovered),
        })

    per_fault_csv = os.path.join(args.out_dir, f"{args.case}_residual_classification.csv")
    write_per_fault_csv(rows, per_fault_csv)

    filter_name = recommend_filter(t1_au, t1_ab, t1_ud, rec_au, rec_ab, rec_ud)
    note = (
        "AU-dominated residuals show weak T4 payoff"
        if filter_name != "all"
        else "T4 recovery is not strongly skewed away from AU"
    )
    append_summary(args.summary_csv, {
        "case": args.case,
        "residual_total": residual_total,
        "t1_au": t1_au,
        "t1_ab": t1_ab,
        "t1_ud": t1_ud,
        "t1_other": t1_other,
        "t4_recovered_total": rec_total,
        "t4_recovered_from_au": rec_au,
        "t4_recovered_from_ab": rec_ab,
        "t4_recovered_from_ud": rec_ud,
        "t4_recovery_rate_total": pct(rec_total, residual_total),
        "t4_recovery_rate_from_au": pct(rec_au, t1_au),
        "t4_recovery_rate_from_ab": pct(rec_ab, t1_ab),
        "t4_recovery_rate_from_ud": pct(rec_ud, t1_ud),
        "recommended_filter": filter_name,
        "note": note,
    })

    print(f"case={args.case}")
    print(f"residual_total={residual_total}")
    print(f"T1 AU/AB/UD/other = {t1_au}/{t1_ab}/{t1_ud}/{t1_other}")
    print(f"T4 recovered total = {rec_total}")
    print(f"T4 recovered from AU/AB/UD = {rec_au}/{rec_ab}/{rec_ud}")
    print(f"recommended_filter={filter_name}")
    print(f"per_fault_csv={per_fault_csv}")
    print(f"summary_csv={args.summary_csv}")


if __name__ == "__main__":
    main()
