"""WaterTAP's steady-state BSM2 plant (ASM1 activated sludge + ADM1 digester), used as the ground truth.

The flowsheet is watertap.flowsheets.full_water_resource_recovery_facility.BSM2 as shipped with
WaterTAP 1.8.0: BSM2 layout, simplified clarifiers (fixed split fractions), WaterTAPCosting.
Reactor volumes, clarifiers, digester and influent composition stay at WaterTAP's defaults.

Variables, with the units used in the dataset:
    do3, do4, do5  dissolved-oxygen set-points in the aerobic reactors R3-R5, mg/L
    recycle        internal (nitrate) recycle: fraction of the R5 outflow returned to R1, -
    wastage        fraction of the secondary-clarifier underflow wasted (1 - sludge recycle split), -
    influent       influent flow, m3/d (a disturbance, fixed in each scenario)
    lcow           levelized cost of water, $/m3 of influent
    sec            specific energy consumption, kWh/m3 of influent
    tss, cod, tn, bod5, nh4   effluent concentrations, mg/L
    biogas         digester gas flow, m3/d

Effluent limits (BSM2): tss <= 30, cod <= 100, tn <= 18, bod5 <= 10, nh4 <= 4 mg/L.
"""

import logging
import time

import pyomo.environ as pyo
from pyomo.environ import check_optimal_termination, value

import idaes.logger as idaeslog
from idaes.core.scaling.custom_scaler_base import ConstraintScalingScheme, CustomScalerBase
from idaes.core.util.model_serializer import from_json, to_json
from watertap.core.solvers import get_solver
from watertap.flowsheets.full_water_resource_recovery_facility import BSM2 as bsm2

INPUTS = ["do3", "do4", "do5", "recycle", "wastage", "influent"]
OUTPUTS = ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"]

BASE = {"do3": 1.72, "do4": 2.43, "do5": 0.449, "recycle": 0.6, "wastage": 0.015, "influent": 20648.0}
# DO starts at 0.5 mg/L: at 0.3 mg/L in all three tanks the nitrifiers wash out, and confirming
# washout costs minutes per point. WaterTAP's own optimum sits at 0.7-0.9 mg/L.
RANGES = {"do3": (0.5, 3.0), "do4": (0.5, 3.0), "do5": (0.5, 3.0), "recycle": (0.3, 0.8),
          "wastage": (0.006, 0.025), "influent": (16500.0, 24800.0)}
LIMITS = {"tss": 30.0, "cod": 100.0, "tn": 18.0, "bod5": 10.0, "nh4": 4.0}


def quiet():
    for name in ("idaes", "pyomo", "watertap"):
        logging.getLogger(name).setLevel(logging.ERROR)
    idaeslog.getLogger("idaes").setLevel(logging.ERROR)
    idaeslog.getInitLogger("idaes").setLevel(logging.ERROR)
    bsm2._log.setLevel(logging.ERROR)


# Steady-state ASM1 always admits a washout solution with no nitrifiers (X_BA = 0), and a warm start
# far from the previous point can land on it even where nitrification is sustainable (DO 3 mg/L gave
# NH4 41 mg/L that way). A floor on the autotrophs in the five reactors excludes that branch; where
# the nitrifying branch truly does not exist, the floored problem has no solution and the point is
# labelled "washout" (solved again without the floor).
AUTOTROPH_FLOOR = 1e-3  # kg COD/m3, i.e. 1 g/m3; the base case has about 196 g/m3
MAX_STEP = 0.25  # largest move per continuation step, as a fraction of each input's range
MIN_STEP = 1.0 / 32.0  # a step is abandoned after four halvings of MAX_STEP


def normalized_distance(a, b):
    return max(abs(a[v] - b[v]) / (RANGES[v][1] - RANGES[v][0]) for v in INPUTS)


class Plant:
    """One BSM2 model, solved once from scratch and then moved by continuation to new inputs."""

    def __init__(self, solver=None):
        self.solver = solver or get_solver()
        m = bsm2.build()
        bsm2.set_operating_conditions(m)
        bsm2.initialize_system(m)
        bsm2.add_costing(m)
        m.fs.costing.initialize()
        bsm2.scale_system(m)
        m.fs.objective.deactivate()
        self.m = m
        self.reactors = [m.fs.R1, m.fs.R2, m.fs.R3, m.fs.R4, m.fs.R5]
        self.current = dict(BASE)
        self._clone_solve()
        self.base_state = to_json(m, return_dict=True)
        self.set_floor(True)

    def _clone_solve(self):
        """The first solve from initialization needs the scaled clone (as in WaterTAP's main)."""
        scaling = pyo.TransformationFactory("core.scale_model")
        scaled = scaling.create_using(self.m, rename=False)
        if not check_optimal_termination(self.solver.solve(scaled)):
            raise RuntimeError("The BSM2 base case did not solve.")
        scaling.propagate_solution(scaled, self.m)

    def _solve(self):
        try:
            return check_optimal_termination(self.solver.solve(self.m))
        except Exception:
            return False

    def set_floor(self, on):
        for r in self.reactors:
            r.control_volume.properties_out[0].conc_mass_comp["X_BA"].setlb(AUTOTROPH_FLOOR if on else None)

    def autotrophs(self):
        """Autotroph concentration in R5, g/m3."""
        return value(self.m.fs.R5.control_volume.properties_out[0].conc_mass_comp["X_BA"]) * 1e3

    def restore_base(self):
        from_json(self.m, sd=self.base_state)  # also restores the variable bounds of the base state
        self.set_floor(True)
        self.current = dict(BASE)

    def _walk(self, target):
        """Adaptive continuation from self.current to target; True if the target was reached."""
        step = MAX_STEP
        while normalized_distance(self.current, target) > 1e-12:
            distance = normalized_distance(self.current, target)
            fraction = min(1.0, step / distance)
            point = {v: self.current[v] + fraction * (target[v] - self.current[v]) for v in INPUTS}
            snapshot = to_json(self.m, return_dict=True)
            self.set_inputs(point)
            if self._solve():
                self.current = point
                step = min(MAX_STEP, 2.0 * step)
            else:
                from_json(self.m, sd=snapshot)
                self.set_floor(True)
                self.set_inputs(self.current)
                step /= 2.0
                if step < MIN_STEP:
                    return False
        return True

    def set_inputs(self, x):
        fs = self.m.fs
        fs.R3.outlet.conc_mass_comp[0, "S_O"].fix(x["do3"] * 1e-3)
        fs.R4.outlet.conc_mass_comp[0, "S_O"].fix(x["do4"] * 1e-3)
        fs.R5.outlet.conc_mass_comp[0, "S_O"].fix(x["do5"] * 1e-3)
        fs.SP5.split_fraction[0, "underflow"].fix(x["recycle"])
        fs.SP6.split_fraction[0, "recycle"].fix(1.0 - x["wastage"])
        fs.FeedWater.flow_vol.fix(x["influent"] / 86400.0)

    def _walk_coordinates(self, target, order):
        """Continuation that moves one input at a time, in the given order."""
        for v in order:
            if not self._walk(dict(self.current, **{v: target[v]})):
                return False
        return True

    def evaluate(self, x):
        """Steady state at inputs x on the nitrifying branch.

        Tries a straight walk from the current point, then from the base case, then walks from the
        base case that move one input at a time (forward and reverse order): some points near the
        recycle bound are only reached along a different path.

        Returns (status, outputs): "ok" with the outputs; "washout" with the outputs of the
        no-nitrifier state when the nitrifying branch cannot be reached even from the base case;
        "failed" with None. The model is left at x after "ok", at the base case otherwise."""
        x = {v: float(x[v]) for v in INPUTS}
        if self._walk(x):
            return "ok", self.read_outputs()
        self.restore_base()
        if self._walk(x):
            return "ok", self.read_outputs()
        for order in (INPUTS, INPUTS[::-1]):
            self.restore_base()
            if self._walk_coordinates(x, order):
                return "ok", self.read_outputs()
        self.restore_base()
        self.set_floor(False)
        self.set_inputs(x)
        solved = self._solve()
        outputs = self.read_outputs() if solved and self.autotrophs() < AUTOTROPH_FLOOR * 1e3 else None
        self.restore_base()
        return ("washout", outputs) if outputs else ("failed", None)

    def read_outputs(self):
        fs = self.m.fs
        effluent = fs.CL1.effluent_state[0]
        return {
            "do3": value(fs.R3.outlet.conc_mass_comp[0, "S_O"]) * 1e3,
            "do4": value(fs.R4.outlet.conc_mass_comp[0, "S_O"]) * 1e3,
            "do5": value(fs.R5.outlet.conc_mass_comp[0, "S_O"]) * 1e3,
            "recycle": value(fs.SP5.split_fraction[0, "underflow"]),
            "wastage": 1.0 - value(fs.SP6.split_fraction[0, "recycle"]),
            "influent": value(fs.FeedWater.flow_vol[0]) * 86400.0,
            "lcow": value(fs.costing.LCOW),
            "sec": value(fs.costing.specific_energy_consumption),
            "tss": value(effluent.TSS) * 1e3,
            "cod": value(effluent.COD) * 1e3,
            "tn": value(effluent.Total_N) * 1e3,
            "bod5": value(effluent.BOD5["effluent"]) * 1e3,
            "nh4": value(effluent.conc_mass_comp["S_NH"]) * 1e3,
            "biogas": value(fs.RADM.vapor_outlet.flow_vol[0]) * 86400.0,
        }

    def optimize(self, influent, objective="lcow", start=None, limits=None):
        """WaterTAP's own optimum (IPOPT on the flowsheet) over the five operating decisions within
        RANGES, at a fixed influent, subject to the effluent limits. objective is "lcow" or "sec"
        (minimized) or "biogas" (maximized). Starts from `start` (decisions; default BASE).
        Returns the outputs or None. The model is back at the base case afterwards."""
        limits = LIMITS if limits is None else limits
        x0 = dict(start or BASE, influent=influent)
        if self.evaluate(x0)[0] != "ok":
            return None
        fs = self.m.fs
        decisions = {
            "do3": (fs.R3.outlet.conc_mass_comp[0, "S_O"], 1e-3),
            "do4": (fs.R4.outlet.conc_mass_comp[0, "S_O"], 1e-3),
            "do5": (fs.R5.outlet.conc_mass_comp[0, "S_O"], 1e-3),
            "recycle": (fs.SP5.split_fraction[0, "underflow"], 1.0),
        }
        for name, (var, factor) in decisions.items():
            var.unfix()
            var.setlb(RANGES[name][0] * factor)
            var.setub(RANGES[name][1] * factor)
        recycle_split = fs.SP6.split_fraction[0, "recycle"]
        recycle_split.unfix()
        recycle_split.setlb(1.0 - RANGES["wastage"][1])
        recycle_split.setub(1.0 - RANGES["wastage"][0])

        effluent = fs.CL1.effluent_state[0]
        fs.opt = pyo.Block()
        fs.opt.tss = pyo.Constraint(expr=effluent.TSS <= limits["tss"] * 1e-3)
        fs.opt.cod = pyo.Constraint(expr=effluent.COD <= limits["cod"] * 1e-3)
        fs.opt.tn = pyo.Constraint(expr=effluent.Total_N <= limits["tn"] * 1e-3)
        fs.opt.bod5 = pyo.Constraint(expr=effluent.BOD5["effluent"] <= limits["bod5"] * 1e-3)
        fs.opt.nh4 = pyo.Constraint(expr=effluent.conc_mass_comp["S_NH"] <= limits["nh4"] * 1e-3)
        if objective == "lcow":
            fs.opt.objective = pyo.Objective(expr=fs.costing.LCOW)
        elif objective == "sec":
            fs.opt.objective = pyo.Objective(expr=fs.costing.specific_energy_consumption)
        elif objective == "biogas":
            fs.opt.objective = pyo.Objective(expr=fs.RADM.vapor_outlet.flow_vol[0] * 86400.0,
                                             sense=pyo.maximize)
        else:
            raise ValueError(objective)
        scaler = CustomScalerBase()
        for c in fs.opt.component_data_objects(pyo.Constraint):
            scaler.scale_constraint_by_nominal_value(c, scheme=ConstraintScalingScheme.inverseMaximum,
                                                     overwrite=True)

        result = self.read_outputs() if self._solve() else None

        fs.del_component(fs.opt)
        self.restore_base()
        return result


def lhs(n, dimensions, rng):
    """Latin hypercube sample in [0, 1]^dimensions."""
    columns = []
    for _ in range(dimensions):
        strata = rng.permutation(n)
        columns.append((strata + rng.random(n)) / n)
    return list(zip(*columns))


def timed(function, *args, **kwargs):
    start = time.time()
    result = function(*args, **kwargs)
    return result, time.time() - start
