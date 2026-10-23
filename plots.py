"""Figures for the water treatment toy example (written to figures/).

    parity.png   test-set predictions of the OpenNN surrogate against WaterTAP
    slice_S1.png LCOW and outlet flux along the pressure at 35 g/kg, recovery 0.5
                 (WaterTAP's own optimize_set_up problem), with both answers
    pareto.png   the LCOW/recovery Pareto fronts found on the surrogate, checked in WaterTAP

    python plots.py [workers]
"""

import csv
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ro_flowsheet as rf

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
EXE = ROOT / "model" / "ro_surrogate.exe"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL = "#d03b3b"

LABELS = {"lcow": "LCOW ($/m³)", "sec": "SEC (kWh/m³)", "permeate_ppm": "Permeate NaCl (ppm)",
          "flux_out": "Outlet flux (kg/m²/h)", "flux_avg": "Average flux (kg/m²/h)", "area": "Membrane area (m²)"}


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
        return [{k: (v if k in ("scenario", "method", "feasible") else (float(v) if v else np.nan))
                 for k, v in row.items()} for row in csv.DictReader(f)]


def parity():
    rows = read_csv(RESULTS / "test_predictions.csv")
    fig, axes = plt.subplots(2, 3, figsize=(10, 6.4))
    for ax, name in zip(axes.flat, rf.OUTPUTS):
        true = np.array([r[name] for r in rows])
        pred = np.array([r[name + "_predicted"] for r in rows])
        r2 = 1.0 - np.sum((true - pred) ** 2) / np.sum((true - true.mean()) ** 2)
        lo, hi = min(true.min(), pred.min()), max(true.max(), pred.max())
        ax.plot([lo, hi], [lo, hi], color=MUTED, linewidth=1, zorder=1)
        ax.scatter(true, pred, s=14, color=BLUE, edgecolor=SURFACE, linewidth=0.5, zorder=2)
        ax.set_title(f"{LABELS[name]}   R² {r2:.4f}", loc="left")
        ax.set_xlabel("WaterTAP")
        ax.set_ylabel("OpenNN")
    fig.suptitle(f"Test set ({len(rows)} held-out flowsheet solves)", x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "parity.png", dpi=150)
    plt.close(fig)


def _init():
    rf.quiet()
    global SOLVER
    SOLVER = rf.get_solver()


def _evaluate(point):
    return rf.evaluate(*point, solver=SOLVER)


def surrogate(points):
    inputs, outputs = FIGURES / "_slice_inputs.csv", FIGURES / "_slice_outputs.csv"
    with open(inputs, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(rf.INPUTS)
        writer.writerows(points)
    subprocess.run([str(EXE), "predict", str(ROOT), str(inputs), str(outputs)], check=True)
    rows = read_csv(outputs)
    inputs.unlink()
    outputs.unlink()
    return rows


def slice_s1(workers):
    pressures = np.round(np.arange(52.0, 85.01, 1.0), 3)
    points = [(35.0, 0.5, float(p)) for p in pressures]
    with Pool(workers, initializer=_init) as pool:
        truth = pool.map(_evaluate, points)
    model = surrogate(points)

    optima = read_csv(RESULTS / "opennn_optima.csv")
    nominal = next(r for r in optima if r["scenario"] == "S1_fixed_recovery")["pressure"]
    margin = next(r for r in optima if r["scenario"] == "S1_fixed_recovery_margin")["pressure"]
    best = rf.optimize(35.0, recovery=0.5)

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(7.5, 6.2), sharex=True)
    for ax, name in ((top, "lcow"), (bottom, "flux_out")):
        ok = [i for i, t in enumerate(truth) if t is not None]
        ax.plot(pressures[ok], [truth[i][name] for i in ok], color=ORANGE, label="WaterTAP")
        ax.plot(pressures, [m[name] for m in model], color=BLUE, label="OpenNN surrogate")
        ax.axvline(best["pressure"], color=INK_2, linewidth=1, linestyle="--")
        ax.axvline(nominal, color=AQUA, linewidth=1.2)
        ax.axvline(margin, color=AQUA, linewidth=1.2, linestyle=":")
        ax.set_ylabel(LABELS[name])
    bottom.axhline(1.0, color=MUTED, linewidth=1)
    bottom.set_ylim(0, 8)
    bottom.text(84.5, 1.25, "minimum outlet flux", color=INK_2, fontsize=8, ha="right")
    top.text(0.99, 0.04, f"dashed: WaterTAP optimum {best['pressure']:.2f} bar\n"
             f"aqua: OpenNN {nominal:.2f} bar (nominal), {margin:.2f} bar (with margin)",
             transform=top.transAxes, color=INK_2, fontsize=8, ha="right", va="bottom")
    top.legend(loc="upper left")
    top.set_title("35 g/kg, recovery 0.5: LCOW is flat, so the outlet-flux limit sets the optimum", loc="left")
    bottom.set_xlabel("RO feed pressure (bar)")
    fig.tight_layout()
    fig.savefig(FIGURES / "slice_S1.png", dpi=150)
    plt.close(fig)


def pareto():
    checked = read_csv(RESULTS / "pareto_check.csv")
    curve = read_csv(RESULTS / "watertap_lcow_by_recovery.csv")
    methods = sorted({r["method"] for r in checked}, key=lambda m: (m.startswith("margin_"), m))
    columns = 2
    rows_number = (len(methods) + columns - 1) // columns
    fig, axes = plt.subplots(rows_number, columns, figsize=(11, 4.2 * rows_number), sharex=True, sharey=True,
                             squeeze=False)
    for ax, method in zip(axes.flat, methods):
        rows = [r for r in checked if r["method"] == method]
        ax.plot([c["recovery"] for c in curve], [c["lcow"] for c in curve], color=INK_2, linewidth=1.5,
                label="WaterTAP minimum LCOW at each recovery")
        ax.scatter([r["recovery"] for r in rows], [r["predicted_lcow"] for r in rows], s=22, color=BLUE,
                   edgecolor=SURFACE, linewidth=0.8, label="OpenNN front (predicted)", zorder=3)
        feasible = [r for r in rows if r["feasible"] == "yes"]
        infeasible = [r for r in rows if r["feasible"] == "no"]
        ax.scatter([r["recovery"] for r in feasible], [r["true_lcow"] for r in feasible], s=22, color=ORANGE,
                   edgecolor=SURFACE, linewidth=0.8, label="WaterTAP at those points, feasible", zorder=4)
        if infeasible:
            ax.scatter([r["recovery"] for r in infeasible], [r["true_lcow"] for r in infeasible], s=22,
                       marker="x", color=CRITICAL, linewidth=1.2,
                       label="WaterTAP at those points, violating a constraint", zorder=4)
        label = method.replace("margin_", "") + (", with margins" if method.startswith("margin_") else ", nominal")
        ax.set_title(f"{label}: {len(feasible)} of {len(rows)} feasible in WaterTAP", loc="left")
    for ax in axes[-1]:
        ax.set_xlabel("Water recovery")
    for ax in axes[:, 0]:
        ax.set_ylabel(LABELS["lcow"])
    axes[0][0].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "pareto.png", dpi=150)
    plt.close(fig)


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    FIGURES.mkdir(exist_ok=True)
    style()
    parity()
    pareto()
    slice_s1(workers)


if __name__ == "__main__":
    main()
