"""Runs the dynamic IWA BSM2 (bsm2-python, open loop) under a constant operating policy and returns
the benchmark scores: the building block for a policy -> KPI dataset (see README.md, track D1).

The policy is the oxygen-transfer coefficients of the aerated reactors R3-R5 (KLa, 1/d) and the
internal recycle flow (m3/d). The influent is BSM2's 609-day dynamic file in 15-minute steps.
The standard protocol simulates all 609 days and scores days 245-609; shorter horizons are for
tests and for screening.

Runs in the "bsm2" conda environment:

    python dynamic_policy.py [endtime_days] [evaluation_days]
"""

import sys
import time

import numpy as np

from bsm2_python.bsm2.init import asm1init_bsm2 as asm1init
from bsm2_python.bsm2.init import reginit_bsm2 as reginit
from bsm2_python.bsm2_ol import BSM2OL

DEFAULT_POLICY = {"kla3": float(reginit.KLA3), "kla4": float(reginit.KLA4), "kla5": float(reginit.KLA5),
                  "qintr": float(asm1init.QINTR)}

KPI_NAMES = ["iqi", "eqi", "sludge_production", "tss_mass", "carbon_mass", "ch4", "h2", "co2", "gas",
             "heat_demand", "mixing_energy", "pumping_energy", "aeration_energy", "oci"]


def evaluate(policy=None, endtime=609.0, evaluation_days=364.0):
    """Simulates BSM2 from its standard initial state under a constant policy.

    Returns the KPIs of get_final_performance (daily averages over the evaluation window, OCI and
    EQI as defined by the benchmark) plus the time (days) with effluent NH4 above 4 mg/L."""
    policy = dict(DEFAULT_POLICY, **(policy or {}))
    plant = BSM2OL(endtime=endtime, evaltime=np.array([endtime - evaluation_days, endtime]))
    plant.qintr = policy["qintr"]
    klas = np.array([0.0, 0.0, policy["kla3"], policy["kla4"], policy["kla5"]])
    for i in range(len(plant.simtime)):
        plant.step(i, klas)
    kpis = dict(zip(KPI_NAMES, plant.get_final_performance()))
    kpis["nh4_violation_days"] = plant.get_violations(("SNH",), (4,))["SNH"]
    return kpis


if __name__ == "__main__":
    endtime = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    evaluation_days = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    for policy in (None, {"kla3": 80.0, "kla4": 80.0, "kla5": 40.0}):
        start = time.time()
        kpis = evaluate(policy, endtime, evaluation_days)
        print("policy", policy or "default", f"{time.time() - start:.0f} s",
              {k: round(float(kpis[k]), 2) for k in ("eqi", "oci", "aeration_energy", "pumping_energy", "ch4",
                                                      "sludge_production", "nh4_violation_days")})
