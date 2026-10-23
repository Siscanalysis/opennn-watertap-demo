"""NH4 of the wastewater networks along the daily-pattern scenarios, against WaterTAP.

    python compare_scenarios.py [name=root ...]

Reads data/bsm2_paths_verified.csv (from scenarios.py) and predicts it with each network: by
default the original one (../bsm2_steady) and the retrained one (models/bsm2); `name=root` pairs
add others (a root holds model/bsm2_network.json). Prints the NH4 error by range of the true value,
and how often the network puts NH4 on the wrong side of the 4 mg/L limit. Writes
models/bsm2/scenario_comparison.csv and models/bsm2/scenarios_nh4.png (one panel per scenario:
WaterTAP as dots, each network as a line).
"""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from plants import EXE, ORIGINAL_ROOT, ROOT, TO_SHOW

INPUTS = ["do3", "do4", "do5", "recycle", "wastage", "influent"]
BANDS = [(0, 2), (2, 4), (4, 8), (8, 15), (15, 100)]
LIMIT = 4.0
COLORS = {"original": "#8a949b", "retrained": "#2a78d6"}


def predict(root, rows):
    with tempfile.TemporaryDirectory() as folder:
        source, out = Path(folder) / "in.csv", Path(folder) / "out.csv"
        with open(source, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(INPUTS)
            writer.writerows([[r[v] for v in INPUTS] for r in rows])
        subprocess.run([str(EXE["bsm2"]), "predict", str(root), str(source), str(out)], check=True,
                       stdout=subprocess.DEVNULL)
        with open(out, newline="") as f:
            return np.array([float(r["nh4"]) for r in csv.DictReader(f)])


def main():
    networks = {"original": ORIGINAL_ROOT["bsm2"], "retrained": ROOT["bsm2"]}
    for pair in sys.argv[1:]:
        name, root = pair.split("=", 1)
        networks[name] = Path(root)

    with open(TO_SHOW / "data" / "bsm2_paths_verified.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] in ("ok", "washout")]
    truth = np.array([float(r["true_nh4"]) for r in rows])
    predictions = {name: predict(root, rows) for name, root in networks.items()}

    table = []
    print(f"NH4 on {len(rows)} scenario points (mean absolute error, mg/L; points per range in brackets)")
    print("  network      " + "".join(f"{f'{lo}-{hi}':>11s}" for lo, hi in BANDS) + "   all    wrong side of 4")
    for name, p in predictions.items():
        cells = []
        for lo, hi in BANDS:
            m = (truth >= lo) & (truth < hi)
            cells.append(float(np.mean(np.abs(p[m] - truth[m]))) if m.any() else float("nan"))
        wrong = int(np.sum((p > LIMIT) != (truth > LIMIT)))
        overall = float(np.mean(np.abs(p - truth)))
        print(f"  {name:12s} " + "".join(f"{c:11.3f}" for c in cells) + f"{overall:7.3f}   {wrong}")
        table.append([name] + [f"{c:.6g}" for c in cells] + [f"{overall:.6g}", wrong])
    counts = [int(np.sum((truth >= lo) & (truth < hi))) for lo, hi in BANDS]
    print("  points       " + "".join(f"{f'[{c}]':>11s}" for c in counts))

    folder = ROOT["bsm2"]
    with open(folder / "scenario_comparison.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["network"] + [f"mae_nh4_{lo}_{hi}" for lo, hi in BANDS] + ["mae_nh4_all", "wrong_side_of_4"])
        writer.writerows(table)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scenarios = sorted({int(r["scenario"]) for r in rows})
    cols = 4
    fig, axes = plt.subplots((len(scenarios) + cols - 1) // cols, cols, figsize=(14, 3.0 * ((len(scenarios) + cols - 1) // cols)),
                             sharex=True, squeeze=False)
    for ax, s in zip(axes.flat, scenarios):
        idx = [i for i, r in enumerate(rows) if int(r["scenario"]) == s]
        q = np.array([float(rows[i]["influent"]) for i in idx]) / 1000.0
        for name, p in predictions.items():
            ax.plot(q, p[idx], color=COLORS.get(name), lw=2, label=f"OpenNN, {name}")
        ax.plot(q, truth[idx], "o", color="#d95926", ms=4, label="WaterTAP")
        ax.axhline(LIMIT, color="#d03b3b", lw=1, ls="--")
        r0 = rows[idx[0]]
        ax.set_title(f"DO {float(r0['do3']):.1f}/{float(r0['do4']):.1f}/{float(r0['do5']):.1f}, "
                     f"IR {100 * float(r0['recycle']):.0f} %, WAS {100 * float(r0['wastage']):.2f} %", fontsize=9)
        ax.tick_params(labelsize=8)
    for ax in axes.flat[len(scenarios):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("influent, thousand m³/d", fontsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("effluent NH₄, mg/L", fontsize=8)
    axes.flat[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Daily-pattern scenarios: set-points held, influent swept (dashed: the 4 mg/L limit)", fontsize=11)
    fig.tight_layout()
    fig.savefig(folder / "scenarios_nh4.png", dpi=110)
    print(f"Wrote {folder / 'scenario_comparison.csv'} and {folder / 'scenarios_nh4.png'}")


if __name__ == "__main__":
    main()
