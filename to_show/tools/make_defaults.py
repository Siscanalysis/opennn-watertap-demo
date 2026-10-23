"""Candidate default operations for the dashboard: random set-points at the dashboard's disturbance
values (influent flow for BSM2, feed salinity for RO), kept when the OpenNN network predicts every
limit met with the same safety margins the optimizer uses. verify_points.py then solves them in
WaterTAP, and the dashboard keeps only those that are feasible there too.

Writes to_show/data/<plant>_default_candidates.csv.

    python make_defaults.py [candidates per plant] [kept per plant]
"""

import csv
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from plants import DATASET, EXE, ROOT, TO_SHOW

SEED = 2026


def read_margins(path):
    with open(path, newline="") as f:
        return {(r["output"], float(r["bound"])): float(r["margin"]) for r in csv.DictReader(f)}


def bsm2_setup():
    margins = read_margins(ROOT["bsm2"] / "model" / "constraint_margins.csv")
    limits = {"tss": 30.0, "cod": 100.0, "tn": 18.0, "bod5": 10.0, "nh4": 4.0}
    grid = [16600.0 + 300.0 * k for k in range(28)]

    def sample(rng, influent):
        return {"do3": rng.uniform(0.5, 3.0), "do4": rng.uniform(0.5, 3.0), "do5": rng.uniform(0.5, 3.0),
                "recycle": rng.uniform(0.3, 0.8), "wastage": rng.uniform(0.006, 0.025), "influent": influent}

    def feasible(row):
        return all(row[k] <= v - margins[(k, v)] for k, v in limits.items())

    return dict(root=ROOT["bsm2"], exe=EXE["bsm2"],
                inputs=["do3", "do4", "do5", "recycle", "wastage", "influent"], grid=grid,
                sample=sample, feasible=feasible)


def ro_setup():
    margins = read_margins(ROOT["ro"] / "model" / "constraint_margins.csv")
    grid = [26.0 + k for k in range(19)]
    with open(DATASET["ro"], newline="") as f:  # pressure*(1 - recovery)/salinity: smallest in the training data
        guard = min(float(r["pressure"]) * (1.0 - float(r["recovery"])) / float(r["salinity"]) for r in csv.DictReader(f))

    def sample(rng, salinity):
        return {"salinity": salinity, "recovery": rng.uniform(0.35, 0.60), "pressure": rng.uniform(40.0, 80.0)}

    def feasible(row):
        return (row["permeate_ppm"] <= 500.0 - margins[("permeate_ppm", 500.0)]
                and row["flux_out"] >= 1.0 + margins[("flux_out", 1.0)]
                and row["pressure"] <= 80.0
                and row["pressure"] * (1.0 - row["recovery"]) / row["salinity"] >= guard)

    return dict(root=ROOT["ro"], exe=EXE["ro"], inputs=["salinity", "recovery", "pressure"],
                grid=grid, sample=sample, feasible=feasible)


def main():
    candidates = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
    kept = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    (TO_SHOW / "data").mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp())
    for plant, setup in (("bsm2", bsm2_setup()), ("ro", ro_setup())):
        rng = random.Random(SEED)
        points = [setup["sample"](rng, setup["grid"][k % len(setup["grid"])]) for k in range(candidates)]
        sample_csv, predicted_csv = scratch / f"{plant}_in.csv", scratch / f"{plant}_out.csv"
        with open(sample_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(setup["inputs"])
            writer.writerows([[f"{p[v]:.7g}" for v in setup["inputs"]] for p in points])
        subprocess.run([str(setup["exe"]), "predict", str(setup["root"]), str(sample_csv), str(predicted_csv)],
                       check=True)
        with open(predicted_csv, newline="") as f:
            rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
        feasible = [r for r in rows if setup["feasible"](r)]
        # Round-robin over the disturbance grid so every flow (salinity) gets candidates.
        by_value = {}
        for r in feasible:
            by_value.setdefault(r[setup["inputs"][-1] if plant == "bsm2" else "salinity"], []).append(r)
        chosen = []
        while len(chosen) < kept and any(by_value.values()):
            for value in sorted(by_value):
                if by_value[value] and len(chosen) < kept:
                    chosen.append(by_value[value].pop(0))
        target = TO_SHOW / "data" / f"{plant}_default_candidates.csv"
        with open(target, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(chosen)
        print(f"{plant}: {len(feasible)} of {len(rows)} random operations predicted feasible with margins; "
              f"{len(chosen)} kept -> {target.name}")


if __name__ == "__main__":
    main()
