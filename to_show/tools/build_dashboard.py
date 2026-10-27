"""Builds to_show/water_treatment_hmi.html: one self-contained page that opens offline in any browser.

Inlines src/style.css, src/model.js and src/app.js into src/index.html, with a JSON block holding:
  - the network weights (weights/<plant>_network.json, from export_weights.py),
  - the OpenNN optima over the disturbance grid (models/<plant>/results/dashboard_optima.csv)
    with their WaterTAP solutions (data/<plant>_optima_verified.csv, from verify_points.py),
  - the default operations that are feasible in WaterTAP (data/<plant>_defaults_verified.csv) and
    that the network does not show over a limit,
  - the limits, safety margins and model facts shown on the page, including how the retrained
    network compares with the original one (models/<plant>/comparison.csv),
  - for the wastewater plant, once run_storm.py has made it, the storm network (seventh input:
    rain), which the page uses while it rains: its weights, margins, optima at each rain level
    (data/bsm2_rain_optima_verified.csv) and facts (models/bsm2_rain/comparison.csv).

    python build_dashboard.py [--out=<file>]      (default: to_show/water_treatment_hmi.html)
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np

from plants import DATASET, ORIGINAL_ROOT, ROOT, TO_SHOW

SRC = TO_SHOW / "src"
ORIGINAL_DATASET = {"bsm2": ORIGINAL_ROOT["bsm2"] / "data" / "bsm2_dataset_infill.csv",
                    "ro": ORIGINAL_ROOT["ro"] / "data" / "ro_dataset.csv"}


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_margins(path):
    return {(r["output"], float(r["bound"])): float(r["margin"]) for r in read_rows(path)}


def read_summary(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("test_r2_"):
            values[parts[0][len("test_r2_"):]] = float(parts[1])
        elif parts and parts[0] in ("hidden_neurons", "hidden_layers"):
            values[parts[0]] = int(parts[1])
    return values


def architecture(inputs, outputs, summary):
    neurons, layers = summary.get("hidden_neurons", 32), summary.get("hidden_layers", 1)
    hidden = f"{neurons} hidden neurons" if layers == 1 else f"{layers} hidden layers of {neurons} neurons"
    return f"{len(inputs)} inputs, {hidden}, {len(outputs)} outputs"


def count_rows(path):
    with open(path, newline="") as f:
        return sum(1 for _ in f) - 1


def r2_below(plant, key, limit):
    """Test R² of one output over the test samples whose true value is below `limit`."""
    rows = read_rows(ROOT[plant] / "results" / "test_predictions.csv")
    y = np.array([float(r[key]) for r in rows])
    p = np.array([float(r[f"{key}_predicted"]) for r in rows])
    mask = y < limit
    return 1.0 - float(np.sum((y[mask] - p[mask]) ** 2) / np.sum((y[mask] - y[mask].mean()) ** 2))


def forward(model, x):
    """The network's prediction, as src/model.js computes it."""
    z = np.array([(x[i["name"]] - i["mean"]) / i["std"] for i in model["inputs"]])
    for layer in model["layers"]:
        z = np.array(layer["biases"]) + z @ np.array(layer["weights"])
        if layer["activation"] == "Tanh":
            z = np.tanh(z)
    return {o["name"]: float(np.exp(z[k]) if o["scaler"] == "Logarithm" else z[k] * o["std"] + o["mean"])
            for k, o in enumerate(model["outputs"])}


SUBSET_TEXT = {"all": "", "nh4_2_to_8": " where it is 2 to 8 mg/L", "nh4_above_8": " where it is above 8 mg/L"}


def read_comparison(plant):
    path = ROOT[plant] / "comparison.csv"
    return {(r["subset"], r["output"], r["network"]): r for r in read_rows(path)} if path.exists() else {}


def ro_guard():
    """Smallest pressure*(1 - recovery)/salinity in the RO training data: the domain guard the OpenNN
    sweep kept (the corner of the input box below it has no data)."""
    return min(float(r["pressure"]) * (1.0 - float(r["recovery"])) / float(r["salinity"]) for r in read_rows(DATASET["ro"]))


def margin_data(plant, keys):
    """Per constrained output, the validation samples' true value and absolute error: the page
    computes the safety margin of any bound from them, as OpenNN does for the stored optima (95th
    percentile of the error among samples within a factor of two of the bound)."""
    rows = read_rows(ROOT[plant] / "results" / "validation_predictions.csv")
    short = lambda v: float(f"{v:.6g}")
    return {k: [[short(float(r[k])), short(abs(float(r[f"{k}_predicted"]) - float(r[k])))] for r in rows] for k in keys}


def mean_error(plant, subset, key, network):
    """A network's mean absolute error on a subset of held-out simulations (comparison.csv), or None."""
    row = read_comparison(plant).get((subset, key, network))
    return float(row["mae"]) if row else None


def comparison_text(plant, items):
    """One sentence on the held-out simulations: (output, subset, label, unit, digits) per item."""
    rows = read_comparison(plant)
    parts, samples = [], None
    for key, subset, label, unit, digits in items:
        original, retrained = rows.get((subset, key, "original")), rows.get((subset, key, "retrained"))
        if not (original and retrained):
            continue
        samples = samples or int(rows[("all", key, "original")]["samples"])
        before, after = float(original["mae"]), float(retrained["mae"])
        parts.append(f"{after:.{digits}f} {unit} in {label}{SUBSET_TEXT[subset]} (original network {before:.{digits}f})")
    if not parts:
        return ""
    return (f"On {samples} new simulations that neither network saw, the retrained network's mean error is "
            + " and ".join(parts) + ".")


def value_of(row, k):
    """An input of a stored row; dry-weather files have no rain column (no rain)."""
    return float(row.get(k) or 0.0) if k == "rain" else float(row[k])


def point(row, inputs, outputs, feasible_fn):
    """One stored operating point: inputs, OpenNN prediction (when present) and WaterTAP solution."""
    x = {k: value_of(row, k) for k in inputs}
    y = {k: float(row[k]) for k in outputs if row.get(k, "") != ""}
    true = None
    if row.get("status") in ("ok", "washout") and row.get(f"true_{outputs[0]}", "") != "":
        true = {k: float(row[f"true_{k}"]) for k in outputs}
    return {"x": x, "y": y or None, "true": true, "feasible": bool(true) and feasible_fn(x, true)}


def paths_data(plant, inputs, outputs, disturbance):
    """WaterTAP solutions along the demo's paths (data/<plant>_paths_verified.csv, from scenarios.py):
    compact rows of inputs then outputs, and the held set-points of each path."""
    path = TO_SHOW / "data" / f"{plant}_paths_verified.csv"
    if not path.exists():
        return None, set(), None
    every = read_rows(path)
    optimum_path = TO_SHOW / "data" / f"{plant}_optimum_paths_verified.csv"
    optimum_every = read_rows(optimum_path) if optimum_path.exists() else []
    solved = lambda rows: [r for r in rows if r["status"] in ("ok", "washout")]
    short = lambda v: float(f"{float(v):.6g}")
    data = {"inputs": inputs, "outputs": outputs,
            "rows": [[short(value_of(r, k)) for k in inputs] + [short(r[f"true_{k}"]) for k in outputs]
                     for r in solved(every) + solved(optimum_every)]}
    # Only paths solved at every grid value serve the guided demo (held at high salinity, some
    # desalination set-points fall below the brine's osmotic pressure and have no solution): the
    # default's own path, and the path of the optimum the demo applies at the default's condition.
    broken = {r["scenario"] for r in every if r["status"] not in ("ok", "washout")}
    held = {tuple(f"{value_of(r, k):.6g}" for k in inputs if k != disturbance) for r in solved(every) if r["scenario"] not in broken}
    starts = None
    if optimum_every:
        broken = {r["scenario"] for r in optimum_every if r["status"] not in ("ok", "washout")}
        starts = {round(float(r["scenario"]), 3) for r in optimum_every if r["scenario"] not in broken}
    return data, held, starts


def defaults_for(plant, model, inputs, outputs, feasible, held=frozenset(), disturbance=None, starts=None):
    """Default operations feasible in WaterTAP that the network also shows within every limit; `path`
    marks those whose set-points, and the optimum the demo applies at their condition, have stored
    paths through the condition range."""
    stored = [point(r, inputs, outputs, feasible) for r in read_rows(TO_SHOW / "data" / f"{plant}_defaults_verified.csv")]
    kept = [d for d in stored if d["feasible"] and feasible(d["x"], forward(model, d["x"]))]
    for d in kept:
        d["path"] = (tuple(f"{d['x'][k]:.6g}" for k in inputs if k != disturbance) in held
                     and (starts is None or round(d["x"][disturbance], 3) in starts))
    print(f"{plant}: {len(kept)} of {sum(d['feasible'] for d in stored)} WaterTAP-feasible default operations "
          f"are within every limit for the network too; {sum(d['path'] for d in kept)} have a stored path")
    return kept


def network_facts(net, model, summary):
    """The facts of a wastewater network shown on the page: architecture, weights and test R²."""
    inputs, outputs = model["inputs"], model["outputs"]
    return {
        "rows": count_rows(DATASET[net]),
        "architecture": architecture(inputs, outputs, summary),
        "parameters": sum(len(l["biases"]) + sum(len(r) for r in l["weights"]) for l in model["layers"]),
        "r2_text": (f"{summary['sec']:.3f} for energy, {summary['lcow']:.4f} for cost and {summary['biogas']:.4f} for biogas; "
                    f"{summary['nh4']:.2f} for ammonium overall, {r2_below(net, 'nh4', 8.0):.2f} below 8 mg/L where the limit is"),
    }


def stored_facts(stored):
    return {"optima": len(stored), "optima_feasible": sum(p["feasible"] for p in stored),
            "optima_unsolved": sum(p["true"] is None for p in stored)}


def bsm2():
    model = json.loads((TO_SHOW / "weights" / "bsm2_network.json").read_text())
    inputs = [i["name"] for i in model["inputs"]]
    outputs = [o["name"] for o in model["outputs"]]
    margins = read_margins(ROOT["bsm2"] / "model" / "constraint_margins.csv")
    bounds = {"nh4": 4.0, "tn": 18.0, "cod": 100.0, "tss": 30.0, "bod5": 10.0}
    limits = [{"output": k, "max": v, "margin": margins[(k, v)]} for k, v in bounds.items()]

    def feasible(x, y):
        return all(y[k] <= v * (1 + 1e-3) for k, v in bounds.items())

    grid = [16600.0 + 300.0 * k for k in range(28)]
    optima_rows = read_rows(TO_SHOW / "data" / "bsm2_optima_verified.csv")
    objectives = {}
    for name in ("min_energy", "min_cost", "max_biogas"):
        by_value = {round(float(r["influent"])): point(r, inputs, outputs, feasible)
                    for r in optima_rows if r["objective"] == name}
        objectives[name] = [by_value.get(round(g)) for g in grid]

    paths, held, starts = paths_data("bsm2", inputs, outputs, "influent")
    defaults = defaults_for("bsm2", model, inputs, outputs, feasible, held, "influent", starts)
    summary = read_summary(ROOT["bsm2"] / "model" / "training_summary.txt")
    facts = network_facts("bsm2", model, summary)
    facts.update({
        "source": (f"WaterTAP's steady-state BSM2 plant (ASM1 activated sludge, ADM1 digester), sampled over the five "
                   f"set-points and the influent flow, with one round of extra simulations where the optimizer went. "
                   f"For this page it was retrained with {facts['rows'] - count_rows(ORIGINAL_DATASET['bsm2']):,} more, "
                   f"half of them near the effluent limits."),
        "comparison": comparison_text("bsm2", [("sec", "all", "energy", "kWh/m³", 4),
                                               ("nh4", "nh4_2_to_8", "ammonium", "mg/L", 2)]),
        "nh4_high_mae": mean_error("bsm2", "nh4_above_8", "nh4", "retrained"),
        "defaults": len(defaults),
        **stored_facts([p for list_ in objectives.values() for p in list_ if p]),
    })
    data = {"model": model, "disturbance": {"name": "influent", "grid": grid}, "limits": limits,
            "margin_data": margin_data("bsm2", list(bounds)), "paths": paths,
            "objectives": objectives, "defaults": defaults, "facts": facts}
    storm = storm_network(bounds, feasible, grid)
    if storm:
        data["storm"] = storm
    return data


def storm_network(bounds, feasible, grid):
    """The storm network (models/bsm2_rain, a seventh input: rain), which the page uses while it
    rains: its weights, the validation errors behind its safety margins, its optima at each rain
    level of the storm (level after level, each over the influent grid) and its facts. None until
    run_storm.py has made it. At no rain the page keeps the dry-weather network, more accurate there."""
    net = "bsm2_rain"
    weights, verified = TO_SHOW / "weights" / f"{net}_network.json", TO_SHOW / "data" / f"{net}_optima_verified.csv"
    if not (weights.exists() and verified.exists()):
        return None
    model = json.loads(weights.read_text())
    inputs = [i["name"] for i in model["inputs"]]
    outputs = [o["name"] for o in model["outputs"]]
    optima_rows = read_rows(verified)
    levels = sorted({round(value_of(r, "rain")) for r in optima_rows} - {0})
    objectives = {}
    for name in ("min_energy", "min_cost", "max_biogas"):
        by_value = {(round(value_of(r, "rain")), round(float(r["influent"]))): point(r, inputs, outputs, feasible)
                    for r in optima_rows if r["objective"] == name}
        objectives[name] = [by_value.get((level, round(g))) for level in levels for g in grid]

    # What it learned from: the dry-weather network's simulations, the wet-weather ones, and the
    # optima of its earlier rounds solved in WaterTAP (run_storm.py retrains when one misses a limit).
    wet = count_rows(ROOT[net] / "data" / "rain_simulations.csv") - count_rows(ROOT[net] / "data" / "holdout.csv")
    checked, missed = 0, 0
    for path in sorted((TO_SHOW / "data").glob(f"{net}_optima_verified_round*.csv")):
        solved = [r for r in read_rows(path) if r["status"] in ("ok", "washout")]
        checked += len(solved)
        missed += sum(not all(float(r[f"true_{k}"]) <= v * (1 + 1e-3) for k, v in bounds.items()) for r in solved)
    source = f"The storm network learned from the same simulations and {wet:,} wet-weather ones with up to 6,000 m³/d of rain"
    source += (f", and from the {checked} optima of its first version solved in WaterTAP, {missed} of which missed a limit."
               if checked else ".")

    # Against the dry-weather network: on wet held-out simulations (where that one ignores the
    # rain) and on dry ones, where ammonium is 2 to 8 mg/L, near the limit.
    error = lambda subset, network: mean_error(net, subset, "nh4", network)
    comparison = ""
    rows = read_comparison(net)
    if ("wet_nh4_2_to_8", "nh4", "storm") in rows:
        comparison = (f"On {int(rows[('wet', 'nh4', 'storm')]['samples'])} wet-weather simulations it did not see, its mean ammonium "
                      f"error is {error('wet_nh4_2_to_8', 'storm'):.2f} mg/L where ammonium is 2 to 8 mg/L; the dry-weather network, "
                      f"which ignores the rain, is off by {error('wet_nh4_2_to_8', 'dry'):.2f} mg/L there. In dry weather it is the less "
                      f"accurate of the two ({error('nh4_2_to_8', 'storm'):.2f} against {error('nh4_2_to_8', 'dry'):.2f} mg/L), "
                      f"so the page uses it only while it rains.")
    summary = read_summary(ROOT[net] / "model" / "training_summary.txt")
    facts = network_facts(net, model, summary)
    facts.update({
        "source": source,
        "comparison": comparison,
        "nh4_high_mae": error("wet_nh4_above_8", "storm"),
        **stored_facts([p for list_ in objectives.values() for p in list_ if p]),
    })
    print(f"bsm2 storm network: {facts['optima_feasible']} of {facts['optima']} optima at rain {levels} feasible in WaterTAP")
    return {"model": model, "margin_data": margin_data(net, list(bounds)), "objectives": objectives,
            "rain_levels": [float(level) for level in levels], "facts": facts}


def ro():
    model = json.loads((TO_SHOW / "weights" / "ro_network.json").read_text())
    inputs = [i["name"] for i in model["inputs"]]
    outputs = [o["name"] for o in model["outputs"]]
    margins = read_margins(ROOT["ro"] / "model" / "constraint_margins.csv")
    limits = [{"output": "permeate_ppm", "max": 500.0, "margin": margins[("permeate_ppm", 500.0)]},
              {"output": "flux_out", "min": 1.0, "margin": margins[("flux_out", 1.0)]}]

    def feasible(x, y):
        return y["permeate_ppm"] <= 500.5 and y["flux_out"] >= 0.999 and x["pressure"] <= 80.0 + 1e-6

    grid = [26.0 + k for k in range(19)]
    optima_rows = [r for r in read_rows(TO_SHOW / "data" / "ro_optima_verified.csv") if r["objective"] == "min_cost"]
    by_value = {round(float(r["salinity"])): point(r, inputs, outputs, feasible) for r in optima_rows}
    objectives = {"min_cost": [by_value.get(round(g)) for g in grid]}

    paths, held, starts = paths_data("ro", inputs, outputs, "salinity")
    defaults = defaults_for("ro", model, inputs, outputs, feasible, held, "salinity", starts)
    summary = read_summary(ROOT["ro"] / "model" / "training_summary.txt")
    rows, original = count_rows(DATASET["ro"]), count_rows(ORIGINAL_DATASET["ro"])
    stored = [p for p in objectives["min_cost"] if p]
    facts = {
        "rows": rows,
        "architecture": architecture(inputs, outputs, summary),
        "parameters": sum(len(l["biases"]) + sum(len(r) for r in l["weights"]) for l in model["layers"]),
        "r2_text": (f"{summary['lcow']:.4f} for cost, {summary['sec']:.4f} for energy, "
                    f"{summary['permeate_ppm']:.4f} for permeate salinity and {summary['flux_out']:.4f} for the brine-end flux"),
        "source": (f"WaterTAP's reverse osmosis flowsheet with a pressure exchanger (0D membrane, NaCl), sampled over "
                   f"feed salinity, recovery and feed pressure. For this page it was retrained with {rows - original:,} more simulations."),
        "comparison": comparison_text("ro", [("lcow", "all", "cost", "$/m³", 5), ("sec", "all", "energy", "kWh/m³", 4)]),
        "defaults": len(defaults),
        "optima": len(stored),
        "optima_feasible": sum(p["feasible"] for p in stored),
        "optima_unsolved": sum(p["true"] is None for p in stored),
    }
    return {"model": model, "disturbance": {"name": "salinity", "grid": grid}, "limits": limits,
            "margin_data": margin_data("ro", ["permeate_ppm", "flux_out"]), "paths": paths,
            "input_limits": [{"input": "pressure", "max": 80.0, "margin": 2.0}],
            "guard": ro_guard(), "objectives": objectives, "defaults": defaults, "facts": facts}


def main():
    data = {"plants": {"bsm2": bsm2(), "ro": ro()}}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = (SRC / "index.html").read_text(encoding="utf-8")
    page = page.replace("/*__STYLE__*/", (SRC / "style.css").read_text(encoding="utf-8"))
    page = page.replace("/*__MODEL__*/", (SRC / "model.js").read_text(encoding="utf-8"))
    page = page.replace("/*__OPTIMIZER__*/", (SRC / "optimizer.js").read_text(encoding="utf-8"))
    page = page.replace("/*__APP__*/", (SRC / "app.js").read_text(encoding="utf-8"))
    page = page.replace("__DATA__", blob)
    out = next((a[len("--out="):] for a in sys.argv[1:] if a.startswith("--out=")), None)
    target = Path(out) if out else TO_SHOW / "water_treatment_hmi.html"
    target.write_text(page, encoding="utf-8")
    for plant, p in data["plants"].items():
        f = p["facts"]
        print(f"{plant}: {f['defaults']} default operations, {f['optima_feasible']} of {f['optima']} optima feasible in WaterTAP")
    print(f"Wrote {target} ({target.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
