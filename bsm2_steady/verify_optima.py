"""Checks the OpenNN response optimization answers against WaterTAP's steady-state BSM2.

For every row of results/opennn_optima.csv (and 25 evenly spaced points of each Pareto front)
it solves WaterTAP at the proposed inputs, checks the BSM2 effluent limits on the true outputs and
compares the objective with WaterTAP's own optimum: IPOPT on the flowsheet over the same five
decisions and ranges, started from the base case and from four Latin-hypercube points (best kept).
The true energy/nitrogen front is WaterTAP's minimum SEC subject to total N <= epsilon.

Writes results/comparison.csv, results/comparison.md, results/pareto_check.csv and
results/watertap_front.csv.

    python verify_optima.py [workers]
"""

import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import bsm2_flowsheet as bf

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

# Mirror of make_scenarios() in model/main.cpp. A "_margin" variant shares its scenario's nominal limits.
SCENARIOS = {
    "B1_min_lcow": dict(influent=20648.0, objective="lcow"),
    "B2_min_energy": dict(influent=20648.0, objective="sec"),
    "B3_min_energy_low_load": dict(influent=17500.0, objective="sec"),
    "B4_min_energy_high_load": dict(influent=24000.0, objective="sec"),
    "B5_max_biogas": dict(influent=20648.0, objective="biogas"),
}
PARETO = "B6_pareto_energy_nitrogen"
PARETO_SPEC = dict(influent=20648.0, objective="sec", nitrogen_limit=False)
EPSILONS = (6.0, 6.5, 7.0, 7.5, 8.0, 9.0, 10.0, 12.0, 14.0, 17.0, 21.0, 26.0)
FRONT_SAMPLE = 25
DECISIONS = ["do3", "do4", "do5", "recycle", "wastage"]
STARTS_SEED = 7


def base_name(scenario):
    return scenario.removesuffix("_margin")


def better(objective, a, b):
    if b is None:
        return True
    return a[objective] > b[objective] if objective == "biogas" else a[objective] < b[objective]


def violations(true, nitrogen_limit=True):
    """Relative violations of the BSM2 effluent limits (0 when satisfied)."""
    return {name: max(0.0, (true[name] - limit) / limit)
            for name, limit in bf.LIMITS.items() if nitrogen_limit or name != "tn"}


def starts():
    rng = np.random.default_rng(STARTS_SEED)
    points = [{v: bf.BASE[v] for v in DECISIONS}]
    for u in bf.lhs(4, len(DECISIONS), rng):
        points.append({v: bf.RANGES[v][0] + u[k] * (bf.RANGES[v][1] - bf.RANGES[v][0]) for k, v in enumerate(DECISIONS)})
    return points


def _init():
    bf.quiet()
    global PLANT
    PLANT = bf.Plant()


def _task(task):
    kind, payload = task
    if kind == "evaluate":
        status, outputs = PLANT.evaluate(payload)
        return (status, outputs)
    return PLANT.optimize(**payload)


def read_csv(path):
    with open(path, newline="") as f:
        return [{k: (v if k in ("scenario", "method") else float(v)) for k, v in row.items()}
                for row in csv.DictReader(f)]


def fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    optima = read_csv(RESULTS / "opennn_optima.csv")
    fronts = {}
    for path in sorted(RESULTS.glob(f"pareto_{PARETO}_*.csv")):
        rows = sorted(read_csv(path), key=lambda r: r["tn"])
        picks = np.unique(np.round(np.linspace(0, len(rows) - 1, min(FRONT_SAMPLE, len(rows)))).astype(int))
        fronts[path.stem.removeprefix(f"pareto_{PARETO}_")] = [rows[i] for i in picks]

    evaluations = [{v: r[v] for v in bf.INPUTS} for r in optima]
    for rows in fronts.values():
        evaluations += [{v: r[v] for v in bf.INPUTS} for r in rows]

    optimizations = []
    for name, spec in SCENARIOS.items():
        for k, start in enumerate(starts()):
            optimizations.append((name, k, dict(influent=spec["influent"], objective=spec["objective"], start=start)))
    for eps in EPSILONS:
        for k, start in enumerate(starts()[:2]):
            optimizations.append((f"eps {eps}", k, dict(influent=PARETO_SPEC["influent"], objective="sec",
                                                         start=start, limits=dict(bf.LIMITS, tn=eps))))

    tasks = [("evaluate", x) for x in evaluations] + [("optimize", o[2]) for o in optimizations]
    with Pool(workers, initializer=_init) as pool:
        results = pool.map(_task, tasks, chunksize=1)
    truths = results[:len(evaluations)]
    runs = results[len(evaluations):]

    best, by_start = {}, {}
    for (name, k, kwargs), result in zip(optimizations, runs):
        by_start.setdefault(name, {})[k] = result
        objective = kwargs["objective"]
        if result is not None and better(objective, result, best.get(name)):
            best[name] = result

    # Single-objective scenarios and the advised Pareto points.
    rows = []
    for k, r in enumerate(optima):
        status, true = truths[k]
        spec = SCENARIOS.get(base_name(r["scenario"]))
        objective = spec["objective"] if spec else "sec"
        optimum = best.get(base_name(r["scenario"]))
        row = {"scenario": r["scenario"], "method": r["method"], **{v: r[v] for v in bf.INPUTS},
               "objective": objective, "predicted": r[objective], "status": status,
               "true": None if true is None else true[objective],
               "watertap_optimum": None if optimum is None else optimum[objective],
               "gap_percent": None, "worst_violation": ""}
        if true is None:
            row["feasible"] = "flowsheet failed"
        else:
            v = violations(true, nitrogen_limit=spec is not None)
            worst = max(v, key=v.get)
            if v[worst] > 0:
                row["worst_violation"] = f"{worst} by {100 * v[worst]:.1f} %"
            row["feasible"] = "yes" if v[worst] <= 1e-3 else "no"
            if optimum is not None:
                sign = -1.0 if objective == "biogas" else 1.0
                row["gap_percent"] = 100.0 * sign * (true[objective] - optimum[objective]) / optimum[objective]
            for name in bf.OUTPUTS:
                row["true_" + name] = true[name]
                row["predicted_" + name] = r[name]
        rows.append(row)

    columns = ["scenario", "method"] + bf.INPUTS + ["objective", "predicted", "true", "watertap_optimum",
                                                    "gap_percent", "status", "feasible", "worst_violation"]
    columns += [p + n for n in bf.OUTPUTS for p in ("predicted_", "true_")]
    with open(RESULTS / "comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in columns})

    # The WaterTAP energy/nitrogen front and the OpenNN front points checked against it.
    front = sorted([best[f"eps {eps}"] for eps in EPSILONS if f"eps {eps}" in best], key=lambda o: o["tn"])
    with open(RESULTS / "watertap_front.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(bf.INPUTS + bf.OUTPUTS)
        for o in front:
            writer.writerow([o[k] for k in bf.INPUTS + bf.OUTPUTS])
    front_tn = np.array([o["tn"] for o in front])
    front_sec = np.array([o["sec"] for o in front])

    pareto_rows = []
    offset = len(optima)
    for method, points in fronts.items():
        for i, r in enumerate(points):
            status, true = truths[offset + i]
            row = {"method": method, **{v: r[v] for v in bf.INPUTS}, "predicted_sec": r["sec"],
                   "predicted_tn": r["tn"], "predicted_nh4": r["nh4"], "status": status}
            if true is not None:
                v = violations(true, nitrogen_limit=False)
                row.update(true_sec=true["sec"], true_tn=true["tn"], true_nh4=true["nh4"],
                           feasible="yes" if max(v.values()) <= 1e-3 else "no")
                if len(front) > 1 and front_tn[0] <= true["tn"] <= front_tn[-1]:
                    row["minimum_sec_at_tn"] = float(np.interp(true["tn"], front_tn, front_sec))
                    row["excess_percent"] = 100.0 * (true["sec"] / row["minimum_sec_at_tn"] - 1.0)
            else:
                row["feasible"] = "flowsheet failed"
            pareto_rows.append(row)
        offset += len(points)

    pareto_columns = ["method"] + bf.INPUTS + ["predicted_sec", "true_sec", "predicted_tn", "true_tn",
                                                "minimum_sec_at_tn", "excess_percent", "predicted_nh4",
                                                "true_nh4", "status", "feasible"]
    with open(RESULTS / "pareto_check.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=pareto_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(pareto_rows)

    # Markdown summary.
    lines = ["Gap: how much worse WaterTAP's value at the OpenNN point is than WaterTAP's best optimum "
             "(negative = better, which only an infeasible point can be unless WaterTAP's optimum is local).",
             "Feasible: the BSM2 effluent limits hold in WaterTAP within 0.1 % (total N excluded for the Pareto scenario).",
             "", "| Scenario | Method | DO3 | DO4 | DO5 | Recycle | Wastage | Objective | OpenNN predicted "
             "| WaterTAP at that point | WaterTAP optimum | Gap | Feasible in WaterTAP |",
             "|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|"]
    for row in rows:
        gap = "" if row["gap_percent"] is None else f"{row['gap_percent']:+.2f} %"
        feasible = row["feasible"] + (f" ({row['worst_violation']})" if row["worst_violation"] else "")
        lines.append(f"| {row['scenario']} | {row['method']} | {row['do3']:.2f} | {row['do4']:.2f} | {row['do5']:.2f} | "
                     f"{row['recycle']:.3f} | {row['wastage']:.4f} | {row['objective']} | {fmt(row['predicted'])} | "
                     f"{fmt(row['true'])} | {fmt(row['watertap_optimum'])} | {gap} | {feasible} |")
    lines += ["", "WaterTAP optima (IPOPT from the base case = start 0 and four Latin-hypercube starts):", "",
              "| Scenario | Start | DO3 | DO4 | DO5 | Recycle | Wastage | LCOW | SEC | TSS | COD | TN | BOD5 | NH4 | Biogas |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in list(SCENARIOS) + [f"eps {eps}" for eps in EPSILONS]:
        for k, o in by_start.get(name, {}).items():
            if o is None:
                lines.append(f"| {name} | {k} | failed |||||||||||||")
                continue
            mark = " **(best)**" if o is best.get(name) else ""
            lines.append(f"| {name} | {k}{mark} | {o['do3']:.2f} | {o['do4']:.2f} | {o['do5']:.2f} | {o['recycle']:.3f} | "
                         f"{o['wastage']:.4f} | {o['lcow']:.4f} | {o['sec']:.4f} | {o['tss']:.1f} | {o['cod']:.1f} | "
                         f"{o['tn']:.2f} | {o['bod5']:.2f} | {o['nh4']:.2f} | {o['biogas']:.0f} |")
    lines.append("")
    for method in fronts:
        front_rows = [r for r in pareto_rows if r["method"] == method]
        ok = [r for r in front_rows if r["feasible"] == "yes"]
        excess = [r["excess_percent"] for r in ok if "excess_percent" in r]
        summary = (f"median {np.median(excess):+.2f} %, worst {np.max(excess):+.2f} %" if excess else "none comparable")
        lines.append(f"- Pareto front {method}: {len(front_rows)} checked points, {len(ok)} feasible in WaterTAP; "
                     f"true SEC above WaterTAP's minimum at the same total N: {summary}.")
    (RESULTS / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
