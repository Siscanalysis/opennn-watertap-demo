"""Solves dashboard points in WaterTAP and writes their true outputs next to OpenNN's predictions.

    python verify_points.py <plant: bsm2|ro> <points.csv> <out.csv> [workers]
    python verify_points.py bsm2 <out.csv> <out.csv> [workers] retry

points.csv holds the plant's input columns (any other columns, such as OpenNN's predictions or an
"objective" label, are carried over); a wastewater file with a `rain` column is solved with that
rain. out.csv adds a `status` column and `true_<output>` columns.
The `retry` form re-attempts only the rows of an existing out.csv that failed, approaching each
from up to eight nearby solved rows, and rewrites the file.
"""

import csv
import sys
from multiprocessing import Pool
from pathlib import Path

TOY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOY))
sys.path.insert(0, str(TOY / "bsm2_steady"))

PLANT = None


def _init(plant):
    global PLANT, MODULE
    if plant == "bsm2":
        import bsm2_flowsheet as module
        module.quiet()
        PLANT = module.Plant()
    else:
        import ro_flowsheet as module
        module.quiet()
        PLANT = module.get_solver()
    MODULE = module


def _evaluate(task):
    plant, x = task
    if plant == "bsm2":
        status, outputs = PLANT.evaluate(x)
        return status, outputs
    outputs = MODULE.evaluate(x["salinity"], x["recovery"], x["pressure"], solver=PLANT)
    return ("ok", outputs) if outputs else ("failed", None)


def _evaluate_from_anchors(task):
    """Second pass for BSM2 points the first pass could not reach: walk to a nearby point that did
    solve, then on to the target (the steady-state solve depends on the path taken)."""
    x, anchors = task
    for anchor in anchors:
        PLANT.restore_base()
        if PLANT._walk(anchor) and PLANT._walk(x):
            return "ok", PLANT.read_outputs()
    PLANT.restore_base()
    return "failed", None


def input_names(module, columns):
    """The plant's inputs, with the wastewater plant's rain when the file has that column."""
    return module.RAIN_INPUTS if "rain" in columns and hasattr(module, "RAIN_INPUTS") else module.INPUTS


def nearest(module, x, solved, count=3):
    names = list(x)
    span = {v: module.RANGES[v][1] - module.RANGES[v][0] for v in names}
    distance = lambda y: max(abs(x[v] - y[v]) / span[v] for v in names)
    return sorted(solved, key=distance)[:count]


def retry_failed(points_path, out_path, workers):
    import bsm2_flowsheet as module
    with open(points_path, newline="") as f:
        rows = list(csv.DictReader(f))
    names = input_names(module, rows[0].keys())
    as_input = lambda r: {v: float(r[v]) for v in names}
    solved = [as_input(r) for r in rows if r["status"] == "ok"]
    failed = [i for i, r in enumerate(rows) if r["status"] == "failed"]
    tasks = [(as_input(rows[i]), nearest(module, as_input(rows[i]), solved, count=8)) for i in failed]
    with Pool(min(workers, max(1, len(tasks))), initializer=_init, initargs=("bsm2",)) as pool:
        results = pool.map(_evaluate_from_anchors, tasks, chunksize=1)
    for i, (status, true) in zip(failed, results):
        rows[i]["status"] = status
        for k in module.OUTPUTS:
            rows[i][f"true_{k}"] = "" if true is None else f"{true[k]:.8g}"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"retry: {sum(r[0] == 'ok' for r in results)} of {len(failed)} recovered -> {out_path}")


def main():
    plant, points_path, out_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else (6 if plant == "bsm2" else 4)
    if len(sys.argv) > 5 and sys.argv[5] == "retry":
        retry_failed(points_path, out_path, workers)
        return
    if plant == "bsm2":
        import bsm2_flowsheet as module
    else:
        import ro_flowsheet as module
    with open(points_path, newline="") as f:
        rows = list(csv.DictReader(f))
    inputs, outputs = input_names(module, rows[0].keys()), module.OUTPUTS
    tasks = [(plant, {v: float(r[v]) for v in inputs}) for r in rows]
    with Pool(workers, initializer=_init, initargs=(plant,)) as pool:
        results = pool.map(_evaluate, tasks, chunksize=1)
        failed = [i for i, (status, _) in enumerate(results) if status == "failed"]
        if plant == "bsm2" and failed:
            solved = [tasks[i][1] for i, (status, _) in enumerate(results) if status == "ok"]
            retry = [(tasks[i][1], nearest(module, tasks[i][1], solved)) for i in failed]
            for i, result in zip(failed, pool.map(_evaluate_from_anchors, retry, chunksize=1)):
                results[i] = result
            print(f"second pass from nearby solved points: {sum(r[0] == 'ok' for r in (results[i] for i in failed))} of {len(failed)} recovered")

    fields = list(rows[0].keys()) + ["status"] + [f"true_{k}" for k in outputs]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row, (status, true) in zip(rows, results):
            row = dict(row, status=status)
            for k in outputs:
                row[f"true_{k}"] = "" if true is None else f"{true[k]:.8g}"
            writer.writerow(row)
    counts = {s: sum(r[0] == s for r in results) for s in ("ok", "washout", "failed")}
    print(f"{plant}: {len(rows)} points solved in WaterTAP {counts} -> {out_path}")


if __name__ == "__main__":
    main()
