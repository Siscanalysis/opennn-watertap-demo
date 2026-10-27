"""WaterTAP simulations of the wastewater plant in wet weather, for the storm network.

    python storm_simulations.py <samples> [workers] [--until=HH:MM] [--seed=N]

A Latin hypercube over the six usual inputs and the rain flow (bsm2_flowsheet.RANGES: rain 0 to
6,000 m3/d, which adds to the influent and dilutes it). Points are visited along a
nearest-neighbour path, in chunks of 20, so each worker moves its plant by small steps.

Writes, as chunks finish, to_show/models/bsm2_rain/data/rain_simulations.csv (solved points,
inputs then outputs) and rain_simulations_log.csv (every attempt with its status). A run started
again with the same arguments skips the points already attempted. --until stops handing out chunks
at that time of day; the chunks already running finish.
"""

import csv
import datetime
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

TO_SHOW = Path(__file__).resolve().parents[1]
TOY = TO_SHOW.parent
sys.path.insert(0, str(TOY / "bsm2_steady"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from more_simulations import nearest_neighbour_path  # noqa: E402

FOLDER = TO_SHOW / "models" / "bsm2_rain" / "data"
CHUNK = 20


def _init():
    import bsm2_flowsheet as bf
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _chunk(chunk):
    out = []
    for index, x in chunk:
        try:
            status, outputs = PLANT.evaluate(x)
        except Exception as error:  # a failed solve must not end the run
            print(f"point {index}: {type(error).__name__}: {error}", flush=True)
            PLANT.restore_base()
            status, outputs = "failed", None
        out.append((index, status, x, outputs))
    return out


def deadline(text):
    """The next time of day HH:MM, as a timestamp."""
    now = datetime.datetime.now()
    hour, minute = map(int, text.split(":"))
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at <= now:
        at += datetime.timedelta(days=1)
    return at.timestamp()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    options = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    samples = int(args[0])
    workers = int(args[1]) if len(args) > 1 else 6
    stop_at = deadline(options["until"]) if "until" in options else float("inf")
    seed = int(options.get("seed", 23))

    import bsm2_flowsheet as bf
    names, outputs = bf.RAIN_INPUTS, bf.OUTPUTS
    rng = np.random.default_rng(seed)
    points = [{v: bf.RANGES[v][0] + u[k] * (bf.RANGES[v][1] - bf.RANGES[v][0]) for k, v in enumerate(names)}
              for u in bf.lhs(samples, len(names), rng)]
    order = nearest_neighbour_path(points, bf.RANGES, names, bf.BASE)
    chunks = [[(i, points[i]) for i in order[k:k + CHUNK]] for k in range(0, len(order), CHUNK)]

    FOLDER.mkdir(parents=True, exist_ok=True)
    data_path, log_path = FOLDER / "rain_simulations.csv", FOLDER / "rain_simulations_log.csv"
    done = set()
    if log_path.exists():
        with open(log_path, newline="") as f:
            done = {int(r["index"]) for r in csv.DictReader(f)}
    else:
        with open(log_path, "w", newline="") as f:
            csv.writer(f).writerow(["index", "status"] + names)
        with open(data_path, "w", newline="") as f:
            csv.writer(f).writerow(names + outputs)
    chunks = [c for c in ([(i, x) for i, x in chunk if i not in done] for chunk in chunks) if c]
    print(f"bsm2 rain: {len(points)} points, {len(done)} attempted before, {sum(map(len, chunks))} to go "
          f"in {len(chunks)} chunks on {workers} workers", flush=True)

    start, counts = time.time(), {"ok": 0, "washout": 0, "failed": 0}
    with Pool(workers, initializer=_init) as pool:
        running, next_chunk = [], 0
        while next_chunk < len(chunks) or running:
            while next_chunk < len(chunks) and len(running) < workers and time.time() < stop_at:
                running.append(pool.apply_async(_chunk, (chunks[next_chunk],)))
                next_chunk += 1
            if time.time() >= stop_at and next_chunk < len(chunks):
                print(f"bsm2 rain: stop time reached, {len(chunks) - next_chunk} chunks left for a later run", flush=True)
                next_chunk = len(chunks)
            finished = [r for r in running if r.ready()]
            if not finished:
                time.sleep(2)
                continue
            for result in finished:
                running.remove(result)
                rows = result.get()
                with open(log_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    for index, status, x, _ in rows:
                        writer.writerow([index, status] + [f"{x[v]:.8g}" for v in names])
                with open(data_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    for _, status, x, y in rows:
                        if status in ("ok", "washout") and y:
                            writer.writerow([f"{y.get(v, x[v]):.8g}" for v in names] + [f"{y[k]:.8g}" for k in outputs])
                for _, status, _, _ in rows:
                    counts[status] = counts.get(status, 0) + 1
            print(f"bsm2 rain: {sum(counts.values())} attempted this run {counts}, {time.time() - start:.0f} s", flush=True)
    print(f"bsm2 rain: done -> {data_path}", flush=True)


if __name__ == "__main__":
    main()
