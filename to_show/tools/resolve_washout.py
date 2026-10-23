"""Re-solves the wastewater simulations that ended without nitrifiers, approaching each from nearby
points where the nitrifiers live.

    python resolve_washout.py [workers] [minutes]

Steady-state ASM1 always admits a no-nitrifier solution, and bsm2_flowsheet.Plant labels a point
"washout" when its continuation cannot reach the nitrifying one. Next to points with NH4 of a few
mg/L, that label is usually the path, not the plant: walked to from a nearby nitrifying point, the
same inputs solve with nitrifiers. This takes every row of models/bsm2/data (the merged dataset and
the holdout) with NH4 above 30 mg/L, walks to it from its three nearest rows below 10 mg/L in turn,
and appends to models/bsm2/data/washout_resolved.csv as each row finishes: inputs, status ("ok"
when the nitrifying solution was found, "washout" when none of the walks reached it) and outputs.
A failed walk can take minutes, so the run stops after `minutes` (default 20); rows not reached
keep their washout values. prepare_training.py replaces the outputs of the "ok" rows.
"""

import csv
import sys
import time
from multiprocessing import Pool

import numpy as np

from plants import ROOT, TOY

sys.path.insert(0, str(TOY / "bsm2_steady"))

THRESHOLD = 30.0
ANCHOR_BELOW = 10.0
ANCHORS = 3


def _init():
    import bsm2_flowsheet as bf
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _from_anchors(task):
    x, anchors = task
    for anchor in anchors:
        PLANT.restore_base()
        if PLANT._walk(anchor) and PLANT._walk(x):
            outputs = PLANT.read_outputs()
            PLANT.restore_base()
            return x, "ok", outputs
    PLANT.restore_base()
    return x, "washout", None


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    import bsm2_flowsheet as bf
    names = bf.INPUTS
    folder = ROOT["bsm2"] / "data"
    rows = []
    for name in ("bsm2_dataset.csv", "holdout.csv"):
        with open(folder / name, newline="") as f:
            rows += list(csv.DictReader(f))
    x = np.array([[float(r[v]) for v in names] for r in rows])
    nh4 = np.array([float(r["nh4"]) for r in rows])
    span = np.array([bf.RANGES[v][1] - bf.RANGES[v][0] for v in names])
    anchors = np.where(nh4 < ANCHOR_BELOW)[0]

    tasks = []
    for i in np.where(nh4 > THRESHOLD)[0]:
        distance = np.abs((x[anchors] - x[i]) / span).max(axis=1)
        nearest = anchors[np.argsort(distance)[:ANCHORS]]
        tasks.append(({v: float(x[i, k]) for k, v in enumerate(names)},
                      [{v: float(x[j, k]) for k, v in enumerate(names)} for j in nearest]))
    print(f"bsm2: {len(tasks)} rows with NH4 above {THRESHOLD:g} mg/L to re-solve, for at most {minutes:g} minutes", flush=True)

    target = folder / "washout_resolved.csv"
    with open(target, "w", newline="") as f:
        csv.writer(f).writerow(names + ["status"] + bf.OUTPUTS)
    deadline = time.time() + 60.0 * minutes
    found, done = [], 0
    pool = Pool(min(workers, max(1, len(tasks))), initializer=_init)
    try:
        results = pool.imap_unordered(_from_anchors, tasks)
        while done < len(tasks):
            try:
                point, status, outputs = results.next(timeout=max(1.0, deadline - time.time()))
            except Exception:  # the time is up (multiprocessing.TimeoutError)
                break
            done += 1
            with open(target, "a", newline="") as f:
                csv.writer(f).writerow([f"{point[v]:.8g}" for v in names] + [status]
                                       + [f"{outputs[k]:.8g}" if outputs else "" for k in bf.OUTPUTS])
            if status == "ok":
                found.append(outputs["nh4"])
            print(f"bsm2: {done}/{len(tasks)} done, {len(found)} with nitrifiers", flush=True)
    finally:
        pool.terminate()
    print(f"bsm2: nitrifying solution found for {len(found)} of {done} re-solved rows ({len(tasks) - done} not reached)"
          + (f", NH4 {min(found):.2f} to {max(found):.2f} mg/L" if found else "") + f" -> {target}")


if __name__ == "__main__":
    main()
