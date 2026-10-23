"""Figures for the steady-state BSM2 toy (written to figures/).

    parity.png  test-set predictions of the OpenNN surrogate against WaterTAP
    pareto.png  the energy/nitrogen fronts found on the surrogate, checked in WaterTAP, against
                WaterTAP's own front (minimum SEC subject to total N <= epsilon)

    python plots.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
CRITICAL = "#d03b3b"
TN_AXIS_MAX = 15.0  # a washed-out point (total N above 40 mg/L) would otherwise flatten the fronts

OUTPUTS = ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]
LABELS = {"lcow": "LCOW ($/m³)", "sec": "SEC (kWh/m³)", "tss": "Effluent TSS (mg/L)", "cod": "Effluent COD (mg/L)",
          "tn": "Effluent total N (mg/L)", "bod5": "Effluent BOD5 (mg/L)", "nh4": "Effluent NH₄ (mg/L)",
          "biogas": "Biogas (m³/d)"}


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "axes.titlesize": 10, "axes.labelsize": 9, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 8, "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "lines.linewidth": 2,
    })


def read_csv(path):
    with open(path, newline="") as f:
        return [{k: (v if k in ("scenario", "method", "feasible", "status") else (float(v) if v else np.nan))
                 for k, v in row.items()} for row in csv.DictReader(f)]


def parity(results=RESULTS, suffix=""):
    rows = read_csv(results / "test_predictions.csv")
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.4))
    for ax, name in zip(axes.flat, OUTPUTS):
        true = np.array([r[name] for r in rows])
        pred = np.array([r[name + "_predicted"] for r in rows])
        r2 = 1.0 - np.sum((true - pred) ** 2) / np.sum((true - true.mean()) ** 2)
        lo, hi = min(true.min(), pred.min()), max(true.max(), pred.max())
        ax.plot([lo, hi], [lo, hi], color=MUTED, linewidth=1, zorder=1)
        ax.scatter(true, pred, s=14, color=BLUE, edgecolor=SURFACE, linewidth=0.5, zorder=2)
        ax.set_title(f"{LABELS[name]}   R² {r2:.4f}", loc="left")
        ax.set_xlabel("WaterTAP")
        ax.set_ylabel("OpenNN")
    stage = ", before infill" if suffix == "_round0" else ""
    fig.suptitle(f"Test set ({len(rows)} held-out flowsheet solves){stage}", x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / f"parity{suffix}.png", dpi=150)
    plt.close(fig)


def pareto(results=RESULTS, suffix=""):
    checked = read_csv(results / "pareto_check.csv")
    front = sorted(read_csv(results / "watertap_front.csv"), key=lambda r: r["tn"])
    methods = sorted({r["method"] for r in checked}, key=lambda m: (m.startswith("margin_"), m))
    columns = 2
    rows_number = (len(methods) + columns - 1) // columns
    fig, axes = plt.subplots(rows_number, columns, figsize=(11, 4.2 * rows_number), sharex=True, sharey=True,
                             squeeze=False)
    for ax, method in zip(axes.flat, methods):
        rows = [r for r in checked if r["method"] == method]
        ax.plot([r["tn"] for r in front], [r["sec"] for r in front], color=INK_2, linewidth=1.5, marker="o",
                markersize=3, label="WaterTAP minimum SEC at each total-N limit")
        ax.scatter([r["predicted_tn"] for r in rows], [r["predicted_sec"] for r in rows], s=22, color=BLUE,
                   edgecolor=SURFACE, linewidth=0.8, label="OpenNN front (predicted)", zorder=3)
        feasible = [r for r in rows if r["feasible"] == "yes"]
        infeasible = [r for r in rows if r["feasible"] == "no"]
        ax.scatter([r["true_tn"] for r in feasible], [r["true_sec"] for r in feasible], s=22, color=ORANGE,
                   edgecolor=SURFACE, linewidth=0.8, label="WaterTAP at those points, feasible", zorder=4)
        if infeasible:
            ax.scatter([r["true_tn"] for r in infeasible], [r["true_sec"] for r in infeasible], s=22, marker="x",
                       color=CRITICAL, linewidth=1.2, label="WaterTAP at those points, violating a limit", zorder=4)
        label = method.replace("margin_", "") + (", with margins" if method.startswith("margin_") else ", nominal")
        ax.set_title(f"{label}: {len(feasible)} of {len(rows)} checked points feasible", loc="left")
        off_scale = sum(1 for r in rows if r.get("true_tn", 0) > TN_AXIS_MAX or r["predicted_tn"] > TN_AXIS_MAX)
        if off_scale:
            ax.text(0.99, 0.02, f"{off_scale} point(s) beyond {TN_AXIS_MAX:.0f} mg/L not shown", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=8, color=INK_2)
    visible = [r["sec"] for r in front]
    for r in checked:
        if r["predicted_tn"] <= TN_AXIS_MAX:
            visible.append(r["predicted_sec"])
        if r.get("true_tn", np.nan) <= TN_AXIS_MAX:
            visible.append(r["true_sec"])
    pad = 0.05 * (max(visible) - min(visible))
    for ax in axes.flat:
        ax.set_xlim(right=TN_AXIS_MAX)
        ax.set_ylim(min(visible) - pad, max(visible) + pad)
    for ax in axes[-1]:
        ax.set_xlabel(LABELS["tn"])
    for ax in axes[:, 0]:
        ax.set_ylabel(LABELS["sec"])
    axes[0][0].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES / f"pareto{suffix}.png", dpi=150)
    plt.close(fig)


def main():
    """Figures for the current results, and for results_round0/ (before infill) when present."""
    FIGURES.mkdir(exist_ok=True)
    style()
    parity()
    pareto()
    if (ROOT / "results_round0").exists():
        parity(ROOT / "results_round0", "_round0")
        pareto(ROOT / "results_round0", "_round0")


if __name__ == "__main__":
    main()
