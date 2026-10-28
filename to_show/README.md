# Water Treatment HMI

`water_treatment_hmi.html` is a control-room screen for two plants: a wastewater treatment plant (BSM2 layout) and a seawater desalination plant (reverse osmosis). An OpenNN neural network predicts each plant from its set-points and OpenNN optimizes them. The WaterTAP simulator can run beside the network, so the page shows four things together:

- what the simulator says;
- what the network predicts;
- what the optimizer suggests;
- what the optimization achieves in the simulator.

## Opening it

- **Network only.** Double-click `water_treatment_hmi.html`. It is a single file that runs in any modern browser, offline, with nothing installed. It carries WaterTAP's solutions for the default operations, the optima and the guided demo's paths. Every other point shows the network alone.
- **Network and simulator.** Run `..\setup.bat` once on the computer (`../setup.sh` on Linux or macOS). Then either press **Start WaterTAP** in the page, or double-click `..\start_demo.bat` (the same as `start_simulator.bat` here), which also opens the page from the service (`http://127.0.0.1:8765/`). From then on, every operating point that holds still for half a second, and every OpenNN proposal, is also solved in WaterTAP. The desalination models are ready in seconds and the wastewater models in about a minute. A solve takes about 5 to 15 s (desalination) or 5 to 25 s (wastewater). The simulator runs in its own window, minimized when the button started it; closing that window stops it.

  The service uses the Python environment that setup created; `simulator/python_path.txt` records its `python.exe`. To use another one, set `PYTHON` before running `start_simulator.bat`. Started a second time, the service only opens the page.

### The Start WaterTAP button

A web page cannot start a program on its own. The button opens an `opennn-watertap:` link, and `setup.bat` registers that link type for the current Windows user (`HKCU\Software\Classes\opennn-watertap`): it runs `start_simulator.bat --from-page` from the folder where setup ran. The browser asks once ("Open OpenNN WaterTAP simulator?"); Chrome and Edge can remember the answer. The page then waits for the service and turns live by itself.

- Without the setup, the button does nothing, and after 15 s the page says what to run, with this folder's path when it is opened as a file.
- The link takes no arguments, so any web page can at most start this simulator, and only after that prompt.
- `setup.bat --uninstall` removes the registration. Moving the folder needs `setup.bat` again.
- On Linux and macOS the page shows the commands instead of the button.

### Sharing it

- **The HTML file alone** can be emailed or put on any web page. It needs nothing else, but without the service it shows only the stored WaterTAP solutions above. With GitHub Pages turned on for this repository (Settings → Pages → `main`, root folder), the page is at `https://siscanalysis.github.io/opennn-watertap-demo/to_show/water_treatment_hmi.html`. Wherever the page is opened from, it looks for the service on the viewer's own computer, so a viewer who has run the setup gets the live simulator there too.
- **The live simulator** cannot travel in one file. WaterTAP needs Python, Pyomo/IDAES and the IPOPT solver, about 800 MB, and browsers cannot run IPOPT. To run it elsewhere, clone or download the repository (the service imports `..\ro_flowsheet.py` and `..\bsm2_steady\bsm2_flowsheet.py`) and run `setup.bat`. Alternatively, run the service once on a server and point the page at it.

The `WATERTAP` chip in the top bar says whether the simulator is offline, starting, live or solving.

## What is on the screen

| Area | What it shows |
|---|---|
| Process diagram | The plant with live tags: flows, dissolved-oxygen set-points, energy, biogas, and the effluent or permeate analyzers. Tags turn amber near a limit and red past it. The `OpenNN / WaterTAP` switch chooses whose values the tags show; while WaterTAP solves a new point, its values for the previous one are dimmed. |
| Operation panel | The plant condition (influent flow or feed salinity) and the operator set-points. `New default operation` loads a random feasible operation. `Optimize with OpenNN` shows the optimizer's proposal; `Apply set-points` ramps the plant to it. `AUTO` keeps the set-points on the optimum while the condition changes. |
| Constraints to respect | The limits the optimizer keeps, one row each: switch a limit off, or type another value (for example NH₄ ≤ 2 mg/L instead of the permit's 4). Alarms, limit bars, trends and the WaterTAP checks follow the limits in force. `Reset to permit` restores the permit. See [Your own limits](#your-own-limits). |
| KPI tiles | Energy, cost of water and biogas (or membrane area) predicted by OpenNN, compared with the default operation, with savings per year at the current flow. Below, WaterTAP's value for the same point and the network's difference from it. |
| Optimizer card | First the proposal: the set-points now and proposed, the outputs OpenNN predicts, and WaterTAP's solution at the proposed set-points with its limit check. After `Apply set-points`, the result: the plant before and after, both solved in WaterTAP, next to the change OpenNN predicted. |
| Limits | Each effluent or product limit as a bar, with OpenNN's value (▲ below the bar) and WaterTAP's (▼ above it, orange). The shaded band is the safety margin the optimizer keeps. |
| OpenNN and WaterTAP | Both at the current operating point, their difference, and how long each takes: about 10 to 20 µs per network prediction in the browser against seconds per WaterTAP solve, roughly a million times longer. |
| Trends | The last 12 plant hours: the network's prediction as a line and WaterTAP's solutions as orange dots. A solution that arrives after the plant has moved on is drawn where the plant was. In AUTO, a dotted violet line marks where the optimizer keeps an output: its limit less the safety margin (NH₄ ≤ 3.56 mg/L with the permit, 3.19 mg/L in a storm). The line steps where the network in use changes. |
| Event log | Alarms, operator actions, optimizer steps and simulator results. |

The tabs switch between the two plants. `Theme` cycles between system, dark and light.

### Why NH₄ stays flat in AUTO

Removing more ammonium takes more aeration or an older sludge, and both cost energy, money or biogas. So each optimum uses all the room the NH₄ limit allows: that limit is what stops the optimizer. AUTO therefore holds NH₄ on the dotted line (the 4 mg/L limit less the 0.44 mg/L safety margin) while the set-points and the energy follow the influent; a note under the trends says so. WaterTAP's dots scatter around the line, below the limit: that scatter is what the margin is for. In a storm the line drops to 3.19 mg/L, because the storm network's error near the limit is larger (a 0.81 mg/L margin).

With the set-points held (manual), NH₄ moves a lot along the daily pattern: from 1.1 to 5.5 mg/L for one stored default, in WaterTAP. The influent load and the sludge wastage move it most. One tank's dissolved oxygen moves it less, because the other two aerated tanks take up the work.

## Presenting it

`Play guided demo` runs the story in about a minute:

1. A random default operation that meets every limit.
2. OpenNN proposes optimal set-points (minimum energy for the wastewater plant, minimum cost for the desalination plant), and WaterTAP checks them.
3. The set-points are applied. The card shows the saving measured in WaterTAP next to the one OpenNN predicted, and every limit still holds.
4. The influent follows a daily pattern (or the salinity swings) with the set-points held fixed. At high load the plant drifts toward its limits, and at low load it wastes energy.
5. AUTO: OpenNN re-optimizes as the condition changes, and the WaterTAP dots follow the network's line. NH₄ now stays on the AUTO line while the energy follows the load.

Opening the file with `#bsm2-demo` or `#ro-demo` at the end of the address starts the demo directly. `#ro` opens the desalination plant.

With the simulator running, move a set-point slider and let go: the network answers at once, and WaterTAP a few seconds later. During the daily pattern the plant moves faster than WaterTAP can solve, so the dots thin out. That is the case for the network.

## Your own limits

With the permit limits, the proposals are the optima OpenNN response optimization computed beforehand, which WaterTAP checked. With limits you set, the page solves the same problem itself, in the browser, on the OpenNN network:

- the same objective, over the same set-points, within the range the network was trained on;
- every limit in force kept with a safety margin. The margin follows OpenNN's rule for each bound you set: the 95th percentile of the network's validation error among samples within a factor of two of that bound. The page carries those validation errors.

The search is differential evolution followed by a local pattern search (`src/optimizer.js`). It runs in a background thread and takes about 30 to 300 ms per condition. With the permit limits it reaches OpenNN's stored optima at every condition (`tools/check_optimizer.mjs`). The proposal says which of the two produced it ("your limits"). With the simulator running, WaterTAP checks it like any other proposal. If no set-points meet every limit, the card says which limits the closest point still misses.

AUTO works with your limits as well: it re-optimizes for each new condition. Where nothing meets the limits, it holds the set-points and logs it.

## Storm (wet weather)

The wastewater plant's condition panel has a weather switch under the daily pattern: `Dry weather` or `Storm`. In a storm, rainwater enters with the sewage. The rain inflow rises to 4,500 m³/d over about an hour of plant time, and after `Dry weather` it falls back to none over about two hours. The influent meter in the diagram reads sewage and rain together, a tag below it shows the rain, and the influent trend hatches the rain's share. The daily pattern carries on underneath.

**How it is modelled.** Rain adds to the flow and dilutes every influent concentration by influent / (influent + rain): the load stays the same, but the water is more dilute and passes through faster. The page carries a second wastewater network for it, the storm network, with a seventh input, `rain` (0 to 6,000 m³/d). The page uses it while it rains, and the dry-weather network otherwise, because that one is more accurate without rain. The storm network was trained on three sets of rows:
- the dry-weather network's 1,922 rows;
- 811 WaterTAP simulations with rain (`tools/storm_simulations.py`);
- 331 optima of its first version, solved in WaterTAP.

OpenNN computed its optima at 1,500, 3,000 and 4,500 m³/d of rain, and WaterTAP checked them. The page snaps the rain to those levels, so the network changes when the rain reaches the first level and again when it is back to none.

**What to expect.** With the set-points held, NH₄ rises with the rain. Sludge wastage is a share of the clarifier underflow, so the extra flow wastes more sludge; the sludge age falls and the nitrifiers fall behind. For one set of held set-points at 20,500 m³/d of sewage (dissolved oxygen 1.31, 1.77 and 1.33 mg/L, wastage 1.98%), WaterTAP gives 2.2 mg/L of NH₄ in dry weather and 6.9 mg/L at the storm's peak, over the 4 mg/L limit. COD and suspended solids fall with the dilution, and energy per m³ falls because there are more m³ for the same work.

AUTO keeps NH₄ under the limit by cutting the sludge wastage, which keeps the sludge age. For minimum energy at the same sewage flow, the optima are:

| Rain, m³/d | Sludge wastage | Dissolved oxygen, tanks 3 to 5 | NH₄ in WaterTAP | Energy in WaterTAP |
|---|---|---|---|---|
| none (dry-weather network) | 1.75% | 0.59, 1.02, 1.02 mg/L | 3.44 mg/L | 0.286 kWh/m³ |
| 1,500 | 1.17% | 0.51, 0.50, 0.50 mg/L | 3.40 mg/L | 0.263 kWh/m³ |
| 4,500 | 1.01% | 0.50 mg/L each (the minimum) | 3.26 mg/L | 0.236 kWh/m³ |

**How well it does** (`tools/compare_rain.py`, `models/bsm2_rain/summary.txt`):
- **Wet weather.** On 143 wet-weather simulations it never saw, the storm network's mean NH₄ error is 0.25 mg/L where NH₄ is 2 to 8 mg/L. The dry-weather network, which ignores the rain, is off by 1.92 mg/L on the same points.
- **Washout.** Above 8 mg/L, mostly washouts, the errors are 3.8 and 16.3 mg/L. 87 of the 954 wet simulations that solved washed out, with NH₄ at 31 to 36 mg/L, mostly above 3,000 m³/d of rain with high wastage. They stay in the training data; unlike the dry data, none was re-solved to look for a nitrifying solution.
- **Dry weather.** On the 119 dry held-out simulations, the storm network is the less accurate of the two: 0.25 against 0.18 mg/L where NH₄ is 2 to 8 mg/L. That is why the page keeps the dry-weather network when there is no rain.
- **Its optima.** In the first round, 36 of the 331 optima that WaterTAP solved missed the NH₄ limit, by a median 0.23 mg/L; one of them washed out. `run_storm.py` added those 331 checked points to the training data and retrained. Of the second round's 252 optima at 1,500 to 4,500 m³/d, WaterTAP solved 246 and all of them meet every limit (highest NH₄ 3.67 mg/L); it did not converge at the other 6. The storm network's margin near the NH₄ limit is wider (0.81 against 0.44 mg/L).
- **Without rain.** Its optima would use a median 1.1% more energy than the dry-weather network's.

**Read with care.** The model is steady state, so a storm shows the plant settled into wet weather, as after days of rain, and not the first hours of a storm. WaterTAP's steady BSM2 has no first flush, no clarifier overload (its clarifiers split at fixed fractions) and no temperature effect, so these are missing too. A storm as an event belongs to the dynamic benchmark (`../bsm2_dynamic`).

## Where the numbers come from

- **Models.** Each plant is a WaterTAP flowsheet solved at steady state (`../bsm2_steady` and the RO toy in `..`).
- **Networks.** The networks on the page were retrained in OpenNN for it, on the original simulations plus new ones (`models/<plant>/`; the toy folders keep the original networks):
  - desalination: 1,560 simulations, 596 more than the original 964 (same architecture, 32 hidden neurons);
  - wastewater: 1,922 simulations, 952 more than the original 970, with two hidden layers of 32 neurons instead of one. Half of the 800 new simulations went where the original network put the effluent near a limit; the rest of the new rows are WaterTAP solutions of the dashboard's defaults and optima;
  - wastewater in a storm (`models/bsm2_rain`, used while it rains): 3,064 rows, the 1,922 above, 811 wet-weather simulations and 331 optima of its first version, with rain as a seventh input and two hidden layers of 32 neurons. See [Storm](#storm-wet-weather) for how it compares.

  A seeded 15% of the new simulations was kept out of training, so both networks can be compared on simulations neither saw (`tools/compare_networks.py`):

  | Plant | Output | Original network | Retrained |
  |---|---|---|---|
  | Desalination (87 held out) | cost of water, mean error | 0.00109 $/m³ | 0.00090 $/m³ |
  | | energy, mean error | 0.0040 kWh/m³ | 0.0032 kWh/m³ |
  | Wastewater (119 held out) | NH₄, mean error | 0.45 mg/L | 0.29 mg/L |
  | | NH₄ where it is 2 to 8 mg/L (21) | 0.43 mg/L | 0.18 mg/L |
  | | NH₄ above 8 mg/L (8) | 5.3 mg/L | 3.6 mg/L |
  | | total nitrogen, mean error | 0.77 mg/L | 0.31 mg/L |
  | | energy, mean error | 0.0023 kWh/m³ | 0.0011 kWh/m³ |

  **Why two layers for the wastewater plant.** NH₄ climbs steeply as the nitrifiers approach washout, and the error of the original network grew with it: on the 794 new simulations it averaged 0.65 mg/L between 4 and 8 mg/L and 2.0 mg/L between 8 and 15. More data alone made a one-layer network worse on NH₄ (0.62 mg/L held out). Two hidden layers follow the steep part, and the network is chosen by its validation error of log NH₄ between 1 and 20 mg/L. Along 12 daily-pattern paths solved in WaterTAP (a default held while the influent sweeps its range, `tools/scenarios.py`), the NH₄ error between 4 and 8 mg/L falls from 0.70 to 0.19 mg/L, and between 8 and 15 mg/L from 1.46 to 0.59 mg/L. The points where the network puts NH₄ on the wrong side of the 4 mg/L limit fall from 9 to 2 of 336 (`models/bsm2/scenarios_nh4.png`, copied to `screenshots/wastewater_nh4_paths.png`). Sudden washout jumps (to about 40 mg/L in one influent step) remain beyond a smooth network. The page warns when NH₄ is above 8 mg/L.

  **Washout rows.** Steady-state ASM1 also has a no-nitrifier solution. `tools/resolve_washout.py` solved the 30 training rows with NH₄ about 40 mg/L again, from nearby rows where the nitrifiers live. One was a solver artefact (it solves at 3.6 mg/L, next to a neighbour at 3.75) and was corrected. The other 29 are real washout or near washout.
- **In the browser.** The page holds the trained weights (`weights/*.json`, 22 and 5 KB) and computes the network in JavaScript (`src/model.js`). On 2,000 random points per plant this reproduces OpenNN's own predictions to within 1e-5 of each output's spread (`tools/check_forward.py`).
- **Optima.** OpenNN response optimization computed the optimal set-points beforehand with the retrained networks, for 28 influent flows (16,600 to 24,700 m³/d) and 19 feed salinities (26 to 44 g/kg). It kept every limit with a safety margin equal to the network's validation error.
- **Verification.** The stored points were solved in WaterTAP (`tools/verify_points.py`):
  - all 120 default operations (60 per plant) meet every limit;
  - 83 of the 84 wastewater optima and all 19 desalination optima meet every limit;
  - WaterTAP did not converge at the remaining wastewater optimum (minimum energy at 21,700 m³/d), and the page says so when it is proposed;
  - of the storm network's 252 optima (1,500 to 4,500 m³/d of rain), WaterTAP solved 246, and all of them meet every limit.
  - Against the original network's optima, both solved in WaterTAP (`data/original_network/`, `tools/compare_optima.py`):
    - the wastewater minimum-energy optima use a median 2.4% less energy (0.9 to 7.9%) at every solved condition;
    - minimum cost is 0.2% lower at every condition, and maximum biogas is equal within 0.1%;
    - the desalination optima cost a median 0.16% more. The retrained network's validation error near the brine-end flux limit is larger, so its margin is wider (0.90 instead of 0.63 kg/m²·h).
  - One infill round was needed. With the first two-layer network, 8 of the 28 maximum-biogas optima at high influent (all DO at 3 mg/L, sludge wastage near its maximum) exceeded the NH₄ limit in WaterTAP by 0.04 to 0.22 mg/L. Adding every WaterTAP-solved optimum to the training data and optimizing again cleared all of them.
- **What is simulated.** Without the simulator, a point other than a stored one (a slider moved by hand, a set-point ramp) is a network prediction only, and the page says so. With it, each point that holds still is solved too.
- **Steady state.** The models describe the plant once it has settled. A ramp or a daily pattern is drawn as a sequence of steady states, not as process dynamics.

`screenshots/` holds stills for slides:
- `wastewater_proposal.png`: a proposal checked in WaterTAP;
- `wastewater_result.png`: the result, with WaterTAP's saving next to OpenNN's prediction;
- `wastewater_your_limits.png`: NH₄ limited to 2 mg/L;
- `wastewater_auto.png`: AUTO after the daily peak;
- `wastewater_storm.png`: AUTO in a storm at 4,500 m³/d of rain, with the simulator running: the rain hatched in the influent trend, and the AUTO line stepping down to the storm network's;
- `desalination_light.png`: the light theme;
- `wastewater_nh4_paths.png`: original and retrained network against WaterTAP along the daily-pattern paths.

## The simulator service

`simulator/server.py` keeps a pool of WaterTAP worker processes per plant, each with its own model warm, and answers on `127.0.0.1` only. There are 3 wastewater and 2 desalination workers by default; change them with `--workers-bsm2=N` and `--workers-ro=N`.

- `GET /status` reports, per plant, whether the models are ready, how many solves are running and waiting, and the equation count.
- `POST /simulate` with `{"plant", "x", "kind"}` returns WaterTAP's outputs and the solve time.
- `POST /prefetch` gives the points the plant is about to reach. During the daily pattern or the salinity swing, the page sends the next condition values with the set-points held (or at the optimum, in AUTO).
- `GET /results?since=n` returns the solutions finished since the page last asked. The page pulls them every 1.5 s and draws them on the trends, at the time the plant was at that point.

Checks (an OpenNN proposal, the points before and after applying it) go first, in order. Next comes the plant's current point; a newer one replaces one still waiting, so the simulator follows the operator instead of working through a backlog. Prefetched points come last. Results are cached, and the stored points are loaded at start. Every new solve is appended to `models/<plant>/data/session_simulations_local.csv` (not in Git), so the points visited while presenting can join the next retraining; `session_simulations.csv` holds those of earlier sessions that the current networks were trained with. Wastewater solves record the rain too: a log begun before the rain input is rewritten with a `rain` column (0 for its rows) when the service starts. `prepare_training.py` takes the dry rows and `prepare_rain_training.py` the rainy ones.

`python simulator/server.py --check` builds both WaterTAP models, solves one point with each and exits; setup runs it.

A point no one could predict, such as a slider just moved, still takes one WaterTAP solve, a few seconds. The trends show "WaterTAP solving" meanwhile.

## Retraining and rebuilding

The page is built from `src/` (`index.html`, `style.css`, `model.js`, `app.js`) and the data in `weights/`, `data/` and `models/`. From this folder, in the `watertap` conda environment (the surrogate programs are `..\model\ro_surrogate.exe` and `..\bsm2_steady\model\bsm2_surrogate.exe`, which `..\build_surrogates.bat` builds with OpenNN; see the [main README](../README.md#setup)):

```
python tools/more_simulations.py ro 600
python tools/more_simulations.py bsm2 800 6
python tools/resolve_washout.py 6 20                      (wastewater only, after a first prepare_training)
python tools/prepare_training.py ro
..\model\ro_surrogate.exe train models\ro
..\model\ro_surrogate.exe export models\ro
..\model\ro_surrogate.exe validation models\ro
..\model\ro_surrogate.exe sweep models\ro
python tools/compare_networks.py ro
python tools/export_weights.py ro
python tools/check_forward.py %TEMP%\fwd ro
python tools/verify_points.py ro models/ro/results/dashboard_optima.csv data/ro_optima_verified.csv
python tools/compare_optima.py ro
node tools/check_optimizer.mjs ro
(the same for bsm2, with ..\bsm2_steady\model\bsm2_surrogate.exe and the settings below, and then)
python tools/verify_points.py bsm2 data/bsm2_optima_verified.csv data/bsm2_optima_verified.csv 6 retry
python tools/scenarios.py bsm2 12 6
python tools/scenarios.py bsm2 12 6 --optimum
python tools/scenarios.py ro 12 3
python tools/scenarios.py ro 12 3 --optimum
python tools/compare_scenarios.py
python tools/build_dashboard.py
```

The `scenarios.py` runs store the guided demo's paths in WaterTAP: 12 defaults each held through the whole condition range, and the optimum the demo applies at each default's condition held the same way. The page carries them, so the demo shows WaterTAP without the simulator. Desalination paths that cannot run at high salinity (feed pressure below the brine's osmotic pressure) are stored but not used by the demo.

The wastewater network is trained with `set BSM2_LAYERS=2`, `set BSM2_NEURONS=16,24,32` and `set BSM2_SELECT=nh4` (two hidden layers, chosen by the validation error of log NH₄ between 1 and 20 mg/L). Without them, `bsm2_surrogate train` reproduces the toy's original one-layer network. `set BSM2_SWEEP=min_energy` (or `min_cost`, `max_biogas`) sweeps one objective into `results/dashboard_optima_<objective>.csv`, so the three can run in parallel; join them into `dashboard_optima.csv`. `bsm2_surrogate` takes its inputs from the dataset's columns, so a dataset with a `rain` column gives the storm network, and `set BSM2_RAIN_LEVELS=0,1500,3000,4500` sweeps those rain flows too.

The storm network (`models/bsm2_rain`, see [Storm](#storm-wet-weather)) has its own pipeline:

```
python tools/storm_simulations.py 1000 6 --until=16:30     wet-weather simulations, resumable
python tools/run_storm.py --until=19:45                    training, optima and WaterTAP checks, rounds
python tools/build_dashboard.py                            the page carries the storm network once it exists
```

`run_storm.py` runs `prepare_rain_training.py` (the dry training set with no rain, the wet-weather simulations and, from the second round, the checked optima), trains two hidden layers of 32 or 48 neurons, exports the weights, sweeps the three objectives at four rain levels, solves the optima in WaterTAP and, if one misses a limit, starts a second round when there is time for it. `compare_rain.py` then writes `models/bsm2_rain/summary.txt` and `comparison.csv`. The networks on the page were made with OpenNN dev `31da51dbd`, which is not on GitHub; OpenNN 26.0.3, which `..\build_surrogates.bat` downloads, retrains the dry-weather networks bit for bit and gives the storm network the same validation predictions (see the [main README](../README.md#setup)).

| Step | What it does | Time |
|---|---|---|
| `more_simulations.py` | New WaterTAP simulations (`models/<plant>/data/new_simulations.csv`). | about 20 minutes (600 RO, 4 workers), about an hour (800 BSM2, 6 workers): run it outside working hours |
| `prepare_training.py` | Merges the original data, the new simulations, the dashboard points and the session log; keeps 15% of the new simulations out as `holdout.csv`. | seconds |
| `train`, `export`, `sweep` | Train the network (8 to 32 hidden neurons, best worst-output validation R²), write its weights, and compute the optima over the condition grid. | minutes each |
| `compare_networks.py` | Original against retrained network on the held-out simulations (`models/<plant>/comparison.csv`). | seconds |
| `export_weights.py`, `check_forward.py` | Browser weight files, and the check that the browser network matches OpenNN. | seconds |
| `verify_points.py` | Solves the optima in WaterTAP; `retry` re-attempts the wastewater points that did not converge, from nearby solved ones. | about 5 to 15 minutes per wastewater file |
| `compare_optima.py` | Original against retrained optima, both as solved in WaterTAP. | seconds |
| `resolve_washout.py` | Re-solves the wastewater rows that ended without nitrifiers (NH₄ about 40 mg/L) from nearby nitrifying points; `prepare_training.py` replaces those that solve with nitrifiers. | at most the minutes given |
| `validation` (surrogate mode) | The validation split's predictions, from which the page computes the safety margin of any limit you set. | seconds |
| `scenarios.py`, `compare_scenarios.py` | The demo's paths (a default, or the optimum at its condition, held while the influent or the salinity sweeps its range) solved in WaterTAP; NH₄ of each wastewater network along the default paths (`models/bsm2/scenarios_nh4.png`). | about 10 minutes per wastewater set, 5 per desalination set |
| `check_optimizer.mjs` | The page's optimizer against OpenNN's stored optima at the permit limits. | seconds |
| `make_defaults.py` | Only to draw new default operations (then `verify_points.py` on `data/<plant>_default_candidates.csv`). The page keeps the stored defaults that the network also places within every limit. | seconds |
| `storm_simulations.py` | Wet-weather WaterTAP simulations: a Latin hypercube over the six inputs and rain (0 to 6,000 m³/d), written as chunks finish (`models/bsm2_rain/data/rain_simulations.csv`). | about 4 hours for 1,000 points on 6 workers |
| `run_storm.py`, `prepare_rain_training.py`, `compare_rain.py` | The storm network's training, optima, WaterTAP checks and comparison with the dry network, in rounds, stopping at a given time. | about 1 to 1.5 hours per round, most of it the WaterTAP checks |
| `build_dashboard.py` | Writes `water_treatment_hmi.html`. | seconds |
