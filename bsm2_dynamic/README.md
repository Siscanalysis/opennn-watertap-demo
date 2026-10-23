# Dynamic BSM2 with OpenNN: plan

`../bsm2_steady` uses WaterTAP's steady-state BSM2. That is the BSM2 plant layout solved at one operating point, with simplified clarifiers and WaterTAP costing.

The IWA benchmark itself is dynamic:

- a 609-day influent at 15-minute resolution, with rain, storms and seasons;
- scored over days 245 to 609 with the effluent quality index (EQI), the operational cost index (OCI) and the time spent above the effluent limits.

This folder organizes that dynamic version and lists what OpenNN can do with it.

## Simulator

[bsm2-python](https://bsm2-python.readthedocs.io/user_guide/) 0.0.16 is installed in its own conda environment, `miniforge3\envs\bsm2` (Python 3.12). It is kept separate from `watertap`, whose numpy and pyomo pins differ. The ingredients:

| Ingredient | Where |
|---|---|
| Open-loop plant: 5 ASM1 reactors, 1-D settler, primary clarifier, thickener, ADM1 digester, dewatering, storage | `BSM2OL`; `step(i, klas)` takes the KLa of the 5 reactors at each step |
| Closed-loop plant: PI control of DO in R4, with KLa3 and KLa5 proportional to KLa4 | `BSM2CL`; `step(i, so4ref)` takes the DO set-point |
| Internal recycle | `plant.qintr` (m³/d), changeable between steps |
| Waste sludge flow | constructor argument of the settler (`asm1init.QW`); changing it during a run means setting the settler's attribute (not tried yet) |
| Scores | `get_final_performance()`: IQI, EQI, sludge production, CH₄, aeration, pumping and mixing energy, heat demand, OCI. `get_violations()`: days above a limit |
| Full trajectories | `y_eff_all`, `y_out1_all` … `y_out5_all`, `iqi_all`, `eqi_all`, `oci_all` (one row per time step) |
| Influent | `data/dyninfluent_bsm2.csv`: 58,465 rows (609 days × 96 per day): flow, ASM1 components, temperature |

`dynamic_policy.py` runs the open-loop plant under a constant policy (KLa of R3–R5 and internal recycle) and returns those scores. It is the building block for track D1.

Measured on this laptop (i7-8550U), while the steady-state dataset used the other cores:

| Run | Speed | A full 609-day run |
|---|---|---|
| Open loop, 15-minute steps | 3.4 s per simulated day (after a one-off numba compilation of about 1–2 min) | about 35 min |
| Closed loop, 1-minute steps | 105 s per simulated day | about 18 h |

A test over 3 days, scoring the last 2, shows what lower aeration does:

| KLa R3/R4/R5 (1/d) | EQI | OCI | Aeration energy (kWh/d) | NH₄ > 4 mg/L |
|---|---:|---:|---:|---:|
| 120 / 120 / 60 (default) | 4483 | 10404 | 4000 | 0 d |
| 80 / 80 / 40 | 11938 | 9446 | 2667 | 0.13 d |

A 3-day window is far too short for the benchmark scores. It only shows that the trade-off is there to optimize.

## What OpenNN can do with it

The tracks are ordered from cheapest to most ambitious.

One OpenNN constraint shapes tracks D1 and D2. `ResponseOptimization` takes its search box from a flat `Scaling` layer at the network input (`get_unconstrained_domain`). So the networks it optimizes must be ordinary tabular ones. A recurrent or forecasting network can predict, but it cannot be optimized directly. Anything time-dependent therefore enters as explicit lagged or summary columns.

### D3: influent forecasting (no simulation needed)

Forecast the next 24 h of influent flow and NH₄ or COD load from the past days. This is the input any predictive controller needs.

- **Data:** the 609-day influent file, which is already on disk.
- **OpenNN:** `TabularDataset` with `configure_forecasting(past, future)`, comparing an LSTM against a dense network on lagged columns. Use a chronological split (train on days 0–400, test on 400–609).
- **Baselines:** persistence (same time yesterday) and a daily-profile mean.
- **Cost:** minutes. This is a good first dynamic toy.

### D1: policy surrogate and response optimization (the dynamic analogue of the steady-state toy)

Each sample is one dynamic run under a constant policy, and each row of the dataset is that run's scores.

- **Inputs:** KLa of R3, R4 and R5 (or one DO set-point for the closed loop), internal recycle and waste flow.
- **Outputs:** EQI, OCI, aeration and pumping energy, sludge production, CH₄, and days above the NH₄ and total-N limits.
- **OpenNN:** an `ApproximationNetwork`, then `ResponseOptimization`. Two examples: minimum OCI with fewer than x days of NH₄ violation, and the EQI vs OCI Pareto front.
- **Check:** every answer is re-simulated with `dynamic_policy.py`, and the validation-error margins carry over from the steady-state toys.
- **Cost:** about 35 min per sample at the full protocol. A screening protocol (for example 120 days, scoring the last 60) cuts that to about 7 min. With 4 parallel runs:

| Plan | Samples | Time |
|---|---|---|
| Screening protocol | ~150 | ~4–5 h |
| Full protocol | ~60 | ~9 h |

  Either fits an unattended overnight run. Confirm the final answers with the full 609-day protocol.

### D2: dynamic surrogate for predictive control (closest to real-time operation with feedback)

**Data.** One long open-loop run whose controls are deliberately varied: piecewise-constant KLa and internal recycle, changed every few hours at random within limits. That gives one row per 15 minutes over 609 days (about 58,000 rows) for about 35 min of simulation.

**Model.** A tabular next-horizon model. One row is the plant at time t:

- recent effluent NH₄, NO₃ and DO, plus influent flow and load over the past hours, all as lagged columns;
- the controls planned for the next H hours (for example 2 h);
- the influent forecast from D3.

The targets are the average NH₄, total N and aeration energy over those H hours.

**Control.** At each decision time, `ResponseOptimization` chooses the controls with minimum energy subject to predicted NH₄ ≤ 4 minus a margin. The current state is fixed with `Equal` constraints, as influent flow is fixed in the steady-state toy. The plant then runs H hours and the loop repeats.

**Score.** Run the full 364-day evaluation with that loop and compare EQI, OCI and violations against the default closed-loop PI control. The PI baseline needs one closed-loop run of about 18 h; that run can also be shortened.

**Engineering.** The C++ optimizer must answer one request per decision, which comes to about 35,000 requests over 364 days at H = 15 min, or about 4,400 at H = 2 h. That needs a persistent `ro_surrogate`-style process reading requests on stdin, rather than one process per call. Alternatively, OpenNN's Python export of the network could be optimized in Python, but that would no longer test OpenNN's optimizer.

### Also possible

- **Soft sensor:** effluent NH₄ or total N from cheap online signals (flow, DO, temperature), using an OpenNN approximation network on the D2 trajectories.
- **Anomaly detection:** an OpenNN autoencoder on the trajectories, with sensor faults injected. bsm2-python already adds sensor noise; the faults would have to be added.
- **Steady-state to dynamic check:** run the set-points found in `../bsm2_steady` as constant policies in the dynamic plant and score them. The two models differ (WaterTAP fixes 35 °C, uses simplified clarifiers and has its own defaults), so this tests only the direction of the change, for example "lower DO", not the numbers.

## Recommended order

1. **D3**, to learn OpenNN forecasting on this influent at almost no cost.
2. **D1 with the screening protocol**, as an overnight run, then confirm its optima with the full protocol.
3. **D2**, once D1 has shown which controls matter.
