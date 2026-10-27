"""Training data for the storm network (to_show/models/bsm2_rain), whose seventh input is rain.

    python prepare_rain_training.py

Merges, without duplicates (same inputs to 6 significant digits):
  - the dry-weather training set of the page's wastewater network (models/bsm2/data/bsm2_dataset.csv),
    with no rain;
  - the wet-weather simulations (models/bsm2_rain/data/rain_simulations.csv, from storm_simulations.py);
  - the storm network's optima solved in WaterTAP (data/bsm2_rain_optima_verified*.csv), from the
    second round on;
  - the wet-weather points the simulator service solved for the page
    (models/bsm2/data/session_simulations_local.csv, rows with rain).

A seeded 15 % of the wet-weather simulations is kept out as models/bsm2_rain/data/holdout.csv. The dry
network's holdout (models/bsm2/data/holdout.csv) is not in the dry training set either, so both
networks can be compared on it. Writes models/bsm2_rain/data/bsm2_dataset.csv.
"""

import csv
import math

import numpy as np

from plants import TO_SHOW

INPUTS = ["do3", "do4", "do5", "recycle", "wastage", "influent", "rain"]
OUTPUTS = ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]
DRY = TO_SHOW / "models" / "bsm2" / "data"
FOLDER = TO_SHOW / "models" / "bsm2_rain" / "data"
SEED = 13
HOLDOUT = 0.15


def read_rows(path, prefix="", status=False):
    """Inputs (rain 0 when the file has none) then outputs of each solved row."""
    if not path.exists():
        return []
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if status and row.get("status") not in ("ok", "washout"):
                continue
            try:
                values = ([float(row.get(c) or 0.0) if c == "rain" else float(row[c]) for c in INPUTS]
                          + [float(row[prefix + c]) for c in OUTPUTS])
            except (KeyError, ValueError):
                continue
            if all(math.isfinite(v) for v in values):
                rows.append(values)
    return rows


def main():
    key = lambda values: tuple(f"{v:.6g}" for v in values[:len(INPUTS)])
    dry = read_rows(DRY / "bsm2_dataset.csv")
    wet = read_rows(FOLDER / "rain_simulations.csv")
    verified = []
    for path in sorted((TO_SHOW / "data").glob("bsm2_rain_optima_verified*.csv")):
        verified += read_rows(path, "true_", status=True)
    # Dry session points are already in the dry training set.
    session = [r for r in read_rows(DRY / "session_simulations_local.csv", status=True) if r[INPUTS.index("rain")] > 0]

    order = np.random.default_rng(SEED).permutation(len(wet))
    held = sorted(order[:round(HOLDOUT * len(wet))])
    holdout = [wet[i] for i in held]
    held_keys = {key(r) for r in holdout} | {key(r) for r in read_rows(DRY / "holdout.csv")}

    merged, seen, counts = [], set(), {}
    for name, rows in (("dry", dry), ("wet", wet), ("optima", verified), ("session", session)):
        counts[name] = 0
        for r in rows:
            k = key(r)
            if k in seen or k in held_keys:
                continue
            seen.add(k)
            merged.append(r)
            counts[name] += 1

    FOLDER.mkdir(parents=True, exist_ok=True)
    for path, rows in ((FOLDER / "bsm2_dataset.csv", merged), (FOLDER / "holdout.csv", holdout)):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(INPUTS + OUTPUTS)
            writer.writerows([f"{v:.8g}" for v in r] for r in rows)

    print(f"bsm2_rain: {len(merged)} training rows ("
          + ", ".join(f"{n} {name}" for name, n in counts.items())
          + f"), {len(holdout)} wet-weather rows held out -> {FOLDER}")


if __name__ == "__main__":
    main()
