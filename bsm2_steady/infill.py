"""One infill round: solves WaterTAP where the last response optimization went, and writes the
original dataset plus those points to data/bsm2_dataset_infill.csv for retraining.

The points are every OpenNN answer in results/opennn_optima.csv, 25 evenly spaced points of each
Pareto front, and NEIGHBOURS random points around each single-objective answer (the five decisions
moved by up to RADIUS of their range; influent kept). Every attempted point goes to
data/bsm2_infill_log.csv.

    python infill.py [workers]
"""

import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import bsm2_flowsheet as bf

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
DATA = ROOT / "data"
FRONT_SAMPLE = 25
NEIGHBOURS = 4
RADIUS = 0.08
SEED = 11
DECISIONS = ["do3", "do4", "do5", "recycle", "wastage"]


def _init():
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _evaluate(x):
    return PLANT.evaluate(x)


def read_rows(path):
    with open(path, newline="") as f:
        return [{k: float(v) for k, v in row.items() if k not in ("scenario", "method")} for row in csv.DictReader(f)]


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    rng = np.random.default_rng(SEED)

    answers = read_rows(RESULTS / "opennn_optima.csv")
    points = [{v: a[v] for v in bf.INPUTS} for a in answers]
    for path in sorted(RESULTS.glob("pareto_B6_*.csv")):
        rows = sorted(read_rows(path), key=lambda r: r["tn"])
        picks = np.unique(np.round(np.linspace(0, len(rows) - 1, min(FRONT_SAMPLE, len(rows)))).astype(int))
        points += [{v: rows[i][v] for v in bf.INPUTS} for i in picks]
    for a in answers:
        for _ in range(NEIGHBOURS):
            x = {v: a[v] for v in bf.INPUTS}
            for v in DECISIONS:
                lo, hi = bf.RANGES[v]
                x[v] = float(np.clip(a[v] + rng.uniform(-RADIUS, RADIUS) * (hi - lo), lo, hi))
            points.append(x)

    unique = {tuple(round(x[v], 6) for v in bf.INPUTS): x for x in points}
    points = list(unique.values())
    print(f"{len(points)} infill points", flush=True)

    with Pool(workers, initializer=_init) as pool:
        results = pool.map(_evaluate, points, chunksize=2)

    with open(DATA / "bsm2_infill_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["status"] + bf.INPUTS)
        for x, (status, _) in zip(points, results):
            writer.writerow([status] + [f"{x[v]:.8g}" for v in bf.INPUTS])

    with open(DATA / "bsm2_dataset.csv", newline="") as f:
        original = list(csv.reader(f))
    added = [[f"{outputs[k]:.8g}" for k in bf.INPUTS + bf.OUTPUTS]
             for status, outputs in results if status != "failed"]
    with open(DATA / "bsm2_dataset_infill.csv", "w", newline="") as f:
        csv.writer(f).writerows(original + added)

    counts = {s: sum(r[0] == s for r in results) for s in ("ok", "washout", "failed")}
    print(f"{counts}; {len(original) - 1} original + {len(added)} infill rows -> data/bsm2_dataset_infill.csv")


if __name__ == "__main__":
    main()
