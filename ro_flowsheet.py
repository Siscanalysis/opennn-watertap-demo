"""WaterTAP reverse osmosis flowsheet with a pressure exchanger, used as the ground truth.

The flowsheet is WaterTAP's own RO_with_energy_recovery (0D RO, NaCl property package,
pressure exchanger plus booster pump, WaterTAPCosting). Feed flow is fixed at 1e-3 m3/s.

Variables, with the units used in the dataset:
    salinity      feed NaCl mass fraction, g/kg
    recovery      RO water mass recovery, -
    pressure      high-pressure pump outlet (RO feed) pressure, bar
    lcow          levelized cost of water, $/m3 of permeate
    sec           specific energy consumption, kWh/m3 of permeate
    permeate_ppm  permeate NaCl mass fraction, mg/kg
    flux_out      water flux at the RO outlet, kg/m2/h (WaterTAP's minimum-flux constraint)
    flux_avg      average water flux, kg/m2/h
    area          membrane area, m2
"""

import logging
import math

from pyomo.environ import Constraint, Objective, check_optimal_termination, maximize, value

import idaes.logger as idaeslog
from watertap.core.solvers import get_solver
from watertap.flowsheets.RO_with_energy_recovery import RO_with_energy_recovery as ro

INPUTS = ["salinity", "recovery", "pressure"]
OUTPUTS = ["lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"]

# Dataset ranges. Pressures are sampled between OSMOTIC_MARGIN times the brine osmotic pressure
# (WaterTAP's estimate with 1 % salt passage) and PRESSURE_MAX. At 0.88 times that pressure the
# outlet flux is still positive (about 0.3 kg/m2/h), so the data straddle the 1 kg/m2/h limit
# that is active at WaterTAP's own optimum.
SALINITY_RANGE = (25.0, 45.0)
RECOVERY_RANGE = (0.35, 0.60)
PRESSURE_MAX = 85.0
OSMOTIC_MARGIN = 0.88


def quiet():
    logging.getLogger("idaes").setLevel(logging.ERROR)
    logging.getLogger("pyomo").setLevel(logging.ERROR)
    logging.getLogger("watertap").setLevel(logging.ERROR)
    idaeslog.getLogger("idaes").setLevel(logging.ERROR)
    idaeslog.getInitLogger("idaes").setLevel(logging.ERROR)


def _build(salinity, recovery, over_pressure_factor, solver):
    m = ro.build(erd_type=ro.ERDtype.pressure_exchanger)
    ro.set_operating_conditions(m, water_recovery=recovery, over_pressure_factor=over_pressure_factor,
                                salt_mass_conc=salinity * 1e-3, solver=solver)
    return m


def _set_pressure(m, pressure_bar):
    pressure = pressure_bar * 1e5
    m.fs.P1.control_volume.properties_out[0].pressure.fix(pressure)
    m.fs.RO.feed_side.properties_in[0].pressure = pressure


def read_outputs(m):
    area = value(m.fs.RO.area)
    permeate_water = value(m.fs.product.properties[0].flow_mass_phase_comp["Liq", "H2O"])
    return {
        "salinity": value(m.fs.feed.properties[0].mass_frac_phase_comp["Liq", "NaCl"]) * 1e3,
        "recovery": value(m.fs.RO.recovery_mass_phase_comp[0, "Liq", "H2O"]),
        "pressure": value(m.fs.P1.control_volume.properties_out[0].pressure) / 1e5,
        "lcow": value(m.fs.costing.LCOW),
        "sec": value(m.fs.costing.specific_energy_consumption),
        "permeate_ppm": value(m.fs.product.properties[0].mass_frac_phase_comp["Liq", "NaCl"]) * 1e6,
        "flux_out": value(m.fs.RO.flux_mass_phase_comp[0, 1, "Liq", "H2O"]) * 3600.0,
        "flux_avg": permeate_water / area * 3600.0,
        "area": area,
    }


def brine_osmotic_pressure(salinity, recovery, solver=None):
    """Osmotic pressure (bar) of the brine at this recovery, with 1 % salt passage (WaterTAP's estimate)."""
    solver = solver or get_solver()
    m = _build(salinity, recovery, 1.0, solver)
    return value(m.fs.P1.control_volume.properties_out[0].pressure) / 1e5


def evaluate(salinity, recovery, pressure, solver=None):
    """Solves the flowsheet with salinity, recovery and pressure fixed (membrane area free).

    Returns the dictionary of read_outputs, or None when initialization or the solve fails,
    which is what happens below the brine osmotic pressure.
    """
    solver = solver or get_solver()
    try:
        m = _build(salinity, recovery, 1.3, solver)
        _set_pressure(m, pressure)
        ro.initialize_system(m, solver=solver)
        results = solver.solve(m)
    except Exception:
        return None
    if not check_optimal_termination(results):
        return None
    return read_outputs(m)


def sample(salinity, recovery, position, solver=None):
    """Solves one dataset point: the pressure sits at `position` (0 to 1) between
    OSMOTIC_MARGIN times the brine osmotic pressure and PRESSURE_MAX.

    Returns (status, row): status is "ok", "out_of_range" (no pressure range below PRESSURE_MAX)
    or "failed"; row holds the inputs and, when solved, the outputs.
    """
    solver = solver or get_solver()
    row = {"salinity": salinity, "recovery": recovery, "pressure": float("nan")}
    try:
        m = _build(salinity, recovery, 1.0, solver)
        osmotic = value(m.fs.P1.control_volume.properties_out[0].pressure) / 1e5
        lower = OSMOTIC_MARGIN * osmotic
        if lower >= PRESSURE_MAX:
            return "out_of_range", row
        row["pressure"] = lower + position * (PRESSURE_MAX - lower)
        _set_pressure(m, row["pressure"])
        ro.initialize_system(m, solver=solver)
        results = solver.solve(m)
    except Exception:
        return "failed", row
    if not check_optimal_termination(results):
        return "failed", row
    return "ok", read_outputs(m)


def optimize(salinity, objective="lcow", recovery=None, pressure_max=80.0, flux_out_min=1.0,
             flux_avg_min=None, permeate_max=500.0, lcow_max=None, recovery_range=RECOVERY_RANGE,
             start_recovery=0.5, solver=None):
    """WaterTAP's own optimum (IPOPT) for one of the response optimization scenarios.

    objective is "lcow" or "sec" (minimized) or "max_recovery". recovery=None leaves the
    recovery free within recovery_range; a number fixes it. Starts from WaterTAP's
    optimize_set_up (minimum LCOW, 10-80 bar pumps, area 1-1500 m2, permeate <= 500 ppm,
    outlet flux >= 1 kg/m2/h) and changes only what the scenario changes.
    """
    solver = solver or get_solver()
    start = recovery if recovery is not None else start_recovery
    m = _build(salinity, start, 1.3, solver)
    ro.initialize_system(m, solver=solver)
    if not check_optimal_termination(solver.solve(m)):
        return None

    ro.optimize_set_up(m)
    m.fs.product_salinity.set_value(permeate_max * 1e-6)
    m.fs.minimum_water_flux.set_value(flux_out_min / 3600.0)
    for pump in (m.fs.P1, m.fs.P2):
        pump.control_volume.properties_out[0].pressure.setub(pressure_max * 1e5)

    water_recovery = m.fs.RO.recovery_mass_phase_comp[0, "Liq", "H2O"]
    if recovery is None:
        water_recovery.unfix()
        water_recovery.setlb(recovery_range[0])
        water_recovery.setub(recovery_range[1])

    if flux_avg_min is not None:
        m.fs.eq_average_flux = Constraint(
            expr=m.fs.product.properties[0].flow_mass_phase_comp["Liq", "H2O"]
            >= flux_avg_min / 3600.0 * m.fs.RO.area)

    if lcow_max is not None:
        m.fs.eq_lcow_budget = Constraint(expr=m.fs.costing.LCOW <= lcow_max)

    if objective != "lcow":
        m.fs.objective.deactivate()
        if objective == "sec":
            m.fs.objective_sec = Objective(expr=m.fs.costing.specific_energy_consumption)
        elif objective == "max_recovery":
            m.fs.objective_recovery = Objective(expr=water_recovery, sense=maximize)
        else:
            raise ValueError(objective)

    try:
        results = solver.solve(m)
    except Exception:
        return None
    if not check_optimal_termination(results):
        return None
    return read_outputs(m)


def lhs(n, dimensions, rng):
    """Latin hypercube sample in [0, 1]^dimensions."""
    columns = []
    for _ in range(dimensions):
        strata = rng.permutation(n)
        columns.append((strata + rng.random(n)) / n)
    return list(zip(*columns))


def is_finite(row):
    return all(math.isfinite(row[k]) for k in OUTPUTS)
