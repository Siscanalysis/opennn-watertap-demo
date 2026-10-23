"""The original network against the retrained ones, on WaterTAP simulations none of them has seen.

    python compare_networks.py ro|bsm2 [name=root ...]

Runs the OpenNN surrogate's predict mode with each network on models/<plant>/data/holdout.csv (a
seeded 15 % of the new simulations, kept out of training by prepare_training.py): the original
network (the toy's), the retrained one (models/<plant>) and any `name=root` given (a root holds
model/<plant>_network.json). Writes models/<plant>/comparison.csv: R² and mean absolute error per
output and network, on all held-out points and, for the wastewater plant, by range of the true
effluent NH4 (below 2, 2 to 8 around the 4 mg/L limit, above 8).
"""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from plants import EXE, ORIGINAL_ROOT, ROOT

OUTPUTS = {"ro": ["lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"],
           "bsm2": ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]}

# Wastewater subsets by the true effluent NH4 (mg/L): around the 4 mg/L limit, and above it, where
# the nitrifiers approach washout.
NH4_BANDS = {"nh4_below_2": (0.0, 2.0), "nh4_2_to_8": (2.0, 8.0), "nh4_above_8": (8.0, 1.0e9)}


def read(path, names):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {n: np.array([float(r[n]) for r in rows]) for n in names}


def predict(plant, root, holdout):
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "predicted.csv"
        subprocess.run([str(EXE[plant]), "predict", str(root), str(holdout), str(out)], check=True,
                       stdout=subprocess.DEVNULL)
        return read(out, OUTPUTS[plant])


def r2(y, p):
    return 1.0 - float(np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)) if len(y) > 1 else float("nan")


def main():
    plant = sys.argv[1]
    outputs = OUTPUTS[plant]
    roots = {"original": ORIGINAL_ROOT[plant], "retrained": ROOT[plant]}
    for pair in sys.argv[2:]:
        name, root = pair.split("=", 1)
        roots[name] = Path(root)

    holdout = ROOT[plant] / "data" / "holdout.csv"
    truth = read(holdout, outputs)
    networks = {name: predict(plant, root, holdout) for name, root in roots.items()}
    n = len(truth[outputs[0]])

    subsets = {"all": np.ones(n, bool)}
    if plant == "bsm2":
        for name, (lo, hi) in NH4_BANDS.items():
            subsets[name] = (truth["nh4"] >= lo) & (truth["nh4"] < hi)

    rows = []
    for subset, mask in subsets.items():
        print(f"{plant}, {subset} ({mask.sum()} held-out simulations): R² / mean absolute error")
        print(f"  {'output':14s}" + "".join(f"{name:>24s}" for name in networks))
        for key in outputs:
            y = truth[key][mask]
            cells = []
            for name, p in networks.items():
                values = (r2(y, p[key][mask]), float(np.mean(np.abs(y - p[key][mask]))))
                cells.append(f"{values[0]:10.4f} / {values[1]:<11.4g}")
                rows.append([subset, int(mask.sum()), key, name, f"{values[0]:.6g}", f"{values[1]:.6g}"])
            print(f"  {key:14s}" + "".join(f"{c:>24s}" for c in cells))

    with open(ROOT[plant] / "comparison.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["subset", "samples", "output", "network", "r2", "mae"])
        writer.writerows(rows)


if __name__ == "__main__":
    main()
