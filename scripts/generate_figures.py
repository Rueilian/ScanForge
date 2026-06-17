#!/usr/bin/env python3
"""Generate report figures from exp2_two_phase.csv (10 canonical circuits)."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIG_DIR = os.path.join(REPO, "docs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family":"sans-serif","font.size":11,"axes.titlesize":13,
    "axes.labelsize":11,"xtick.labelsize":9,"ytick.labelsize":9,
    "legend.fontsize":9,"figure.dpi":150,"savefig.dpi":150,
    "savefig.bbox":"tight","axes.spines.top":False,"axes.spines.right":False,
})

C = {"blue":"#3B7DD8","orange":"#E8923A","green":"#4DAF7A","red":"#E25A5A","gray":"#95A5A6"}
CSV = os.path.join(REPO, "results", "exp2_two_phase.csv")

ITC99 = ["b03","b04","b05","b07","b08","b09"]
ISCAS89 = ["s953","s1196","s1238","s5378"]

def load():
    rows = {}
    with open(CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r["ratio"] == "0.1":
                rows[r["circuit"]] = r
    return rows

def fig1_two_phase_flow():
    fig, ax = plt.subplots(figsize=(10,5))
    ax.set_xlim(0,10); ax.set_ylim(0,5); ax.axis("off")
    def box(x,y,t,kw):
        ax.text(x,y,t,ha="center",va="center",fontsize=10,bbox=kw,zorder=5)
    def arr(x1,y1,x2,y2,c="#2C3E50"):
        ax.annotate("",xy=(x2,y2),xytext=(x1,y1),
                    arrowprops=dict(arrowstyle="->",color=c,lw=1.5),zorder=3)
    ax.text(5,4.7,"Progressive Residual Pipeline with Two-Phase State Justification",
            fontsize=13,ha="center",fontweight="bold")
    s = dict(boxstyle="round,pad=0.4",fc="#F8F9FA",ec="#2C3E50",lw=1.5)
    g = dict(boxstyle="round,pad=0.3",fc="#E8F8F0",ec=C["green"],lw=1.5)
    o = dict(boxstyle="round,pad=0.3",fc="#FEF3E2",ec=C["orange"],lw=1.5)
    b = dict(boxstyle="round,pad=0.3",fc="#E8F4FD",ec=C["blue"],lw=1.5)
    box(1.8,3.7,"T=1 (single frame)\nall faults, ptt=5s",s)
    box(1.8,2.3,"DT ✓",g); box(3.5,2.3,"TO / AU",o)
    box(5.5,3.7,"T=2 (two-frame)\nresidual R1 = F−D1\nTwo-Phase ON",s)
    box(5.5,2.3,"DT ✓",g); box(7.2,2.3,"TO / AU",o)
    box(8.8,3.0,"T=4 (four-frame)\nresidual R2\nTwo-Phase ON",s)
    box(8.8,1.5,"+0 DT\n(0 pp)",o)
    arr(1.8,3.3,1.8,2.7); arr(1.8,2.0,5.5,3.3)
    arr(5.5,3.3,5.5,2.7); arr(5.5,2.0,8.8,2.6)
    arr(8.8,2.6,8.8,1.9)
    ax.text(5,1.0,"Final FC = |D1 ∪ D2 ∪ D4| / |F|   (fixed T=1 denominator)",
            fontsize=11,ha="center",fontstyle="italic")
    ax.text(5,0.6,"Two-Phase: Phase 1 = propagation on last frame | Phase 2 = justify through earlier frames",
            fontsize=9,ha="center",color="#7F8C8D")
    fig.savefig(os.path.join(FIG_DIR,"fig1_two_phase_flow.png"))
    plt.close(fig); print("  fig1_two_phase_flow.png")

def fig2_coverage_bar_chart():
    rows = load()
    fig, axes = plt.subplots(1,2,figsize=(11,4.5),sharey=True)
    for idx, (label, circs) in enumerate([("ITC'99", ITC99), ("ISCAS'89", ISCAS89)]):
        ax = axes[idx]
        t1 = [float(rows[c]["FC_T1"]) for c in circs]
        t12 = [float(rows[c]["FC_T1_T2"]) for c in circs]
        t124 = [float(rows[c]["FC_T1_T2_T4"]) for c in circs]
        gain = [float(rows[c]["total_gain_pp"]) for c in circs]
        x = np.arange(len(circs)); w = 0.25
        ax.bar(x-w, t1, w, label="T=1", color=C["blue"], zorder=3)
        ax.bar(x, t12, w, label="T1∪T2", color=C["orange"], zorder=3)
        ax.bar(x+w, t124, w, label="T1∪T2∪T4", color=C["green"], zorder=3)
        for i, (g, v) in enumerate(zip(gain, t124)):
            ax.annotate(f"+{g:.1f}", (x[i]+w, v+0.5), ha="center", fontsize=7.5,
                        fontweight="bold", color=C["green"])
        ax.set_title(label, fontsize=13, fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(circs, rotation=45)
        ax.set_xlabel("Circuit")
        if idx == 0: ax.set_ylabel("Fault coverage (%)")
        ax.set_ylim(20, 100); ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.suptitle("Progressive Residual Pipeline: T-stage Union Coverage (10% non-scan, ptt=5s)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.legend(handles=[
        plt.Rectangle((0,0),1,1,color=C["blue"],label="T=1"),
        plt.Rectangle((0,0),1,1,color=C["orange"],label="T1∪T2"),
        plt.Rectangle((0,0),1,1,color=C["green"],label="T1∪T2∪T4"),
    ], loc="lower center", ncol=3, bbox_to_anchor=(0.5,-0.1), framealpha=0.9)
    fig.tight_layout(); fig.subplots_adjust(bottom=0.18)
    fig.savefig(os.path.join(FIG_DIR,"fig2_coverage_bar_chart.png"))
    plt.close(fig); print("  fig2_coverage_bar_chart.png")

def fig3_recovered_by_depth():
    rows = load()
    fig, axes = plt.subplots(1,2,figsize=(11,4.5))
    for idx, (label, circs) in enumerate([("ITC'99", ITC99), ("ISCAS'89", ISCAS89)]):
        ax = axes[idx]
        t2new = [int(rows[c]["T2_new_DT"]) for c in circs]
        t4new = [int(rows[c]["T4_new_DT"]) for c in circs]
        x = np.arange(len(circs)); w = 0.3
        ax.bar(x-w/2, t2new, w, label="New at T=2", color=C["orange"], zorder=3)
        ax.bar(x+w/2, t4new, w, label="New at T=4", color=C["green"], zorder=3)
        ax.set_title(label, fontsize=13, fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(circs, rotation=45)
        ax.set_xlabel("Circuit")
        if idx == 0: ax.set_ylabel("Newly detected faults")
        ax.grid(axis="y", alpha=0.3, zorder=0); ax.legend(loc="upper left", fontsize=9)
    fig.suptitle("Residual Recovery: T=2 vs T=4 (10% non-scan, ptt=5s)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout(); fig.subplots_adjust(bottom=0.15)
    fig.savefig(os.path.join(FIG_DIR,"fig3_recovered_by_depth.png"))
    plt.close(fig); print("  fig3_recovered_by_depth.png")

def fig4_runtime_vs_gain():
    rows = load()
    fig, ax = plt.subplots(figsize=(8,4.5))
    for c in ITC99:
        r = rows[c]
        ax.scatter(float(r["total_rt"]), float(r["total_gain_pp"]),
                   s=80, color=C["blue"], zorder=4, edgecolors="white", linewidths=0.5)
        ax.annotate(c, (float(r["total_rt"]), float(r["total_gain_pp"])),
                    textcoords="offset points", xytext=(5,5), fontsize=8)
    for c in ISCAS89:
        r = rows[c]
        ax.scatter(float(r["total_rt"]), float(r["total_gain_pp"]),
                   s=80, color=C["orange"], zorder=4, marker="s", edgecolors="white", linewidths=0.5)
        ax.annotate(c, (float(r["total_rt"]), float(r["total_gain_pp"])),
                    textcoords="offset points", xytext=(5,5), fontsize=8)
    ax.set_xlabel("Total pipeline runtime (s)"); ax.set_ylabel("Total gain vs T=1 (pp)")
    ax.set_title("Pipeline Runtime vs. Coverage Gain", fontsize=13, fontweight="bold")
    ax.grid(alpha=0.3, zorder=0); ax.set_xscale("log")
    ax.legend(handles=[
        plt.Line2D([],[],color=C["blue"],marker="o",ls="None",ms=8,label="ITC'99"),
        plt.Line2D([],[],color=C["orange"],marker="s",ls="None",ms=8,label="ISCAS'89"),
    ], loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR,"fig4_runtime_vs_gain.png"))
    plt.close(fig); print("  fig4_runtime_vs_gain.png")

# B2 full-scan FC values from phase_d_fullscan_dataset.csv (fc_scan) and
# iscas89_fullscan_baseline.csv (FC_fullscan_pct)
B2_ITC99 = {"b03":91.23,"b04":94.18,"b05":96.10,"b07":93.92,"b08":95.47,"b09":94.58}
B2_ISCAS89 = {"s953":97.79,"s1196":98.87,"s1238":96.36,"s5378":96.65}

def fig5_gap_to_fullscan():
    rows = load()
    fig, axes = plt.subplots(1,2,figsize=(11,4.5),sharey=True)
    for idx, (label, circs, b2map) in enumerate([
        ("ITC'99", ITC99, B2_ITC99), ("ISCAS'89", ISCAS89, B2_ISCAS89)
    ]):
        ax = axes[idx]
        t1 = [float(rows[c]["FC_T1"]) for c in circs]
        exp = [float(rows[c]["FC_T1_T2_T4"]) for c in circs]
        b2v = [b2map[c] for c in circs]
        gap = [b - e for b, e in zip(b2v, exp)]
        x = np.arange(len(circs)); w = 0.25
        ax.bar(x-w, t1, w, label="B1 (T=1)", color=C["blue"], zorder=3)
        ax.bar(x, exp, w, label="Exp (T1+T2)", color=C["orange"], zorder=3)
        ax.bar(x+w, b2v, w, label="B2 (full-scan)", color=C["gray"], alpha=0.5, zorder=3)
        for i, (g, b) in enumerate(zip(gap, b2v)):
            if g > 0.5:
                ax.annotate(f"gap={g:.1f}pp", (x[i]+w, b+0.5),
                            ha="center", fontsize=7, color=C["red"], fontweight="bold")
        ax.set_title(label, fontsize=13, fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(circs, rotation=45)
        ax.set_xlabel("Circuit")
        if idx == 0: ax.set_ylabel("Fault coverage (%)")
        ax.set_ylim(20, 102); ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.suptitle("B1 → Experiment → B2: Gap to Full-Scan (10% non-scan, ptt=5s)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.legend(handles=[
        plt.Rectangle((0,0),1,1,color=C["blue"],label="B1 (T=1 partial-scan)"),
        plt.Rectangle((0,0),1,1,color=C["orange"],label="Exp (T1∪T2)"),
        plt.Rectangle((0,0),1,1,color=C["gray"],alpha=0.5,label="B2 (full-scan)"),
    ], loc="lower center", ncol=3, bbox_to_anchor=(0.5,-0.1), framealpha=0.9)
    fig.tight_layout(); fig.subplots_adjust(bottom=0.18)
    fig.savefig(os.path.join(FIG_DIR,"fig5_gap_to_fullscan.png"))
    plt.close(fig); print("  fig5_gap_to_fullscan.png")

def main():
    print("Generating figures...")
    for fn in [fig1_two_phase_flow, fig2_coverage_bar_chart, fig3_recovered_by_depth,
               fig4_runtime_vs_gain, fig5_gap_to_fullscan]:
        fn()
    print(f"Done → {FIG_DIR}/")

if __name__ == "__main__":
    main()
