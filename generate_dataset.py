"""Samples the WaterTAP RO flowsheet and writes data/ro_dataset.csv.

Latin hypercube over (salinity, recovery, pressure position); see ro_flowsheet.sample.
Every attempted point, solved or not, goes to data/ro_samples_log.csv.

    python generate_dataset.py [samples] [workers]
"""

import csv
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import ro_flowsheet as rf

ROOT = Path(__file__).resolve().parent
SEED = 20261022


def _worker_init():
    rf.quiet()
    global SOLVER
    SOLVER = rf.get_solver()


def _solve(task):
    index, salinity, recovery, position = task
    status, row = rf.sample(salinity, recovery, position, solver=SOLVER)
    if status == "ok" and not rf.is_finite(row):
        status = "failed"
    return index, position, status, row


def main():
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    rng = np.random.default_rng(SEED)
    (s_lo, s_hi), (r_lo, r_hi) = rf.SALINITY_RANGE, rf.RECOVERY_RANGE
    tasks = [(i, s_lo + u * (s_hi - s_lo), r_lo + v * (r_hi - r_lo), w)
             for i, (u, v, w) in enumerate(rf.lhs(samples, 3, rng))]

    (ROOT / "data").mkdir(exist_ok=True)
    start = time.time()
    results = []
    with Pool(workers, initializer=_worker_init) as pool:
        for k, result in enumerate(pool.imap_unordered(_solve, tasks, chunksize=4), 1):
            results.append(result)
            if k % 50 == 0 or k == samples:
                solved = sum(r[2] == "ok" for r in results)
                print(f"{k}/{samples} attempted, {solved} solved, {time.time() - start:.0f} s", flush=True)

    results.sort(key=lambda r: r[0])

    with open(ROOT / "data" / "ro_samples_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "status", "position"] + rf.INPUTS)
        for index, position, status, row in results:
            writer.writerow([index, status, f"{position:.6f}"] + [f"{row[k]:.8g}" for k in rf.INPUTS])

    with open(ROOT / "data" / "ro_dataset.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(rf.INPUTS + rf.OUTPUTS)
        for _, _, status, row in results:
            if status == "ok":
                writer.writerow([f"{row[k]:.8g}" for k in rf.INPUTS + rf.OUTPUTS])

    counts = {s: sum(r[2] == s for r in results) for s in ("ok", "out_of_range", "failed")}
    print(f"Done in {time.time() - start:.0f} s: {counts}")


if __name__ == "__main__":
    main()
