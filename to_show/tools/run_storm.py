"""The storm network, after storm_simulations.py: training, optima and WaterTAP checks.

    python run_storm.py [--until=HH:MM] [--rounds=2]

Round by round (a second round only if a first-round optimum misses a limit in WaterTAP):
  1. prepare_rain_training.py      dry training set + wet-weather simulations (+ checked optima)
  2. bsm2_surrogate train          two hidden layers of 32 or 48 neurons, chosen by NH4
     bsm2_surrogate export, validation
  3. export_weights.py bsm2_rain   the browser's weights
  4. bsm2_surrogate sweep          the three objectives in parallel, at the rain levels RAIN_LEVELS
  5. verify_points.py              the optima solved in WaterTAP -> data/bsm2_rain_optima_verified.csv
Then compare_rain.py writes models/bsm2_rain/summary.txt. A step that would run past --until is
stopped there and the run ends; everything is logged to models/bsm2_rain/run_log.txt.
"""

import csv
import datetime
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from plants import EXE, ROOT, TO_SHOW

HERE = Path(__file__).resolve().parent
PYTHON = sys.executable
SURROGATE = str(EXE["bsm2_rain"])
NET = ROOT["bsm2_rain"]
RAIN_LEVELS = "0,1500,3000,4500"
OBJECTIVES = ("min_energy", "min_cost", "max_biogas")
VERIFIED = TO_SHOW / "data" / "bsm2_rain_optima_verified.csv"
LOG = NET / "run_log.txt"


def log(text):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def deadline(text):
    now = datetime.datetime.now()
    hour, minute = map(int, text.split(":"))
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (at if at > now else at + datetime.timedelta(days=1)).timestamp()


class OutOfTime(Exception):
    pass


def run(name, commands, stop_at, env=None):
    """Runs the commands in parallel, each logging to NET/logs/<name>[_k].log; all must succeed."""
    (NET / "logs").mkdir(parents=True, exist_ok=True)
    started, processes = time.time(), []
    for k, command in enumerate(commands):
        out = open(NET / "logs" / (f"{name}_{k}.log" if len(commands) > 1 else f"{name}.log"), "w", encoding="utf-8")
        processes.append((subprocess.Popen(command, cwd=HERE, env={**os.environ, **(env[k] if env else {})},
                                           stdout=out, stderr=subprocess.STDOUT), out))
    log(f"{name}: started {len(commands)} process(es)")
    while any(p.poll() is None for p, _ in processes):
        if time.time() > stop_at:
            for p, _ in processes:
                if p.poll() is None:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            log(f"{name}: stopped at the time limit")
            raise OutOfTime(name)
        time.sleep(5)
    for _, out in processes:
        out.close()
    codes = [p.returncode for p, _ in processes]
    log(f"{name}: done in {(time.time() - started) / 60:.1f} min, exit codes {codes}")
    if any(codes):
        raise RuntimeError(f"{name} failed")


def join_sweeps():
    rows, header = [], None
    for objective in OBJECTIVES:
        with open(NET / "results" / f"dashboard_optima_{objective}.csv", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows += list(reader)
    with open(NET / "results" / "dashboard_optima.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    log(f"sweep: {len(rows)} optima joined")


def missed_limits():
    """Optima that WaterTAP solved and that miss a limit, and how many were solved."""
    bounds = {"nh4": 4.0, "tn": 18.0, "cod": 100.0, "tss": 30.0, "bod5": 10.0}
    with open(VERIFIED, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] in ("ok", "washout")]
    missed = [r for r in rows if any(float(r[f"true_{k}"]) > v * (1 + 1e-3) for k, v in bounds.items())]
    return len(missed), len(rows)


def one_round(number, stop_at):
    log(f"round {number}")
    run(f"prepare_{number}", [[PYTHON, "-B", "prepare_rain_training.py"]], stop_at)
    run(f"train_{number}", [[SURROGATE, "train", str(NET)]], stop_at,
        env=[{"BSM2_LAYERS": "2", "BSM2_NEURONS": "32,48", "BSM2_SELECT": "nh4"}])
    run(f"export_{number}", [[SURROGATE, "export", str(NET)]], stop_at)
    run(f"validation_{number}", [[SURROGATE, "validation", str(NET)]], stop_at)
    run(f"weights_{number}", [[PYTHON, "-B", "export_weights.py", "bsm2_rain"]], stop_at)
    # Three processes at once, so a share of the cores each (OpenNN would take them all).
    threads = str(max(1, (os.cpu_count() or 3) // len(OBJECTIVES)))
    run(f"sweep_{number}", [[SURROGATE, "sweep", str(NET)] for _ in OBJECTIVES], stop_at,
        env=[{"BSM2_SWEEP": o, "BSM2_RAIN_LEVELS": RAIN_LEVELS, "OPENNN_THREADS": threads} for o in OBJECTIVES])
    join_sweeps()
    run(f"verify_{number}", [[PYTHON, "-B", "verify_points.py", "bsm2", str(NET / "results" / "dashboard_optima.csv"),
                              str(VERIFIED), "6"]], stop_at)
    missed, solved = missed_limits()
    log(f"round {number}: {solved} optima solved in WaterTAP, {missed} miss a limit")
    return missed


# What a round produces: its training set, the network, its results and weights, and its optima
# checked in WaterTAP.
ARTIFACTS = [NET / "data" / "bsm2_dataset.csv", NET / "model", NET / "results",
             TO_SHOW / "weights" / "bsm2_rain_network.json", VERIFIED]


def keep(folder):
    """Copies the round's artifacts into folder."""
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for path in ARTIFACTS:
        (shutil.copytree if path.is_dir() else shutil.copy)(path, folder / path.name)


def restore(folder):
    """Puts the artifacts kept in folder back, so the network and its optima belong together."""
    for path in ARTIFACTS:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            shutil.copytree(folder / path.name, path)
        else:
            shutil.copy(folder / path.name, path)


def main():
    options = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    stop_at = deadline(options.get("until", "19:45"))
    rounds = int(options.get("rounds", "2"))
    NET.mkdir(parents=True, exist_ok=True)
    log(f"storm network: up to {rounds} round(s), stop at {datetime.datetime.fromtimestamp(stop_at):%H:%M}")
    # Optima checked for an earlier storm network are not training data for this one.
    for stale in (TO_SHOW / "data").glob("bsm2_rain_optima_verified*.csv"):
        stale.unlink()
        log(f"removed {stale.name} (an earlier storm network's optima)")
    kept = None
    try:
        for number in range(1, rounds + 1):
            started = time.time()
            if one_round(number, stop_at) == 0 or number == rounds:
                break
            # Another round only if it can finish (as long as this one, with a tenth to spare).
            if time.time() + 1.1 * (time.time() - started) > stop_at:
                log(f"no time for round {number + 1}; round {number} stands")
                break
            kept = NET / f"round{number}"
            keep(kept)
            # The next round trains on these checked optima too (prepare_rain_training reads them).
            shutil.copy(VERIFIED, VERIFIED.with_name(f"bsm2_rain_optima_verified_round{number}.csv"))
        run("compare", [[PYTHON, "-B", "compare_rain.py"]], stop_at)
        log("finished")
    except (OutOfTime, RuntimeError) as stopped:
        if kept is not None:
            restore(kept)
            for extra in (TO_SHOW / "data").glob("bsm2_rain_optima_verified_round*.csv"):
                extra.unlink()
            log(f"{stopped} did not finish; the last complete round is back in place")
            try:
                run("compare", [[PYTHON, "-B", "compare_rain.py"]], stop_at + 900)
            except Exception as error:
                log(f"compare failed: {error}")
        else:
            log(f"{stopped} did not finish; no round is complete")
            sys.exit(1)


if __name__ == "__main__":
    main()
