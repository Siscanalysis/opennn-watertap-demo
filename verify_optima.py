"""Checks the OpenNN response optimization answers against the WaterTAP flowsheet.

For every row of results/opennn_optima.csv it solves WaterTAP at the proposed
(salinity, recovery, pressure), reads the true outputs, checks the scenario's nominal
constraints on them and compares the objective with WaterTAP's own optimum.

WaterTAP's optimum is IPOPT on the full flowsheet with the same limits. IPOPT finds a local
optimum, so with the recovery free it is solved three ways: from three starting recoveries,
at fixed recoveries on a grid (salinity is fixed, so only recovery and pressure are free and
the grid makes the search global), and once more from the best grid point. The best is kept.

The Pareto fronts are checked point by point against WaterTAP's minimum LCOW at that recovery.

Writes results/comparison.csv, results/comparison.md, results/pareto_check.csv and
results/watertap_lcow_by_recovery.csv.

    python verify_optima.py [workers]
"""

import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import ro_flowsheet as rf

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

# Mirror of make_scenarios() in model/main.cpp, in the keyword arguments of rf.optimize.
# Defaults there: permeate <= 500 ppm, outlet flux >= 1 kg/m2/h, pressure <= 80 bar,
# recovery within the dataset range. A "_margin" variant shares its scenario's nominal limits.
SCENARIOS = {
    "S1_fixed_recovery": dict(salinity=35.0, recovery=0.5, objective="lcow"),
    "S2_free_recovery": dict(salinity=35.0, objective="lcow"),
    "S2b_free_recovery_no_guard": dict(salinity=35.0, objective="lcow"),
    "S3_min_energy_design_flux": dict(salinity=35.0, objective="sec", flux_avg_min=20.0),
    "S4_high_salinity": dict(salinity=44.0, objective="lcow", pressure_max=70.0),
    "S5_max_recovery_budget": dict(salinity=35.0, objective="max_recovery", lcow_max=0.420),
}
PARETO = "S6_pareto_lcow_recovery"
PARETO_SPEC = dict(salinity=35.0, objective="lcow")

STARTS = (0.38, 0.50, 0.58)
GRID = np.round(np.linspace(rf.RECOVERY_RANGE[0], rf.RECOVERY_RANGE[1], 21), 4)

OBJECTIVE_COLUMN = {"lcow": "lcow", "sec": "sec", "max_recovery": "recovery"}


def base_name(scenario):
    return scenario.removesuffix("_margin")


def best_of(objective, candidates):
    """Best solved candidate: lowest LCOW or SEC, or highest recovery."""
    solved = [c for c in candidates if c is not None]
    if not solved:
        return None
    column = OBJECTIVE_COLUMN[objective]
    return (max if objective == "max_recovery" else min)(solved, key=lambda c: c[column])


def violations(spec, true):
    """Relative violations of the nominal constraints by the true outputs (0 when satisfied)."""
    limits = [
        ("permeate_ppm<=", true["permeate_ppm"], spec.get("permeate_max", 500.0), -1),
        ("flux_out>=", true["flux_out"], spec.get("flux_out_min", 1.0), 1),
        ("pressure<=", true["pressure"], spec.get("pressure_max", 80.0), -1),
    ]
    if "flux_avg_min" in spec:
        limits.append(("flux_avg>=", true["flux_avg"], spec["flux_avg_min"], 1))
    if "lcow_max" in spec:
        limits.append(("lcow<=", true["lcow"], spec["lcow_max"], -1))
    result = {}
    for name, actual, limit, direction in limits:
        miss = (limit - actual) if direction > 0 else (actual - limit)
        result[name] = max(0.0, miss / abs(limit))
    return result


def _init():
    rf.quiet()
    global SOLVER
    SOLVER = rf.get_solver()


def _evaluate(point):
    return rf.evaluate(*point, solver=SOLVER)


def _optimize(kwargs):
    return rf.optimize(**kwargs, solver=SOLVER)


def key(kwargs):
    return tuple(sorted(kwargs.items()))


def read_csv(path):
    with open(path, newline="") as f:
        return [{k: (v if k in ("scenario", "method") else float(v)) for k, v in row.items()}
                for row in csv.DictReader(f)]


def fmt(x, digits=4):
    return "n/a" if x is None else f"{x:.{digits}f}"


def watertap_optima(pool):
    """Returns (best per scenario, every run per scenario, minimum LCOW per grid recovery at 35 g/kg)."""
    plans = {}
    for name, spec in SCENARIOS.items():
        if "recovery" in spec:
            plans[name] = {"fixed recovery": spec}
        else:
            plans[name] = {f"start {s}": dict(spec, start_recovery=s) for s in STARTS}
            plans[name].update({f"grid {r}": dict(spec, recovery=float(r)) for r in GRID})
    plans[PARETO] = {f"grid {r}": dict(PARETO_SPEC, recovery=float(r)) for r in GRID}

    unique = {key(kw): kw for plan in plans.values() for kw in plan.values()}
    solved = dict(zip(unique, pool.map(_optimize, unique.values())))
    runs = {name: {label: solved[key(kw)] for label, kw in plan.items()} for name, plan in plans.items()}

    refine = {}
    for name, spec in SCENARIOS.items():
        grid = [runs[name][f"grid {r}"] for r in GRID if "recovery" not in spec]
        best = best_of(spec["objective"], grid)
        if best is not None:
            refine[name] = dict(spec, start_recovery=round(best["recovery"], 4))
    for name, result in zip(refine, pool.map(_optimize, refine.values())):
        runs[name]["grid best, then free"] = result

    best = {name: best_of(spec["objective"], runs[name].values()) for name, spec in SCENARIOS.items()}
    curve = [(float(r), runs[PARETO][f"grid {r}"]) for r in GRID]
    return best, runs, [(r, o) for r, o in curve if o is not None]


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    optima = read_csv(RESULTS / "opennn_optima.csv")
    fronts = {p.stem.removeprefix(f"pareto_{PARETO}_"): read_csv(p)
              for p in sorted(RESULTS.glob(f"pareto_{PARETO}_*.csv"))}

    points = [(r["salinity"], r["recovery"], r["pressure"]) for r in optima]
    for rows in fronts.values():
        points += [(r["salinity"], r["recovery"], r["pressure"]) for r in rows]

    with Pool(workers, initializer=_init) as pool:
        truths = pool.map(_evaluate, points, chunksize=2)
        best, runs, curve = watertap_optima(pool)

    # Single-objective scenarios and the advised Pareto points.
    rows = []
    for k, r in enumerate(optima):
        true = truths[k]
        spec = SCENARIOS.get(base_name(r["scenario"]), PARETO_SPEC)
        column = OBJECTIVE_COLUMN[spec["objective"]]
        optimum = best.get(base_name(r["scenario"]))
        row = {"scenario": r["scenario"], "method": r["method"], "salinity": r["salinity"],
               "recovery": r["recovery"], "pressure": r["pressure"], "objective": column,
               "predicted": r[column], "true": None if true is None else true[column],
               "watertap_optimum": None if optimum is None else optimum[column],
               "gap_percent": None, "worst_violation": ""}
        if true is None:
            row["feasible"] = "flowsheet failed"
        else:
            v = violations(spec, true)
            worst = max(v, key=v.get)
            if v[worst] > 0:
                row["worst_violation"] = f"{worst} by {100 * v[worst]:.2f} %"
            row["feasible"] = "yes" if v[worst] <= 1e-3 else "no"
            if optimum is not None:
                sign = -1.0 if column == "recovery" else 1.0
                row["gap_percent"] = 100.0 * sign * (true[column] - optimum[column]) / optimum[column]
            for name in rf.OUTPUTS:
                row["true_" + name] = true[name]
                row["predicted_" + name] = r[name]
        rows.append(row)

    columns = ["scenario", "method", "salinity", "recovery", "pressure", "objective", "predicted",
               "true", "watertap_optimum", "gap_percent", "feasible", "worst_violation"]
    columns += [p + n for n in rf.OUTPUTS for p in ("predicted_", "true_")]
    with open(RESULTS / "comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in columns})

    # Pareto fronts: each point against WaterTAP's minimum LCOW at that recovery.
    curve_r = np.array([r for r, _ in curve])
    curve_lcow = np.array([o["lcow"] for _, o in curve])
    with open(RESULTS / "watertap_lcow_by_recovery.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(rf.INPUTS + rf.OUTPUTS)
        for _, o in curve:
            writer.writerow([o[k] for k in rf.INPUTS + rf.OUTPUTS])

    pareto_rows = []
    offset = len(optima)
    for method, front in fronts.items():
        for i, r in enumerate(front):
            true = truths[offset + i]
            row = {"method": method, "recovery": r["recovery"], "pressure": r["pressure"],
                   "predicted_lcow": r["lcow"], "predicted_flux_out": r["flux_out"],
                   "predicted_permeate_ppm": r["permeate_ppm"],
                   "minimum_lcow_at_recovery": float(np.interp(r["recovery"], curve_r, curve_lcow))}
            if true is not None:
                v = violations(PARETO_SPEC, true)
                row.update(true_lcow=true["lcow"], true_flux_out=true["flux_out"],
                           true_permeate_ppm=true["permeate_ppm"],
                           feasible="yes" if max(v.values()) <= 1e-3 else "no",
                           excess_percent=100.0 * (true["lcow"] / row["minimum_lcow_at_recovery"] - 1.0))
            else:
                row["feasible"] = "flowsheet failed"
            pareto_rows.append(row)
        offset += len(front)

    pareto_columns = ["method", "recovery", "pressure", "predicted_lcow", "true_lcow",
                      "minimum_lcow_at_recovery", "excess_percent", "predicted_flux_out",
                      "true_flux_out", "predicted_permeate_ppm", "true_permeate_ppm", "feasible"]
    with open(RESULTS / "pareto_check.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=pareto_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(pareto_rows)

    # Markdown summary.
    lines = ["Gap: how much worse WaterTAP's value at the OpenNN point is than WaterTAP's best optimum "
             "(negative = better, which only an infeasible point can be unless WaterTAP's optimum is local).",
             "Feasible: the nominal constraints hold in WaterTAP within 0.1 %.", "",
             "| Scenario | Method | Recovery | Pressure (bar) | Objective | OpenNN predicted | WaterTAP at that point "
             "| WaterTAP optimum | Gap | Feasible in WaterTAP |",
             "|---|---|---:|---:|---|---:|---:|---:|---:|---|"]
    for row in rows:
        gap = "" if row["gap_percent"] is None else f"{row['gap_percent']:+.2f} %"
        feasible = row["feasible"] + (f" ({row['worst_violation']})" if row["worst_violation"] else "")
        lines.append(f"| {row['scenario']} | {row['method']} | {row['recovery']:.4f} | {row['pressure']:.2f} | "
                     f"{row['objective']} | {fmt(row['predicted'])} | {fmt(row['true'])} | "
                     f"{fmt(row['watertap_optimum'])} | {gap} | {feasible} |")

    lines += ["", "WaterTAP optima:", "",
              "| Scenario | Run | Recovery | Pressure (bar) | LCOW | SEC | Permeate (ppm) | Outlet flux | Average flux | Area (m2) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, spec in SCENARIOS.items():
        shown = {label: o for label, o in runs[name].items() if not label.startswith("grid 0")}
        grid = [o for label, o in runs[name].items() if label.startswith("grid 0")]
        if grid:
            shown["best grid point"] = best_of(spec["objective"], grid)
        for label, o in shown.items():
            if o is None:
                lines.append(f"| {name} | {label} | failed ||||||||")
                continue
            mark = " **(best)**" if o is best[name] else ""
            lines.append(f"| {name} | {label}{mark} | {o['recovery']:.4f} | {o['pressure']:.2f} | {o['lcow']:.4f} | "
                         f"{o['sec']:.4f} | {o['permeate_ppm']:.1f} | {o['flux_out']:.3f} | {o['flux_avg']:.2f} | "
                         f"{o['area']:.1f} |")
    lines.append("")
    for method in fronts:
        front_rows = [r for r in pareto_rows if r["method"] == method]
        ok = [r for r in front_rows if r["feasible"] == "yes"]
        excess = [r["excess_percent"] for r in ok]
        summary = (f"median {np.median(excess):+.2f} %, worst {np.max(excess):+.2f} %" if excess else "none feasible")
        lines.append(f"- Pareto front {method}: {len(front_rows)} points, {len(ok)} feasible in WaterTAP; "
                     f"true LCOW of the feasible ones above WaterTAP's minimum at the same recovery: {summary}.")
    (RESULTS / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
