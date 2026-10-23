"""Training data for the dashboard's retrained networks.

    python prepare_training.py ro|bsm2

Merges, without duplicates (same inputs to 6 significant digits):
  - the toy's original dataset (data/ro_dataset.csv, bsm2_steady/data/bsm2_dataset_infill.csv),
  - the new WaterTAP simulations (models/<plant>/data/new_simulations.csv, from more_simulations.py),
  - the dashboard points solved in WaterTAP (data/<plant>_defaults_verified.csv,
    data/<plant>_optima_verified.csv and the earlier optima in data/original_network/),
  - the operating points the simulator service solved for the page
    (models/<plant>/data/session_simulations.csv).

Rows that resolve_washout.py solved again with nitrifiers (models/bsm2/data/washout_resolved.csv)
take those outputs, in every source and in the holdout.

A seeded 15 % of the new simulations is kept out as models/<plant>/data/holdout.csv. Neither the
original network nor the retrained one sees it, so compare_networks.py can compare them fairly.
Writes models/<plant>/data/<plant>_dataset.csv, the file the surrogate's train mode reads.
"""

import csv
import math
import sys

import numpy as np

from plants import DATASET, ROOT, TO_SHOW, TOY

SEED = 11
HOLDOUT = 0.15

PLANTS = {
    "ro": dict(base=TOY / "data" / "ro_dataset.csv",
               inputs=["salinity", "recovery", "pressure"],
               outputs=["lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"]),
    "bsm2": dict(base=TOY / "bsm2_steady" / "data" / "bsm2_dataset_infill.csv",
                 inputs=["do3", "do4", "do5", "recycle", "wastage", "influent"],
                 outputs=["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]),
}


def read_rows(path, spec, prefix="", status=False):
    """Inputs then outputs of each solved row in `path`, outputs read from prefix + name."""
    if not path.exists():
        return []
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if status and row.get("status") not in ("ok", "washout"):
                continue
            try:
                values = [float(row[c]) for c in spec["inputs"]] + [float(row[prefix + c]) for c in spec["outputs"]]
            except (KeyError, ValueError):
                continue
            if all(math.isfinite(v) for v in values):
                rows.append(values)
    return rows


def main():
    plant = sys.argv[1]
    spec = PLANTS[plant]
    columns = spec["inputs"] + spec["outputs"]
    folder = ROOT[plant] / "data"
    key = lambda values: tuple(f"{v:.6g}" for v in values[:len(spec["inputs"])])

    base = read_rows(spec["base"], spec)
    new = read_rows(folder / "new_simulations.csv", spec)
    # Every optimum ever solved in WaterTAP (the current ones and those archived from earlier
    # networks in data/original_network): an infill where the optimizer goes.
    verified = (read_rows(TO_SHOW / "data" / f"{plant}_defaults_verified.csv", spec, "true_", status=True)
                + read_rows(TO_SHOW / "data" / f"{plant}_optima_verified.csv", spec, "true_", status=True))
    for archived in sorted((TO_SHOW / "data" / "original_network").glob(f"{plant}_optima_verified*.csv")):
        verified += read_rows(archived, spec, "true_", status=True)
    session = read_rows(folder / "session_simulations.csv", spec, status=True)

    # Washout rows that resolve_washout.py solved with nitrifiers take the nitrifying outputs (its
    # rows still labelled "washout" have no outputs and are skipped by read_rows).
    resolved = {key(r): r for r in read_rows(folder / "washout_resolved.csv", spec)}
    corrected = 0
    for rows in (base, new, verified, session):
        for i, r in enumerate(rows):
            fix = resolved.get(key(r))
            if fix is not None and fix[len(spec["inputs"]):] != r[len(spec["inputs"]):]:
                rows[i] = fix
                corrected += 1
    if resolved:
        print(f"{plant}: {corrected} washout rows replaced by their nitrifying solution")

    order = np.random.default_rng(SEED).permutation(len(new))
    held = sorted(order[:round(HOLDOUT * len(new))])
    holdout = [new[i] for i in held]
    held_keys = {key(r) for r in holdout}

    merged, seen, counts = [], set(), {}
    for name, rows in (("original", base), ("new", new), ("dashboard", verified), ("session", session)):
        counts[name] = 0
        for r in rows:
            k = key(r)
            if k in seen or k in held_keys:
                continue
            seen.add(k)
            merged.append(r)
            counts[name] += 1

    for path, rows in ((DATASET[plant], merged), (folder / "holdout.csv", holdout)):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows([f"{v:.8g}" for v in r] for r in rows)

    print(f"{plant}: {len(merged)} training rows ("
          + ", ".join(f"{n} {name}" for name, n in counts.items())
          + f"), {len(holdout)} held out -> {folder}")


if __name__ == "__main__":
    main()
