#!/usr/bin/env python3
"""Generate report figures from progressive_residual_summary.csv."""
import csv, os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG_DIR = os.path.join(REPO, "docs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

CSV = os.path.join(REPO, "results", "progressive_residual_summary.csv")

cases, t1, t12, t124, gain, t2new, t4new = [], [], [], [], [], [], []
with open(CSV) as f:
    for row in csv.DictReader(f):
        label = f"{row['circuit']} {int(float(row['ratio'])*100)}%"
        cases.append(label)
        t1.append(float(row['FC_T1']))
        t12.append(float(row['FC_T1_T2']))
        t124.append(float(row['FC_T1_T2_T4']))
        gain.append(float(row['total_gain_pp']))
        t2new.append(int(row['T2_new_DT']))
        t4new.append(int(row['T4_new_DT']))

# Figure 1: Coverage bar chart
fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(cases))
w = 0.25
ax.bar(x - w, t1, w, label='T=1', color='#4472C4')
ax.bar(x, t12, w, label='T1+T2', color='#ED7D31')
ax.bar(x + w, t124, w, label='T1+T2+T4', color='#70AD47')
ax.set_ylabel('Fault Coverage (%)')
ax.set_title('Progressive Residual Multi-Frame ATPG Coverage')
ax.set_xticks(x)
ax.set_xticklabels(cases, rotation=15, ha='right')
ax.legend()
ax.set_ylim(0, 100)
for i, (g, t124v) in enumerate(zip(gain, t124)):
    ax.annotate(f'+{g:.1f}pp' if g > 0 else f'{g:.1f}pp', (x[i] + w, t124v + 1),
                ha='center', va='bottom', fontsize=8, fontweight='bold',
                color='#70AD47' if g > 5 else '#888888')
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "coverage_bar_chart.png"), dpi=150)
plt.close()
print("Saved coverage_bar_chart.png")

# Figure 2: Recovered faults by depth
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(x - 0.15, t2new, 0.3, label='Recovered by T=2', color='#ED7D31')
ax.bar(x + 0.15, t4new, 0.3, label='Recovered by T=4', color='#70AD47')
for i, (t2, t4) in enumerate(zip(t2new, t4new)):
    if t2: ax.text(x[i] - 0.15, t2 + 0.5, str(t2), ha='center', fontsize=9)
    if t4: ax.text(x[i] + 0.15, t4 + 0.5, str(t4), ha='center', fontsize=9)
ax.set_ylabel('Newly Detected Faults')
ax.set_title('Recovered Faults by Residual Depth')
ax.set_xticks(x)
ax.set_xticklabels(cases, rotation=15, ha='right')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "recovered_faults_chart.png"), dpi=150)
plt.close()
print("Saved recovered_faults_chart.png")

print(f"Figures saved to {FIG_DIR}")
