"""More WaterTAP simulations to retrain the dashboard's networks.

    python more_simulations.py ro <samples> [workers]
    python more_simulations.py bsm2 <samples> [workers]

RO: a new Latin hypercube over feed salinity, recovery and the pressure's position between 0.88
times the brine osmotic pressure and 85 bar (the scheme of the original dataset).
BSM2: half a new Latin hypercube over the six inputs, half points where the current network
predicts the plant near an effluent limit, which is where the optimizer operates. Points are
visited along a nearest-neighbour path so each worker moves its plant by small steps.

Writes to_show/models/<plant>/data/new_simulations.csv (solved points, inputs then outputs) and
new_simulations_log.csv (every attempt with its status).
"""

import csv
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

TO_SHOW = Path(__file__).resolve().parents[1]
TOY = TO_SHOW.parent
sys.path.insert(0, str(TOY))
sys.path.insert(0, str(TOY / "bsm2_steady"))

SEED = 7


# ---------------------------------------------------------------------------- RO

def _ro_init():
    import ro_flowsheet as rf
    rf.quiet()
    global RF, SOLVER
    RF, SOLVER = rf, rf.get_solver()


def _ro_task(task):
    index, salinity, recovery, position = task
    status, row = RF.sample(salinity, recovery, position, solver=SOLVER)
    if status == "ok" and not RF.is_finite(row):
        status = "failed"
    return index, status, row


def ro(samples, workers):
    import ro_flowsheet as rf
    rng = np.random.default_rng(SEED)
    (s_lo, s_hi), (r_lo, r_hi) = rf.SALINITY_RANGE, rf.RECOVERY_RANGE
    tasks = [(i, s_lo + u * (s_hi - s_lo), r_lo + v * (r_hi - r_lo), w)
             for i, (u, v, w) in enumerate(rf.lhs(samples, 3, rng))]
    results = []
    start = time.time()
    with Pool(workers, initializer=_ro_init) as pool:
        for k, result in enumerate(pool.imap_unordered(_ro_task, tasks, chunksize=4), 1):
            results.append(result)
            if k % 50 == 0 or k == samples:
                print(f"ro: {k}/{samples} attempted, {sum(r[1] == 'ok' for r in results)} solved, {time.time() - start:.0f} s", flush=True)
    results.sort(key=lambda r: r[0])
    return rf.INPUTS, rf.OUTPUTS, [(status, row) for _, status, row in results]


# ---------------------------------------------------------------------------- BSM2

def _bsm2_init():
    import bsm2_flowsheet as bf
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _bsm2_chunk(chunk):
    out = []
    for index, x in chunk:
        status, outputs = PLANT.evaluate(x)
        out.append((index, status, outputs if outputs else x))
    return out


def network_predict(model, x):
    """Forward pass of an exported OpenNN network (to_show/weights/*.json), as in src/model.js."""
    z = np.array([(x[i["name"]] - i["mean"]) / i["std"] for i in model["inputs"]])
    for layer in model["layers"]:
        z = np.array(layer["biases"]) + z @ np.array(layer["weights"])
        if layer["activation"] == "Tanh":
            z = np.tanh(z)
    out = {}
    for k, o in enumerate(model["outputs"]):
        out[o["name"]] = float(np.exp(z[k]) if o["scaler"] == "Logarithm" else z[k] * o["std"] + o["mean"])
    return out


def near_limits(y):
    return (2.0 <= y["nh4"] <= 8.0 or 98.5 <= y["cod"] <= 101.5 or 15.0 <= y["tn"] <= 21.0
            or 27.0 <= y["tss"] <= 33.0)


def nearest_neighbour_path(points, ranges, names, start):
    lo = np.array([ranges[v][0] for v in names])
    span = np.array([ranges[v][1] - ranges[v][0] for v in names])
    z = (np.array([[p[v] for v in names] for p in points]) - lo) / span
    here = (np.array([start[v] for v in names]) - lo) / span
    remaining = list(range(len(points)))
    current = min(remaining, key=lambda i: np.abs(z[i] - here).max())
    order = []
    while remaining:
        remaining.remove(current)
        order.append(current)
        if remaining:
            current = remaining[int(np.argmin(np.abs(z[remaining] - z[current]).max(axis=1)))]
    return order


def bsm2(samples, workers):
    import bsm2_flowsheet as bf
    rng = np.random.default_rng(SEED)
    names = bf.INPUTS
    box = lambda u: {v: bf.RANGES[v][0] + u[k] * (bf.RANGES[v][1] - bf.RANGES[v][0]) for k, v in enumerate(names)}
    uniform = [box(u) for u in bf.lhs(samples // 2, len(names), rng)]

    model = json.loads((TO_SHOW / "weights" / "bsm2_network.json").read_text())
    candidates = [box(rng.random(len(names))) for _ in range(30000)]
    boundary = [x for x in candidates if near_limits(network_predict(model, x))]
    picks = rng.choice(len(boundary), size=min(samples - len(uniform), len(boundary)), replace=False)
    points = uniform + [boundary[i] for i in picks]
    print(f"bsm2: {len(uniform)} uniform points and {len(picks)} of {len(boundary)} near-limit candidates", flush=True)

    order = nearest_neighbour_path(points, bf.RANGES, names, bf.BASE)
    chunks = [[(i, points[i]) for i in order[k:k + 20]] for k in range(0, len(points), 20)]
    results = []
    start = time.time()
    with Pool(workers, initializer=_bsm2_init) as pool:
        for chunk_results in pool.imap_unordered(_bsm2_chunk, chunks):
            results += chunk_results
            counts = {s: sum(r[1] == s for r in results) for s in ("ok", "washout", "failed")}
            print(f"bsm2: {len(results)}/{len(points)} attempted {counts}, {time.time() - start:.0f} s", flush=True)
    results.sort(key=lambda r: r[0])
    return names, bf.OUTPUTS, [(status, row) for _, status, row in results]


def main():
    plant, samples = sys.argv[1], int(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    inputs, outputs, results = (ro if plant == "ro" else bsm2)(samples, workers)
    folder = TO_SHOW / "models" / plant / "data"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "new_simulations_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["status"] + inputs)
        for status, row in results:
            writer.writerow([status] + [f"{row[v]:.8g}" for v in inputs])
    with open(folder / "new_simulations.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(inputs + outputs)
        for status, row in results:
            if status in ("ok", "washout"):
                writer.writerow([f"{row[k]:.8g}" for k in inputs + outputs])
    kept = sum(s in ("ok", "washout") for s, _ in results)
    print(f"{plant}: {kept} of {len(results)} simulations kept -> {folder / 'new_simulations.csv'}")


if __name__ == "__main__":
    main()
