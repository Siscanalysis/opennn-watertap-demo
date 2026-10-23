"""Samples WaterTAP's steady-state BSM2 and writes data/bsm2_dataset.csv.

Latin hypercube over the six inputs in bsm2_flowsheet.RANGES. The points are ordered along a
greedy nearest-neighbour path from the base case and cut into chunks, so each worker moves its
plant by small continuation steps. Every attempted point goes to data/bsm2_samples_log.csv with
its status: ok (nitrifying steady state), washout (no nitrifying steady state; kept in the
dataset, since it is the plant's actual state there) or failed (dropped).

    python generate_dataset.py [samples] [workers] [chunk]
"""

import csv
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import bsm2_flowsheet as bf

ROOT = Path(__file__).resolve().parent
SEED = 20261022


def _init():
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _solve_chunk(chunk):
    results = []
    for index, x in chunk:
        status, outputs = PLANT.evaluate(x)
        results.append((index, status, outputs if outputs else x))
    return results


def nearest_neighbour_path(points):
    """Greedy tour in normalized coordinates, starting from the point closest to the base case."""
    lo = np.array([bf.RANGES[v][0] for v in bf.INPUTS])
    span = np.array([bf.RANGES[v][1] - bf.RANGES[v][0] for v in bf.INPUTS])
    z = (np.array([[p[v] for v in bf.INPUTS] for p in points]) - lo) / span
    base = (np.array([bf.BASE[v] for v in bf.INPUTS]) - lo) / span
    remaining = list(range(len(points)))
    current = min(remaining, key=lambda i: np.abs(z[i] - base).max())
    order = []
    while remaining:
        remaining.remove(current)
        order.append(current)
        if remaining:
            distances = np.abs(z[remaining] - z[current]).max(axis=1)
            current = remaining[int(np.argmin(distances))]
    return order


def main():
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    rng = np.random.default_rng(SEED)
    points = [{v: bf.RANGES[v][0] + u[k] * (bf.RANGES[v][1] - bf.RANGES[v][0]) for k, v in enumerate(bf.INPUTS)}
              for u in bf.lhs(samples, len(bf.INPUTS), rng)]
    order = nearest_neighbour_path(points)
    chunks = [[(i, points[i]) for i in order[k:k + chunk_size]] for k in range(0, samples, chunk_size)]

    (ROOT / "data").mkdir(exist_ok=True)
    start = time.time()
    results = []
    with Pool(workers, initializer=_init) as pool:
        for chunk_results in pool.imap_unordered(_solve_chunk, chunks):
            results += chunk_results
            counts = {s: sum(r[1] == s for r in results) for s in ("ok", "washout", "failed")}
            print(f"{len(results)}/{samples} attempted {counts}, {time.time() - start:.0f} s", flush=True)

    results.sort(key=lambda r: r[0])
    with open(ROOT / "data" / "bsm2_samples_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "status"] + bf.INPUTS)
        for index, status, row in results:
            writer.writerow([index, status] + [f"{row[v]:.8g}" for v in bf.INPUTS])
    with open(ROOT / "data" / "bsm2_dataset.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(bf.INPUTS + bf.OUTPUTS)
        for _, status, row in results:
            if status != "failed":
                writer.writerow([f"{row[k]:.8g}" for k in bf.INPUTS + bf.OUTPUTS])
    print(f"Done in {time.time() - start:.0f} s")


if __name__ == "__main__":
    main()
