"""How the storm network (seventh input: rain) compares with the page's dry-weather network.

    python compare_rain.py

Writes to_show/models/bsm2_rain/comparison.csv (the format of compare_networks.py: networks "dry"
and "storm" on the dry held-out simulations and on the wet ones, subsets "wet...", by NH4 range)
and to_show/models/bsm2_rain/summary.txt:
  - on the dry network's held-out simulations (models/bsm2/data/holdout.csv, no rain), the mean
    error of both networks, overall and for NH4 between 2 and 8 mg/L;
  - on the wet-weather held-out simulations (models/bsm2_rain/data/holdout.csv), the storm
    network's mean error, by rain flow, and both networks' by NH4 range (the dry network ignores
    the rain: what the page would show in a storm without the storm network);
  - the storm optima solved in WaterTAP (data/bsm2_rain_optima_verified.csv): solved and within
    every limit, per rain level and objective, and at no rain their objective against the dry
    network's optima (data/bsm2_optima_verified.csv), both as WaterTAP solved them.
"""

import csv
import json
from collections import defaultdict

import numpy as np

from plants import ROOT, TO_SHOW

OUTPUTS = ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]
BOUNDS = {"nh4": 4.0, "tn": 18.0, "cod": 100.0, "tss": 30.0, "bod5": 10.0}
OBJECTIVE_OUTPUT = {"min_energy": "sec", "min_cost": "lcow", "max_biogas": "biogas"}


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def predict(model, rows):
    """The exported network's predictions (src/model.js arithmetic), rain 0 where a row has none."""
    x = np.array([[float(r.get(i["name"]) or 0.0) for i in model["inputs"]] for r in rows])
    z = (x - np.array([i["mean"] for i in model["inputs"]])) / np.array([i["std"] for i in model["inputs"]])
    for layer in model["layers"]:
        z = np.array(layer["biases"]) + z @ np.array(layer["weights"])
        if layer["activation"] == "Tanh":
            z = np.tanh(z)
    out = {}
    for k, o in enumerate(model["outputs"]):
        out[o["name"]] = np.exp(z[:, k]) if o["scaler"] == "Logarithm" else z[:, k] * o["std"] + o["mean"]
    return out


def mae(rows, predicted, key, mask=None):
    truth = np.array([float(r[key]) for r in rows])
    error = np.abs(predicted[key] - truth)
    return float(error[mask].mean()) if mask is not None and mask.any() else float(error.mean())


def r2(y, p):
    return 1.0 - float(np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)) if len(y) > 1 else float("nan")


def comparison_rows(rows, networks, subsets):
    """compare_networks.py's rows: subset, samples, output, network, R², mean absolute error."""
    out = []
    for subset, mask in subsets.items():
        for key in OUTPUTS:
            y = np.array([float(r[key]) for r in rows])[mask]
            for name, p in networks.items():
                out.append([subset, int(mask.sum()), key, name, f"{r2(y, p[key][mask]):.6g}",
                            f"{float(np.mean(np.abs(y - p[key][mask]))):.6g}"])
    return out


def main():
    dry_model = json.loads((TO_SHOW / "weights" / "bsm2_network.json").read_text())
    rain_model = json.loads((TO_SHOW / "weights" / "bsm2_rain_network.json").read_text())
    lines = []

    holdout = read(ROOT["bsm2"] / "data" / "holdout.csv")
    nh4 = np.array([float(r["nh4"]) for r in holdout])
    band = (nh4 >= 2) & (nh4 < 8)
    table = comparison_rows(holdout, {"dry": predict(dry_model, holdout), "storm": predict(rain_model, holdout)},
                            {"all": np.ones(len(holdout), bool), "nh4_2_to_8": (nh4 >= 2) & (nh4 < 8), "nh4_above_8": nh4 >= 8})
    lines.append(f"Dry held-out simulations ({len(holdout)}, {int(band.sum())} with NH4 2-8 mg/L): mean error, dry network / storm network")
    for name, model in (("dry", dry_model), ("storm", rain_model)):
        p = predict(model, holdout)
        lines.append(f"  {name:5s}  nh4 {mae(holdout, p, 'nh4'):.3f}  nh4 2-8 {mae(holdout, p, 'nh4', band):.3f}  "
                     f"tn {mae(holdout, p, 'tn'):.3f}  sec {mae(holdout, p, 'sec'):.4f}  lcow {mae(holdout, p, 'lcow'):.5f}  "
                     f"biogas {mae(holdout, p, 'biogas'):.1f}")

    wet = read(ROOT["bsm2_rain"] / "data" / "holdout.csv")
    if wet:
        p, p_dry = predict(rain_model, wet), predict(dry_model, wet)
        nh4 = np.array([float(r["nh4"]) for r in wet])
        ranges = {"wet": np.ones(len(wet), bool), "wet_nh4_2_to_8": (nh4 >= 2) & (nh4 < 8), "wet_nh4_above_8": nh4 >= 8}
        table += comparison_rows(wet, {"dry": p_dry, "storm": p}, ranges)
        rain = np.array([float(r["rain"]) for r in wet])
        lines.append(f"Wet held-out simulations ({len(wet)}): storm network's mean error by rain flow")
        for lo, hi in ((0, 2000), (2000, 4000), (4000, 6001)):
            mask = (rain >= lo) & (rain < hi)
            if mask.any():
                lines.append(f"  rain {lo:>5}-{min(hi, 6000):<5} ({int(mask.sum()):3d})  nh4 {mae(wet, p, 'nh4', mask):.3f}  "
                             f"tn {mae(wet, p, 'tn', mask):.3f}  sec {mae(wet, p, 'sec', mask):.4f}  cod {mae(wet, p, 'cod', mask):.2f}")
        lines.append("  NH4 mean error by NH4 range: storm network / dry network (which ignores the rain)")
        for name, label in (("wet_nh4_2_to_8", "2-8 mg/L"), ("wet_nh4_above_8", "above 8")):
            mask = ranges[name]
            if mask.any():
                lines.append(f"  nh4 {label:8s} ({int(mask.sum()):3d})  storm {mae(wet, p, 'nh4', mask):.3f}  dry {mae(wet, p_dry, 'nh4', mask):.3f}")

    verified = TO_SHOW / "data" / "bsm2_rain_optima_verified.csv"
    if verified.exists():
        rows = read(verified)
        groups = defaultdict(list)
        for r in rows:
            groups[(round(float(r["rain"])), r["objective"])].append(r)
        lines.append("Storm optima in WaterTAP: solved / within every limit / of all, per rain level and objective")
        for (rain_level, objective), group in sorted(groups.items()):
            solved = [r for r in group if r["status"] in ("ok", "washout")]
            within = [r for r in solved if all(float(r[f"true_{k}"]) <= v * (1 + 1e-3) for k, v in BOUNDS.items())]
            worst = max((float(r["true_nh4"]) for r in solved), default=float("nan"))
            lines.append(f"  rain {rain_level:>5} {objective:11s} {len(solved):2d} / {len(within):2d} / {len(group):2d}   highest NH4 {worst:.2f}")
        dry = {(r["objective"], round(float(r["influent"]))): r for r in read(TO_SHOW / "data" / "bsm2_optima_verified.csv")
               if r["status"] == "ok"}
        lines.append("At no rain, storm optima against the dry network's optima (WaterTAP values; + = storm better)")
        for objective, key in OBJECTIVE_OUTPUT.items():
            changes = []
            for r in rows:
                other = dry.get((objective, round(float(r["influent"]))))
                if r["objective"] == objective and round(float(r["rain"])) == 0 and r["status"] == "ok" and other:
                    a, b = float(other[f"true_{key}"]), float(r[f"true_{key}"])
                    changes.append(100 * ((a - b) if objective != "max_biogas" else (b - a)) / abs(a))
            if changes:
                lines.append(f"  {objective:11s} median {np.median(changes):+.2f} %  (range {min(changes):+.2f} to {max(changes):+.2f}, {len(changes)} conditions)")

    with open(ROOT["bsm2_rain"] / "comparison.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["subset", "samples", "output", "network", "r2", "mae"])
        writer.writerows(table)
    text = "\n".join(lines) + "\n"
    (ROOT["bsm2_rain"] / "summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
