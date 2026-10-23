"""The optima of the original and the retrained network, both solved in WaterTAP, compared.

    python compare_optima.py ro|bsm2

Reads data/original_network/<plant>_optima_verified.csv (the original network's optima) and
data/<plant>_optima_verified.csv (the retrained network's), matched by objective and disturbance
value, and prints per objective: how many meet every limit in WaterTAP, and the objective that
WaterTAP gives at each network's answer.
"""

import csv
import sys

from plants import TO_SHOW

SETUP = {
    "ro": dict(disturbance="salinity", objectives={"min_cost": ("lcow", "min")},
               feasible=lambda r: (float(r["true_permeate_ppm"]) <= 500.5 and float(r["true_flux_out"]) >= 0.999
                                   and float(r["pressure"]) <= 80.0 + 1e-6)),
    "bsm2": dict(disturbance="influent",
                 objectives={"min_energy": ("sec", "min"), "min_cost": ("lcow", "min"), "max_biogas": ("biogas", "max")},
                 feasible=lambda r: all(float(r[f"true_{k}"]) <= v * 1.001
                                        for k, v in {"nh4": 4.0, "tn": 18.0, "cod": 100.0, "tss": 30.0, "bod5": 10.0}.items())),
}


def load(path, setup):
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["objective"] in setup["objectives"]]
    return {(r["objective"], round(float(r[setup["disturbance"]]))): r for r in rows}


def main():
    plant = sys.argv[1]
    setup = SETUP[plant]
    original = load(TO_SHOW / "data" / "original_network" / f"{plant}_optima_verified.csv", setup)
    retrained = load(TO_SHOW / "data" / f"{plant}_optima_verified.csv", setup)
    solved = lambda r: r is not None and r["status"] in ("ok", "washout")

    for objective, (key, sense) in setup["objectives"].items():
        points = sorted(k for k in original if k[0] == objective)
        both = [k for k in points if solved(original.get(k)) and solved(retrained.get(k))]
        feasible_o = sum(setup["feasible"](original[k]) for k in points if solved(original.get(k)))
        feasible_r = sum(setup["feasible"](retrained[k]) for k in points if solved(retrained.get(k)))
        print(f"{plant} {objective}: {len(points)} conditions; every limit met in WaterTAP: "
              f"original {feasible_o}, retrained {feasible_r}")
        gains, better = [], 0
        for k in both:
            if not (setup["feasible"](original[k]) and setup["feasible"](retrained[k])):
                continue
            a, b = float(original[k][f"true_{key}"]), float(retrained[k][f"true_{key}"])
            gain = 100.0 * ((a - b) if sense == "min" else (b - a)) / abs(a)
            gains.append(gain)
            better += gain > 0
        if gains:
            gains.sort()
            print(f"  where both are feasible ({len(gains)}): retrained better at {better}; "
                  f"{key} improvement median {gains[len(gains) // 2]:+.2f} %, range {gains[0]:+.2f} to {gains[-1]:+.2f} %")


if __name__ == "__main__":
    main()
