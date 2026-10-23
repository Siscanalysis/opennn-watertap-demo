"""Paths through the condition range, solved in WaterTAP: a default operation held while the
influent (wastewater) or the feed salinity (desalination) moves over the dashboard's whole grid,
which is what the trends show in the guided demo.

    python scenarios.py <plant: bsm2|ro> [paths] [workers] [--optimum] [--minutes=N]

Takes `paths` default operations (data/<plant>_defaults_verified.csv, seeded choice) and solves
each at every grid value with its set-points held. For the wastewater plant a worker walks one path
in order, so each solve starts from the previous one. Writes data/<plant>_paths_verified.csv
(scenario, inputs, status, true_<output>). The page carries these solutions, so the guided demo
shows WaterTAP without the simulator; no network trains on them, and compare_scenarios.py tests the
wastewater networks along them.

--optimum: the guided demo applies the optimum at the default's condition and then holds it while
the condition moves, so this holds, instead, the stored optimum of the demo's objective (minimum
energy, minimum cost for desalination; data/<plant>_optima_verified.csv) at each chosen default's
condition. Writes data/<plant>_optimum_paths_verified.csv. For the wastewater plant these paths
run into nitrifier washout at the daily peak, where a solve can take minutes: expect hours, so run
it at night (paths are saved as they finish; --minutes=N stops it after N minutes).
"""

import csv
import sys
import time
from multiprocessing import Pool

import numpy as np

from plants import TO_SHOW, TOY

sys.path.insert(0, str(TOY))
sys.path.insert(0, str(TOY / "bsm2_steady"))

SEED = 23
GRID = {"bsm2": ("influent", [16600.0 + 300.0 * k for k in range(28)]),
        "ro": ("salinity", [26.0 + k for k in range(19)])}


def _init(plant):
    global PLANT, MODULE, SOLVER
    if plant == "bsm2":
        import bsm2_flowsheet as module
        module.quiet()
        PLANT = module.Plant()
    else:
        import ro_flowsheet as module
        module.quiet()
        SOLVER = module.get_solver()
    MODULE = module


def _path(task):
    plant, index, setpoints = task
    name, grid = GRID[plant]
    rows = []
    for value in grid:
        x = dict(setpoints, **{name: value})
        if plant == "bsm2":
            status, outputs = PLANT.evaluate(x)
        else:
            outputs = MODULE.evaluate(x["salinity"], x["recovery"], x["pressure"], solver=SOLVER)
            status = "ok" if outputs else "failed"
        rows.append((index, x, status, outputs))
    return rows


DEMO_OBJECTIVE = {"bsm2": "min_energy", "ro": "min_cost"}


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    plant = args[0]
    count = int(args[1]) if len(args) > 1 else 12
    workers = int(args[2]) if len(args) > 2 else 6
    optimum = "--optimum" in flags
    if plant == "bsm2":
        import bsm2_flowsheet as module
    else:
        import ro_flowsheet as module
    name, grid = GRID[plant]

    with open(TO_SHOW / "data" / f"{plant}_defaults_verified.csv", newline="") as f:
        defaults = [r for r in csv.DictReader(f) if r["status"] == "ok"]
    picks = np.random.default_rng(SEED).choice(len(defaults), size=count, replace=False)
    decisions = [v for v in module.INPUTS if v != name]
    if optimum:
        with open(TO_SHOW / "data" / f"{plant}_optima_verified.csv", newline="") as f:
            optima = {round(float(r[name]), 3): r for r in csv.DictReader(f)
                      if r["objective"] == DEMO_OBJECTIVE[plant] and r["status"] in ("ok", "washout")}
        starts = sorted({round(float(defaults[i][name]), 3) for i in picks})
        tasks = [(plant, value, {v: float(optima[value][v]) for v in decisions}) for value in starts if value in optima]
    else:
        tasks = [(plant, k, {v: float(defaults[i][v]) for v in decisions}) for k, i in enumerate(picks)]
    count = len(tasks)

    # Each path is appended as it finishes, so a run stopped early (--minutes=N, or by hand) keeps
    # the paths it completed. Near nitrifier washout a wastewater solve can take minutes.
    minutes = next((float(a.split("=", 1)[1]) for a in flags if a.startswith("--minutes=")), None)
    deadline = time.time() + 60.0 * minutes if minutes else None
    target = TO_SHOW / "data" / f"{plant}_{'optimum_' if optimum else ''}paths_verified.csv"
    with open(target, "w", newline="") as f:
        csv.writer(f).writerow(["scenario"] + module.INPUTS + ["status"] + [f"true_{k}" for k in module.OUTPUTS])
    results = []
    pool = Pool(min(workers, count), initializer=_init, initargs=(plant,))
    try:
        paths = pool.imap_unordered(_path, tasks)
        for _ in range(count):
            try:
                rows = paths.next(timeout=max(1.0, deadline - time.time()) if deadline else None)
            except Exception:  # the time is up
                break
            results += rows
            with open(target, "a", newline="") as f:
                writer = csv.writer(f)
                for index, x, status, outputs in sorted(rows, key=lambda r: r[1][name]):
                    writer.writerow([index] + [f"{x[v]:.8g}" for v in module.INPUTS] + [status]
                                    + [f"{outputs[k]:.8g}" if outputs else "" for k in module.OUTPUTS])
            print(f"{plant} paths: {len(results) // len(grid)}/{count} done, "
                  f"{sum(r[2] == 'failed' for r in results)} points failed", flush=True)
    finally:
        pool.terminate()
    counts = {s: sum(r[2] == s for r in results) for s in ("ok", "washout", "failed")}
    print(f"{plant}: {len(results)} path points {counts} -> {target}")


if __name__ == "__main__":
    main()
