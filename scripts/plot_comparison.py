#!/usr/bin/env python3
import csv
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG_DIR = os.path.join(REPO, "docs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

BASE_CSV = os.path.join(REPO, "results", "progressive_residual_summary.csv")
TWOPHASE_CSV = os.path.join(REPO, "results", "progressive_residual_summary_two_phase.csv")

def load_data(csv_path):
    data = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            c = row["circuit"]
            r = int(float(row["ratio"]) * 100)
            if c not in data:
                data[c] = {}
            data[c][r] = {
                "t1": float(row["FC_T1"]),
                "t124": float(row["FC_T1_T2_T4"]),
                "gain": float(row["total_gain_pp"]),
            }
    return data

base_data = load_data(BASE_CSV)
tp_data = load_data(TWOPHASE_CSV)

circuits = ["b07", "b13"]
ratios = [5, 10, 15, 20]

fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

colors = {
    "t1": "#4f5b66",       # Charcoal Gray
    "base": "#a7adba",     # Light Slate Gray
    "tp": "#3498db"        # Vibrant Blue
}

for idx, c in enumerate(circuits):
    ax = axes[idx]
    
    t1_vals = [base_data[c][r]["t1"] for r in ratios]
    base_vals = [base_data[c][r]["t124"] for r in ratios]
    tp_vals = [tp_data[c][r]["t124"] for r in ratios]
    
    x = np.arange(len(ratios))
    w = 0.25
    
    rects1 = ax.bar(x - w, t1_vals, w, label='T=1 (Baseline)', color=colors["t1"])
    rects2 = ax.bar(x, base_vals, w, label='T=1→T=4 (Standard TFE)', color=colors["base"])
    rects3 = ax.bar(x + w, tp_vals, w, label='T=1→T=4 (Two-Phase)', color=colors["tp"])
    
    ax.set_title(f"Benchmark {c.upper()}", fontsize=12, fontweight='bold')
    ax.set_xlabel('Non-Scan FF Ratio (%)')
    if idx == 0:
        ax.set_ylabel('Fault Coverage (%)')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r}%" for r in ratios])
    ax.set_ylim(0, 80)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Annotate gains
    for i in range(len(ratios)):
        base_gain = base_vals[i] - t1_vals[i]
        tp_gain = tp_vals[i] - t1_vals[i]
        
        # Two-Phase gain annotation
        ax.annotate(f"+{tp_gain:.2f}%",
                    xy=(x[i] + w, tp_vals[i]),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, color=colors["tp"], fontweight='bold')
        
        # Standard gain annotation
        if base_gain > 0.1:
            ax.annotate(f"+{base_gain:.2f}%",
                        xy=(x[i], base_vals[i]),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, color="#555555")

axes[0].legend(loc="upper right")
plt.suptitle("Sequential ATPG Coverage Comparison: Standard TFE vs. Two-Phase State Justification", fontsize=14, fontweight='bold', y=0.98)
plt.tight_layout()

out_path = os.path.join(FIG_DIR, "two_phase_comparison.png")
plt.savefig(out_path, dpi=150)
plt.close()
print(f"Generated comparison figure at {out_path}")
