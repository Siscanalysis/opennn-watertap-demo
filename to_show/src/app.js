"use strict";

// Water Treatment HMI: two plants (BSM2 wastewater, RO desalination) driven by OpenNN networks that
// run in the browser (model.js). Optimal set-points were precomputed with OpenNN response
// optimization over a grid of disturbance values. The WaterTAP simulator runs next to the network
// when the local service (simulator/server.py, started by start_simulator.bat) is up: every settled
// operating point and every OpenNN proposal is solved there and shown beside the prediction.
// Without the service, stored WaterTAP solutions (default operations and optima) are shown.

(() => {
  const DATA = JSON.parse(document.getElementById("plant-data").textContent);
  const reduceMotion = typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const TICK_MS = 250;           // control loop and animation step
  const SAMPLE_MS = 1000;        // trend sampling
  const WINDOW_MIN = 12 * 60;    // trend window, plant minutes
  const RAMP_MS = 3500;          // set-point ramp when a proposal is applied

  // ------------------------------------------------------------------ helpers

  const $ = (id) => document.getElementById(id);
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const fmt = (v, d = 0) => (Number.isFinite(v)
    ? v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–");
  const signed = (v, d = 1) => {
    const r = Number(v.toFixed(d));
    return (r > 0 ? "+" : r < 0 ? "−" : "±") + fmt(Math.abs(r), d);
  };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clockText = (minutes) => {
    const m = ((Math.floor(minutes) % 1440) + 1440) % 1440;
    return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  };
  const lerp = (a, b, f) => a + (b - a) * f;
  const ease = (f) => (f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2);

  const ICON = {
    ok: '<svg class="icon" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M3.5 6.2l1.7 1.7 3.3-3.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    warn: '<svg class="icon" viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1.2l5 9.3H1z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M6 4.7v2.5M6 8.7v.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    alarm: '<svg class="icon" viewBox="0 0 12 12" aria-hidden="true"><rect x="1" y="1" width="10" height="10" rx="1.5" fill="currentColor"/><path d="M6 3.3v3.5M6 8.6v.1" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round"/></svg>',
  };
  const STATE_TEXT = { ok: "Normal", warn: "Near limit", alarm: "Limit exceeded" };
  // A label inside a sentence: lower case first, except a leading formula or acronym (COD, BOD₅).
  const asPhrase = (label) => (/^[A-Z][A-Z0-9\u2080-\u2089]+(\s|$)/.test(label) ? label : label.charAt(0).toLowerCase() + label.slice(1));
  const stateChip = (status, text) => `<span class="state ${status}">${ICON[status]}${esc(text ?? STATE_TEXT[status])}</span>`;

  // ------------------------------------------------------------------ plant definitions

  const DEFS = {
    bsm2: {
      title: "Wastewater treatment · activated sludge and anaerobic digestion (BSM2 layout)",
      disturbance: {
        name: "influent", label: "Influent flow", unit: "m³/d", digits: 0, tag: "FI-101",
        patternLabel: "Daily pattern",
        pattern: (t) => 20650 + 3300 * Math.sin((2 * Math.PI * (t - 540)) / 1440)
          + 700 * Math.sin((4 * Math.PI * (t - 480)) / 1440),
      },
      decisions: [
        { name: "do3", label: "Dissolved oxygen, aerobic tank 3", unit: "mg/L", digits: 2, step: 0.01 },
        { name: "do4", label: "Dissolved oxygen, aerobic tank 4", unit: "mg/L", digits: 2, step: 0.01 },
        { name: "do5", label: "Dissolved oxygen, aerobic tank 5", unit: "mg/L", digits: 2, step: 0.01 },
        { name: "recycle", label: "Internal recycle", unit: "% of tank-5 outflow", scale: 100, digits: 0, step: 0.005 },
        { name: "wastage", label: "Sludge wastage", unit: "% of clarifier underflow", scale: 100, digits: 2, step: 0.0002 },
      ],
      outputs: {
        lcow: { label: "Cost of water", unit: "$/m³", digits: 4 },
        sec: { label: "Energy", unit: "kWh/m³", digits: 3 },
        tss: { label: "Suspended solids", unit: "mg/L", digits: 1 },
        cod: { label: "COD", unit: "mg/L", digits: 1 },
        tn: { label: "Total nitrogen", unit: "mg/L", digits: 1 },
        bod5: { label: "BOD₅", unit: "mg/L", digits: 2 },
        nh4: { label: "Ammonium NH₄", unit: "mg/L", digits: 2 },
        biogas: { label: "Biogas", unit: "m³/d", digits: 0 },
      },
      objectives: [
        { id: "min_energy", label: "Minimum energy", output: "sec", sense: "min" },
        { id: "min_cost", label: "Minimum cost of water", output: "lcow", sense: "min" },
        { id: "max_biogas", label: "Maximum biogas", output: "biogas", sense: "max" },
      ],
      kpis: [
        { output: "sec", better: "lower", annual: "energy" },
        { output: "lcow", better: "lower", annual: "cost" },
        { output: "biogas", better: "higher", annual: "biogas" },
      ],
      checkRows: ["sec", "lcow", "nh4", "tn", "cod", "tss", "biogas"],
      trends: [
        { key: "sec", label: "Energy", unit: "kWh/m³", digits: 3 },
        { key: "nh4", label: "Effluent NH₄", unit: "mg/L", digits: 2, limit: 4 },
        { key: "disturbance", label: "Influent flow", unit: "m³/d", digits: 0 },
      ],
      limitsTitle: "Effluent limits",
    },
    ro: {
      title: "Seawater reverse osmosis · pressure-exchanger energy recovery",
      disturbance: {
        name: "salinity", label: "Feed salinity", unit: "g/kg", digits: 1, tag: "AIT-001",
        patternLabel: "Salinity swing",
        pattern: (t) => 35 + 6.5 * Math.sin((2 * Math.PI * (t - 360)) / 1440),
      },
      decisions: [
        { name: "recovery", label: "Water recovery", unit: "%", scale: 100, digits: 1, step: 0.001 },
        { name: "pressure", label: "Feed pressure", unit: "bar", digits: 1, step: 0.1 },
      ],
      outputs: {
        lcow: { label: "Cost of water", unit: "$/m³", digits: 4 },
        sec: { label: "Energy", unit: "kWh/m³", digits: 3 },
        permeate_ppm: { label: "Permeate salinity", unit: "mg/kg", digits: 0 },
        flux_out: { label: "Brine-end water flux", unit: "kg/m²·h", digits: 2 },
        flux_avg: { label: "Average water flux", unit: "kg/m²·h", digits: 1 },
        area: { label: "Membrane in service", unit: "m²", digits: 1 },
      },
      objectives: [{ id: "min_cost", label: "Minimum cost of water", output: "lcow", sense: "min" }],
      kpis: [
        { output: "lcow", better: "lower", annual: "per1000" },
        { output: "sec", better: "lower" },
        { output: "area", better: null },
      ],
      checkRows: ["lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"],
      trends: [
        { key: "lcow", label: "Cost of water", unit: "$/m³", digits: 4 },
        { key: "permeate_ppm", label: "Permeate salinity", unit: "mg/kg", digits: 0, limit: 500 },
        { key: "disturbance", label: "Feed salinity", unit: "g/kg", digits: 1 },
      ],
      limitsTitle: "Product and membrane limits",
    },
  };

  // Wet weather, for a plant that carries a storm network (a seventh input, rain): rain adds to the
  // influent and dilutes it. The Storm switch ramps the rain to the highest level the storm optima
  // were computed for, over about an hour of plant time, and back to none over about two; the plant
  // settles at each level (steady state), so the rain moves level by level.
  const STORM = Object.fromEntries(Object.keys(DEFS).map((id) => [id, DATA.plants[id].storm || null]));
  const RAIN = Object.fromEntries(Object.keys(DEFS).map((id) => [id, !!STORM[id]]));
  const RAIN_UP_MIN = 60, RAIN_DOWN_MIN = 120;
  const rainLevels = (id) => [0, ...(STORM[id] ? STORM[id].rain_levels : [])];
  // The rain of the plant now, unless given.
  const rainOf = (id, rain) => (RAIN[id] ? rain ?? (app.plants[id] ? app.plants[id].rain : 0) : 0);
  // The network in use, with its margins and optima: the storm network while it rains, and the
  // dry-weather network otherwise (more accurate without rain).
  const net = (id, rain) => (STORM[id] && rainOf(id, rain) > 0 ? STORM[id] : DATA.plants[id]);
  const isStorm = (id, rain) => net(id, rain) !== DATA.plants[id];
  function snapRain(id, value) {
    let best = 0;
    for (const level of rainLevels(id)) if (Math.abs(level - value) < Math.abs(best - value)) best = level;
    return best;
  }
  const stormRain = (id) => Math.max(...rainLevels(id));

  // Ranges of the sliders: the region each network was trained on.
  for (const [id, def] of Object.entries(DEFS)) {
    const inputs = Object.fromEntries(DATA.plants[id].model.inputs.map((i) => [i.name, i]));
    for (const d of def.decisions) { d.min = inputs[d.name].min; d.max = inputs[d.name].max; }
    const grid = DATA.plants[id].disturbance.grid;
    def.disturbance.grid = grid;
    def.disturbance.min = grid[0];
    def.disturbance.max = grid[grid.length - 1];
    def.disturbance.step = grid.length > 1 ? grid[1] - grid[0] : 1;
  }

  // ------------------------------------------------------------------ state

  const app = { active: "bsm2", speed: 10, plants: {}, lastSample: 0, hover: {}, source: "nn", networkMicros: {}, pointKey: "", pointSince: 0 };

  function newPlantState(id) {
    const def = DEFS[id];
    return {
      id, t: 6 * 60, disturbance: def.disturbance.grid[Math.floor(def.disturbance.grid.length / 2)],
      setpoints: {}, baseline: null, defaultIndex: -1,
      mode: "manual", objective: def.objectives[0].id, proposal: false, pattern: false, ramp: null,
      result: null, history: [], events: [], limitStates: {}, outputs: {},
      limits: permitLimits(id), proposalPending: false, autoHeld: "",
      storm: false, rain: 0, rainFlow: 0,
    };
  }

  // ------------------------------------------------------------------ limits the operator can change

  // Where each bound may be set (minimum, maximum, step). The permit value is the default.
  const BOUND_RANGE = {
    nh4: [0.5, 20, 0.1], tn: [5, 40, 0.5], cod: [50, 200, 1], tss: [10, 60, 0.5], bod5: [2, 25, 0.5],
    permeate_ppm: [150, 1000, 10], flux_out: [0.2, 8, 0.1], pressure: [50, 85, 0.5],
  };

  function permitLimits(id) {
    const plant = DATA.plants[id];
    const outputs = plant.limits.map((l) => {
      const upper = l.max !== undefined, bound = upper ? l.max : l.min;
      return { key: l.output, kind: "output", upper, bound, permit: bound, enabled: true };
    });
    const inputs = (plant.input_limits || []).map((l) =>
      ({ key: l.input, kind: "input", upper: true, bound: l.max, permit: l.max, enabled: true, displayMargin: l.margin }));
    return [...outputs, ...inputs];
  }

  const isPermit = (s) => s.limits.every((l) => l.enabled && l.bound === l.permit);
  const limitsSignature = (s) => s.limits.map((l) => (l.enabled ? `${l.key}${l.upper ? "<" : ">"}${l.bound}` : `${l.key}:off`)).join(",");
  const limitMeta = (id, l) => (l.kind === "output" ? DEFS[id].outputs[l.key] : DEFS[id].decisions.find((d) => d.name === l.key));

  // The safety margin of a bound: the 95th percentile of the network's validation error among the
  // samples within a factor of two of the bound, the rule OpenNN used for the stored optima. It
  // belongs to the network in use at that rain.
  const MARGINS = new Map();
  function marginFor(id, key, bound, rain) {
    const storm = isStorm(id, rain);
    const cacheKey = `${id}|${storm}|${key}|${bound}`;
    if (!MARGINS.has(cacheKey)) {
      const data = (net(id, rain).margin_data || {})[key] || [];
      const errors = data.filter(([t]) => t >= 0.5 * bound && t <= 2 * bound).map(([, e]) => e).sort((a, b) => a - b);
      MARGINS.set(cacheKey, errors.length ? errors[Math.ceil(0.95 * errors.length) - 1] : 0);
    }
    return MARGINS.get(cacheKey);
  }
  const limitMargin = (id, l) => (l.kind === "output" ? marginFor(id, l.key, l.bound) : l.displayMargin || 0);

  const plantState = () => app.plants[app.active];

  // rain: the plant's current rain unless given; it picks the network (the dry-weather one has no
  // rain input).
  function predict(id, setpoints, disturbance, rain) {
    const r = rainOf(id, rain);
    return PlantModel.predict(net(id, r).model, { ...setpoints, [DEFS[id].disturbance.name]: disturbance, rain: r });
  }

  function snapToGrid(id, value) {
    const grid = DEFS[id].disturbance.grid;
    let best = grid[0];
    for (const g of grid) if (Math.abs(g - value) < Math.abs(best - value)) best = g;
    return best;
  }

  // The optima of the network in use, over the whole condition grid; the storm network's are stored
  // rain level by rain level.
  function storedOptimum(id, objective, disturbance, rain) {
    const grid = DEFS[id].disturbance.grid;
    const i = grid.indexOf(snapToGrid(id, disturbance));
    const r = snapRain(id, rainOf(id, rain)), source = net(id, r);
    const level = source.rain_levels ? source.rain_levels.indexOf(r) : 0;
    const list = source.objectives[objective] || [];
    return level < 0 ? null : list[level * grid.length + i] || null;
  }

  const decisionValues = (id, x) => Object.fromEntries(DEFS[id].decisions.map((d) => [d.name, x[d.name]]));

  // ------------------------------------------------------------------ optimizer for the operator's limits

  // With the permit limits the page uses the optima OpenNN response optimization computed
  // beforehand (and WaterTAP checked). With other limits it solves the same problem itself, on the
  // OpenNN network, in a background thread (solveOptimum in src/optimizer.js), one condition at a
  // time and cached. A custom optimum has `custom: true` and `meets`: whether the network places it
  // within every limit and its margin.
  const CUSTOM = { worker: null, next: 1, jobs: new Map(), results: new Map(), requested: new Set() };

  function startOptimizer() {
    try {
      const source = `${$("model-src").textContent}\n${$("optimizer-src").textContent}\n`
        + "self.onmessage = (e) => self.postMessage({ id: e.data.id, result: solveOptimum(e.data.task) });";
      const worker = new Worker(URL.createObjectURL(new Blob([source], { type: "text/javascript" })));
      worker.onmessage = (e) => {
        const job = CUSTOM.jobs.get(e.data.id);
        CUSTOM.jobs.delete(e.data.id);
        if (job) finishCustom(job, e.data.result);
      };
      worker.onerror = () => {
        CUSTOM.worker = null;
        for (const job of CUSTOM.jobs.values()) runHere(job);
        CUSTOM.jobs.clear();
      };
      CUSTOM.worker = worker;
    } catch (error) {
      CUSTOM.worker = null;   // no workers here: the optimizer runs on the page's own thread
    }
  }
  const runHere = (job) => setTimeout(() => finishCustom(job, solveOptimum(job.task)), 0);
  const customKey = (s, objective, condition) => `${s.id}|${objective}|${condition}|${RAIN[s.id] ? s.rain : ""}|${limitsSignature(s)}`;

  function optimumFor(id, objective, disturbance) {
    const s = app.plants[id];
    if (isPermit(s)) return storedOptimum(id, objective, disturbance);
    const condition = snapToGrid(id, disturbance);
    const key = customKey(s, objective, condition);
    if (CUSTOM.results.has(key)) return CUSTOM.results.get(key);
    requestCustom(s, objective, condition, key);
    return null;
  }

  const usable = (opt) => !!opt && !(opt.custom && !opt.meets);
  const optimizing = (s) => {
    if (isPermit(s)) return false;
    const key = customKey(s, s.objective, snapToGrid(s.id, s.disturbance));
    return CUSTOM.requested.has(key) && !CUSTOM.results.has(key);
  };

  function requestCustom(s, objective, condition, key) {
    if (CUSTOM.requested.has(key)) return;
    CUSTOM.requested.add(key);
    const def = DEFS[s.id], o = def.objectives.find((x) => x.id === objective);
    const model = net(s.id, s.rain).model;
    const box = Object.fromEntries(model.inputs.map((i) => [i.name, i]));
    const constraints = [];
    for (const l of s.limits) {
      if (!l.enabled) continue;
      if (l.kind === "output") {
        const m = marginFor(s.id, l.key, l.bound);
        constraints.push({ kind: "output", key: l.key, upper: l.upper, threshold: l.upper ? l.bound - m : l.bound + m });
      } else {
        constraints.push({ kind: "input", key: l.key, upper: l.upper, threshold: l.bound, span: box[l.key].max - box[l.key].min });
      }
    }
    if (s.id === "ro") constraints.push({ kind: "guard", min: DATA.plants.ro.guard });
    const stored = storedOptimum(s.id, objective, condition);
    const task = {
      model, constraints, seed: 7,
      decisions: def.decisions.map((d) => ({ name: d.name, min: d.min, max: d.max })),
      fixed: { [def.disturbance.name]: condition, rain: s.rain },
      objective: { output: o.output, sense: o.sense },
      starts: [...(stored ? [decisionValues(s.id, stored.x)] : []), { ...s.setpoints }],
    };
    const job = { key, id: s.id, objective, condition, task, started: performance.now() };
    if (CUSTOM.worker) {
      const n = CUSTOM.next++;
      CUSTOM.jobs.set(n, job);
      CUSTOM.worker.postMessage({ id: n, task });
    } else runHere(job);
  }

  function finishCustom(job, result) {
    const point = { x: result.x, y: result.y, meets: result.feasible, custom: true,
      ms: performance.now() - job.started, evaluations: result.evaluations };
    CUSTOM.results.set(job.key, point);
    const s = app.plants[job.id];
    if (s.proposal && s.proposalPending && customKey(s, s.objective, snapToGrid(s.id, s.disturbance)) === job.key) {
      s.proposalPending = false;
      announceProposal(s, point);
    }
    if (job.id === app.active) renderLive();
  }
  const withCondition = (s, setpoints) => ({
    ...setpoints, [DEFS[s.id].disturbance.name]: s.disturbance, ...(RAIN[s.id] ? { rain: s.rain } : {}) });
  const currentX = (s) => withCondition(s, s.setpoints);

  // ------------------------------------------------------------------ WaterTAP simulator service

  // Served by the service itself, the page talks to its own origin; opened as a file or from any
  // other site (GitHub Pages, for one), it looks for the service on the viewer's own computer.
  // Results are cached per operating point.
  const SIM = {
    base: /^https?:$/.test(location.protocol) && ["127.0.0.1", "localhost"].includes(location.hostname)
      ? "" : "http://127.0.0.1:8765",
    online: false, status: null, results: new Map(), pending: new Set(), lastPlant: {}, live: 0,
    seq: 0, prefetchSent: {}, prefetchAt: 0, polling: false, pollTimer: 0, launchedAt: 0,
  };

  // The "Start WaterTAP" button opens an opennn-watertap: link, which setup.bat registers on Windows
  // for this user: the browser asks once, then runs to_show/start_simulator.bat. A page cannot start
  // a program by itself, so without that setup nothing happens and the page says how to set it up.
  const LAUNCH_WAIT_MS = 15000;     // no answer by then: probably not set up on this computer
  const LAUNCH_POLL_MS = 150000;    // fast polling this long after the button
  const canLaunch = /Windows/.test(navigator.userAgent);
  const launching = () => !SIM.online && SIM.launchedAt > 0 && performance.now() - SIM.launchedAt < LAUNCH_POLL_MS;
  const launchUnanswered = () => !SIM.online && SIM.launchedAt > 0 && performance.now() - SIM.launchedAt > LAUNCH_WAIT_MS;
  const START_BUTTON = '<button type="button" class="btn small sim-start" data-action="start-sim">Start WaterTAP</button>';

  function startSimulator() {
    SIM.launchedAt = performance.now();
    // Through a hidden frame, so that a browser without the handler shows its error there and the
    // page keeps its state.
    let frame = $("sim-launch");
    if (!frame) {
      frame = document.createElement("iframe");
      frame.id = "sim-launch";
      frame.hidden = true;
      frame.setAttribute("aria-hidden", "true");
      document.body.appendChild(frame);
    }
    frame.src = "opennn-watertap://start";
    logEvent(plantState(), "sim", "Starting the WaterTAP simulator on this computer");
    if (!SIM.polling) { clearTimeout(SIM.pollTimer); pollSimulator(); }
    renderLive();
  }

  // Where this page sits, to name the files of the setup: the folder of the page and its parent.
  function pageFolders() {
    if (location.protocol !== "file:" || location.host) return null;
    let path = decodeURIComponent(location.pathname);
    const windows = /^\/[A-Za-z]:\//.test(path);
    if (windows) path = path.slice(1).replace(/\//g, "\\");
    const sep = windows ? "\\" : "/";
    const parts = path.split(sep);
    parts.pop();
    return { page: parts.join(sep), project: parts.slice(0, -1).join(sep) || sep };
  }

  // How to get the simulator running, for the offline state.
  function launchHelp() {
    const where = pageFolders();
    const repo = "https://github.com/Siscanalysis/opennn-watertap-demo";
    if (!canLaunch)
      return where
        ? `To run WaterTAP next to the network, run <b>./setup.sh</b> once in <code>${esc(where.project)}</code>, then <b>./start_demo.sh</b>.`
        : `To run WaterTAP next to the network, download the project from <a href="${repo}">${repo.replace("https://", "")}</a>, run <b>./setup.sh</b> once, then <b>./start_demo.sh</b>.`;
    if (!where)
      return `To run WaterTAP on this computer, download the project from <a href="${repo}">${repo.replace("https://", "")}</a> and run <b>setup.bat</b> once; then this button starts it.`;
    return `The button needs a one-time setup on this computer: double-click <b>setup.bat</b> in <code>${esc(where.project)}</code> `
      + `(it installs WaterTAP, about 1 GB, and connects this button). You can also start <b>start_simulator.bat</b> in <code>${esc(where.page)}</code> yourself.`;
  }

  // The simulator's inputs: the dry-weather network's, and the rain where there is a storm network
  // (none in a point stored without it).
  const inputNames = (id) => [...DATA.plants[id].model.inputs.map((i) => i.name), ...(RAIN[id] ? ["rain"] : [])];
  const pointKey = (id, x) => `${id}|${inputNames(id).map((n) => Number(n === "rain" ? x[n] ?? 0 : x[n]).toPrecision(6)).join("|")}`;
  const simReady = (id) => SIM.online && !!(SIM.status && SIM.status.ready && SIM.status.ready[id]);

  // WaterTAP solutions carried by the page: default operations, optima, and the guided demo's paths
  // (each stored default held through the whole condition range), so the demo shows WaterTAP even
  // without the simulator.
  function preloadStored() {
    for (const id of Object.keys(DEFS)) {
      const plant = DATA.plants[id];
      const optima = [plant, ...(STORM[id] ? [STORM[id]] : [])].flatMap((n) => Object.values(n.objectives).flat());
      for (const point of [...plant.defaults, ...optima])
        if (point && point.true)
          SIM.results.set(pointKey(id, point.x), { status: "ok", outputs: point.true, seconds: null, source: "stored" });
      const paths = plant.paths;
      if (!paths) continue;
      for (const row of paths.rows) {
        const x = Object.fromEntries(paths.inputs.map((n, i) => [n, row[i]]));
        const outputs = Object.fromEntries(paths.outputs.map((n, i) => [n, row[paths.inputs.length + i]]));
        SIM.results.set(pointKey(id, x), { status: "ok", outputs, seconds: null, source: "stored" });
      }
    }
  }

  async function pollSimulator() {
    if (SIM.polling) return;
    SIM.polling = true;
    const wasOnline = SIM.online;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2500);
      const response = await fetch(`${SIM.base}/status`, { cache: "no-store", signal: controller.signal });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`status ${response.status}`);
      SIM.status = await response.json();
      SIM.online = true;
      await pullResults();
    } catch (error) {
      SIM.online = false;
      SIM.status = null;
    } finally {
      SIM.polling = false;
    }
    if (SIM.online && !wasOnline && SIM.launchedAt) {
      SIM.launchedAt = 0;
      logEvent(plantState(), "sim", "WaterTAP simulator found on this computer");
    }
    clearTimeout(SIM.pollTimer);
    SIM.pollTimer = setTimeout(pollSimulator, SIM.online ? 1500 : launching() ? 1000 : 8000);
    renderLive();
  }

  // Solutions the service finished on its own (points solved ahead of the plant), into the cache and
  // the trends.
  async function pullResults() {
    if (!SIM.status || !("workers" in SIM.status)) return;   // a service without the results feed
    const response = await fetch(`${SIM.base}/results?since=${SIM.seq}`, { cache: "no-store" });
    if (!response.ok) return;
    const feed = await response.json();
    SIM.seq = feed.seq;
    for (const item of feed.results) {
      if (!DEFS[item.plant] || !isSolved(item)) continue;
      const key = pointKey(item.plant, item.x);
      if (SIM.results.has(key)) continue;
      SIM.results.set(key, { status: item.status, outputs: item.outputs, seconds: item.seconds, source: "live" });
      fillHistory(item.plant, key, item.outputs);
    }
  }

  // The points the plant is about to reach, nearest first, for the service to solve before it gets
  // there: the condition's next values along the daily pattern or the salinity swing, with the
  // set-points held (manual) or at the optimum for each value (AUTO).
  function upcomingPoints(s) {
    if (!s.pattern) return [];
    const def = DEFS[s.id], points = [], seen = new Set([snapToGrid(s.id, s.disturbance)]);
    for (let minutes = 5; minutes <= 6 * 60 && points.length < 6; minutes += 5) {
      const value = snapToGrid(s.id, clamp(def.disturbance.pattern(s.t + minutes), def.disturbance.min, def.disturbance.max));
      if (seen.has(value)) continue;
      seen.add(value);
      let setpoints = s.setpoints;
      if (s.mode === "auto") {
        const opt = optimumFor(s.id, s.objective, value);
        if (!usable(opt)) continue;
        setpoints = decisionValues(s.id, opt.x);
      }
      const x = { ...setpoints, [def.disturbance.name]: value, ...(RAIN[s.id] ? { rain: s.rain } : {}) };
      if (!SIM.results.has(pointKey(s.id, x))) points.push(x);
    }
    return points;
  }

  async function sendPrefetch(s, now) {
    if (!simReady(s.id) || now - SIM.prefetchAt < 1000) return;
    SIM.prefetchAt = now;
    const points = upcomingPoints(s);
    const signature = points.map((x) => pointKey(s.id, x)).join(";");
    if (signature === (SIM.prefetchSent[s.id] || "")) return;
    SIM.prefetchSent[s.id] = signature;
    try {
      await fetch(`${SIM.base}/prefetch`, {
        method: "POST", headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({ plant: s.id, points: points.map((x) => Object.fromEntries(inputNames(s.id).map((n) => [n, x[n]]))) }),
      });
    } catch (error) { /* the next status poll finds out whether the service is still there */ }
  }

  async function requestSim(id, x, kind) {
    const key = pointKey(id, x);
    if (SIM.results.has(key) || SIM.pending.has(key) || !simReady(id)) return;
    SIM.pending.add(key);
    try {
      const response = await fetch(`${SIM.base}/simulate`, {
        method: "POST", headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({ plant: id, x: Object.fromEntries(inputNames(id).map((n) => [n, x[n]])), kind }),
      });
      const result = await response.json();
      if (["ok", "washout", "failed"].includes(result.status)) {
        SIM.results.set(key, { ...result, source: result.seconds == null ? "stored" : "live" });
        if (kind === "plant") SIM.lastPlant[id] = key;
        if (result.seconds != null && result.status !== "failed") SIM.live += 1;
        if (isSolved(result)) fillHistory(id, key, result.outputs);
        onSimulated(id, x, result, kind);
      }
    } catch (error) {
      SIM.online = false;
    } finally {
      SIM.pending.delete(key);
      if (id === app.active) renderLive();
    }
  }

  // A solution that arrives after the plant has moved on still belongs in the trends, at the times
  // the plant sat at that operating point.
  function fillHistory(id, key, outputs) {
    let filled = false;
    for (const p of app.plants[id].history) {
      if (p.key !== key) continue;
      for (const c of DEFS[id].trends)
        if (c.key !== "disturbance" && !Number.isFinite(p[`sim_${c.key}`])) { p[`sim_${c.key}`] = outputs[c.key]; filled = true; }
    }
    if (filled && id === app.active) renderCharts();
  }

  // What the simulator says about the current operating point: its result, or the last one solved
  // while it works on this one.
  function simFor(s) {
    const key = pointKey(s.id, currentX(s));
    const result = SIM.results.get(key);
    if (result) {
      if (isSolved(result)) SIM.lastPlant[s.id] = key;
      return { state: result.status === "failed" ? "failed" : "solved", result, current: true };
    }
    const last = SIM.lastPlant[s.id] ? SIM.results.get(SIM.lastPlant[s.id]) : null;
    const state = SIM.pending.has(key) ? "solving" : !SIM.online ? "offline"
      : !simReady(s.id) ? "warming" : "waiting";
    return { state, result: state === "offline" ? null : last, current: false };
  }

  function onSimulated(id, x, result, kind) {
    const s = app.plants[id];
    const def = DEFS[id];
    if (kind === "plant" && !s.pattern && result.status !== "failed" && result.seconds != null) {
      const key = def.kpis[0].output, meta = def.outputs[key];
      const predicted = predict(id, decisionValues(id, x), x[def.disturbance.name], x.rain)[key];
      logEvent(s, "sim", `Operating point solved in ${fmt(result.seconds, 1)} s: ${meta.label.toLowerCase()} ${fmt(result.outputs[key], meta.digits)} ${meta.unit} (OpenNN ${fmt(predicted, meta.digits)})`);
    }
    if (kind === "plant" && result.status === "failed" && !s.pattern)
      logEvent(s, "sim", "Did not converge at the operating point");
    logOptimizationResult(s);
  }

  // Speed of the network in this browser, for the comparison panel.
  function measureNetwork() {
    for (const id of Object.keys(DEFS)) {
      const s = app.plants[id];
      const n = 3000, start = performance.now();
      for (let i = 0; i < n; i++) predict(id, s.setpoints, s.disturbance);
      app.networkMicros[id] = ((performance.now() - start) * 1000) / n;
    }
  }

  // The orange dot that marks WaterTAP values across the page; it pulses while a solve runs.
  const simMark = (busy = false) => `<span class="sim-mark${busy ? " busy" : ""}" aria-hidden="true"></span>`;
  const isSolved = (r) => !!(r && r.outputs);

  // ------------------------------------------------------------------ limits and alarms

  // "Near limit" starts once a value is a tenth of the way into the safety margin: the optimizer
  // places its answers on the margin's edge by design, and those should read as normal.
  const INSIDE = 0.1;

  function limitList(s, y) {
    return limitRows(s.id, y, s.setpoints);
  }

  // Limits met by a set of outputs (the network's or WaterTAP's), without the safety margins. Only
  // the limits in force count.
  function limitsMet(id, y, setpoints) {
    const rows = limitRows(id, y, setpoints).filter((l) => l.enabled);
    const failed = rows.filter((l) => l.status === "alarm");
    return { total: rows.length, met: rows.length - failed.length, failed };
  }

  // The plant's current limits (the permit's or the operator's) against a set of outputs; a limit
  // switched off has the status "off".
  function limitRows(id, y, setpoints) {
    return app.plants[id].limits.map((l) => {
      const meta = limitMeta(id, l);
      const value = l.kind === "output" ? y[l.key] : setpoints[l.key];
      const margin = limitMargin(id, l);
      const status = !l.enabled ? "off" : l.upper
        ? (value > l.bound ? "alarm" : value > l.bound - (1 - INSIDE) * margin ? "warn" : "ok")
        : (value < l.bound ? "alarm" : value < l.bound + (1 - INSIDE) * margin ? "warn" : "ok");
      const label = l.kind === "output" ? meta.label : `${meta.label} (pump rating)`;
      return { key: l.key, kind: l.kind, label, unit: meta.unit, digits: meta.digits, value, bound: l.bound,
        permit: l.permit, upper: l.upper, margin, status, enabled: l.enabled };
    });
  }

  function modelAdvisory(s, y) {
    if (s.id === "bsm2" && y.nh4 > 8) {
      const error = net(s.id, s.rain).facts.nh4_high_mae;
      return `Ammonium above 8 mg/L means the nitrifiers are close to washout. The network is least accurate there${error ? ` (about ${fmt(error, error < 10 ? 1 : 0)} mg/L mean error on simulations it never saw)` : ""}; treat these values as indicative.`;
    }
    if (s.id === "ro") {
      const g = DATA.plants.ro.guard;
      if (s.setpoints.pressure * (1 - s.setpoints.recovery) / s.disturbance < g)
        return "This pressure is too low for this salinity and recovery: the plant data never went there, so the network is extrapolating. Raise the pressure or lower the recovery.";
    }
    return null;
  }

  // ------------------------------------------------------------------ events

  function logEvent(s, kind, text) {
    const latest = s.events[0];
    if (latest && latest.kind === kind && latest.text === text && Math.abs(latest.t - s.t) < 1) return;
    s.events.unshift({ t: s.t, kind, text });
    if (s.events.length > 80) s.events.length = 80;
    if (s.id === app.active) renderEvents();
  }

  function describeSetpoints(id, x) {
    return DEFS[id].decisions.map((d) => `${shortName(d)} ${fmt(x[d.name] * (d.scale || 1), d.digits)}${d.unit.startsWith("%") ? " %" : ""}`).join(" · ");
  }

  function shortName(d) {
    return ({ do3: "DO3", do4: "DO4", do5: "DO5", recycle: "IR", wastage: "WAS", recovery: "Recovery", pressure: "Pressure" })[d.name] || d.name;
  }

  // ------------------------------------------------------------------ actions

  // onlyPaths: one of the defaults whose path through the condition range is stored in WaterTAP,
  // so the guided demo shows WaterTAP dots even without the simulator.
  function loadDefault(s, announce = true, onlyPaths = false) {
    const pool = DATA.plants[s.id].defaults;
    const all = pool.map((_, k) => k);
    const choices = onlyPaths && pool.some((d) => d.path) ? all.filter((k) => pool[k].path) : all;
    let i = choices[Math.floor(Math.random() * choices.length)];
    if (choices.length > 1 && i === s.defaultIndex) i = choices[(choices.indexOf(i) + 1) % choices.length];
    s.defaultIndex = i;
    s.baseline = pool[i];
    s.ramp = null;
    s.mode = "manual";
    s.proposal = false;
    s.result = null;
    s.setpoints = decisionValues(s.id, pool[i].x);
    if (!s.pattern) s.disturbance = pool[i].x[DEFS[s.id].disturbance.name];
    if (announce)
      logEvent(s, "info", `Default operation ${i + 1} of ${pool.length} loaded (random feasible set-points, solved in WaterTAP): ${describeSetpoints(s.id, s.setpoints)}`);
  }

  function propose(s) {
    s.proposal = true;
    s.result = null;
    s.proposalPending = false;
    const opt = optimumFor(s.id, s.objective, s.disturbance);
    if (opt) announceProposal(s, opt);
    else if (!isPermit(s)) s.proposalPending = true;   // announced when the optimizer answers
    else logEvent(s, "info", "No OpenNN optimum is stored for this condition.");
  }

  function announceProposal(s, opt) {
    const objective = DEFS[s.id].objectives.find((o) => o.id === s.objective);
    if (!usable(opt)) {
      logEvent(s, "opt", `No set-points meet your limits with their safety margins (${objective.label.toLowerCase()})`);
      return;
    }
    requestSim(s.id, withCondition(s, decisionValues(s.id, opt.x)), "check");
    const now = predict(s.id, s.setpoints, s.disturbance);
    const then = predict(s.id, decisionValues(s.id, opt.x), s.disturbance);
    const change = 100 * (then[objective.output] - now[objective.output]) / now[objective.output];
    logEvent(s, "opt", `OpenNN proposal (${objective.label.toLowerCase()}${opt.custom ? ", your limits" : ""}): ${DEFS[s.id].outputs[objective.output].label.toLowerCase()} ${signed(change, 1)} %`);
  }

  function applyProposal(s) {
    const opt = optimumFor(s.id, s.objective, s.disturbance);
    if (!usable(opt)) return;
    s.ramp = { from: { ...s.setpoints }, to: decisionValues(s.id, opt.x), start: performance.now(), duration: reduceMotion ? 1 : RAMP_MS, label: "the OpenNN optimum" };
    s.proposal = false;
    // Kept for the result card: the operating point before and after, and what OpenNN predicted.
    const before = currentX(s), after = withCondition(s, s.ramp.to);
    s.result = {
      objective: s.objective, before, after, logged: false,
      beforeY: predict(s.id, decisionValues(s.id, before), s.disturbance),
      afterY: predict(s.id, s.ramp.to, s.disturbance),
    };
    requestSim(s.id, before, "check");
    requestSim(s.id, after, "check");
    logEvent(s, "opt", `Operator applied the OpenNN set-points: ${describeSetpoints(s.id, s.ramp.to)}`);
    logOptimizationResult(s);
  }

  // Once WaterTAP has solved both operating points, the event log records the outcome.
  function logOptimizationResult(s) {
    const r = s.result;
    if (!r || r.logged) return;
    const before = SIM.results.get(pointKey(s.id, r.before)), after = SIM.results.get(pointKey(s.id, r.after));
    if (!before || !after || !before.outputs || !after.outputs) return;
    const def = DEFS[s.id], objective = def.objectives.find((o) => o.id === r.objective);
    const key = objective.output, meta = def.outputs[key];
    const real = (100 * (after.outputs[key] - before.outputs[key])) / before.outputs[key];
    const predicted = (100 * (r.afterY[key] - r.beforeY[key])) / r.beforeY[key];
    const limits = limitsMet(s.id, after.outputs, decisionValues(s.id, r.after));
    r.logged = true;
    logEvent(s, "sim", `Optimization result: ${meta.label.toLowerCase()} ${fmt(before.outputs[key], meta.digits)} → ${fmt(after.outputs[key], meta.digits)} ${meta.unit} (${signed(real, 1)} %; OpenNN predicted ${signed(predicted, 1)} %), ${limits.failed.length ? `${limits.failed.length} limit${limits.failed.length > 1 ? "s" : ""} exceeded` : "every limit met"}`);
  }

  // A limit changed: alarms, bars and WaterTAP checks use it at once, and an open proposal or AUTO
  // moves to the optimum for the new limits (computed in the background unless they are the permit's).
  function limitsChanged(s, text) {
    logEvent(s, "info", text);
    s.autoHeld = "";
    if (s.proposal && s.mode !== "auto") propose(s);
    else optimumFor(s.id, s.objective, s.disturbance);
    renderLive();
  }

  function setMode(s, mode) {
    if (s.mode === mode) return;
    s.mode = mode;
    s.ramp = null;
    s.proposal = false;
    const objective = DEFS[s.id].objectives.find((o) => o.id === s.objective);
    logEvent(s, "opt", mode === "auto"
      ? `AUTO on: set-points follow the OpenNN optimum (${objective.label.toLowerCase()})`
      : "AUTO off: set-points held for the operator");
  }

  // ------------------------------------------------------------------ control loop

  function advance(s, dtMs, now) {
    s.t += (dtMs / 1000) * app.speed;
    const def = DEFS[s.id];

    if (s.pattern) {
      const next = snapToGrid(s.id, clamp(def.disturbance.pattern(s.t), def.disturbance.min, def.disturbance.max));
      if (next !== s.disturbance) s.disturbance = next;
    }

    if (RAIN[s.id]) {
      const peak = stormRain(s.id), minutes = (dtMs / 1000) * app.speed;
      const target = s.storm ? peak : 0;
      const step = (peak * minutes) / (s.storm ? RAIN_UP_MIN : RAIN_DOWN_MIN);
      s.rainFlow = target > s.rainFlow ? Math.min(target, s.rainFlow + step) : Math.max(target, s.rainFlow - step);
      const level = snapRain(s.id, s.rainFlow);
      if (level !== s.rain) {
        s.rain = level;
        if (level === peak && s.storm) logEvent(s, "info", `Storm: rain inflow at ${fmt(level, 0)} m³/d`);
        if (level === 0 && !s.storm) logEvent(s, "info", "Storm over: no rain inflow");
      }
    }

    if (s.ramp) {
      const f = clamp((now - s.ramp.start) / s.ramp.duration, 0, 1);
      for (const d of def.decisions) s.setpoints[d.name] = lerp(s.ramp.from[d.name], s.ramp.to[d.name], ease(f));
      if (f >= 1) {
        s.setpoints = { ...s.ramp.to };
        logEvent(s, s.ramp.label === "the OpenNN optimum" ? "opt" : "info", `Set-points reached ${s.ramp.label}`);
        s.ramp = null;
      }
    } else if (s.mode === "auto") {
      const opt = optimumFor(s.id, s.objective, s.disturbance);
      if (usable(opt)) {
        // About a second to the optimum, then exactly onto it, so the operating point matches the
        // optimum's WaterTAP solution (stored or solved ahead) without waiting.
        for (const d of def.decisions) {
          const target = opt.x[d.name];
          const gap = target - s.setpoints[d.name];
          s.setpoints[d.name] = Math.abs(gap) < 1e-2 * (d.max - d.min) || reduceMotion ? target : s.setpoints[d.name] + gap * 0.5;
        }
        s.autoHeld = "";
      } else if (opt) {
        // No set-points meet the operator's limits here: AUTO holds the plant and says so once.
        const held = `${s.disturbance}|${s.rain}|${limitsSignature(s)}|${s.objective}`;
        if (s.autoHeld !== held) {
          s.autoHeld = held;
          logEvent(s, "opt", "AUTO: no set-points meet your limits at this condition, set-points held");
        }
      }
    }

    s.outputs = predict(s.id, s.setpoints, s.disturbance);

    for (const l of limitList(s, s.outputs)) {
      const before = s.limitStates[l.key];
      if (before !== undefined && before !== "alarm" && l.status === "alarm")
        logEvent(s, "alarm", `${l.label} ${fmt(l.value, l.digits)} ${l.unit}: ${l.upper ? "above" : "below"} the limit of ${fmt(l.bound, l.digits)}`);
      if (before === "alarm" && (l.status === "ok" || l.status === "warn"))
        logEvent(s, "normal", `${l.label} back within the limit (${fmt(l.value, l.digits)} ${l.unit})`);
      s.limitStates[l.key] = l.status;
    }
  }

  function sample(s) {
    const y = s.outputs;
    const point = { t: s.t, disturbance: s.disturbance, rain: s.rain, key: pointKey(s.id, currentX(s)) };
    const sim = simFor(s);
    const truth = sim.current && sim.result.outputs ? sim.result.outputs : null;
    for (const c of DEFS[s.id].trends) {
      if (c.key === "disturbance") continue;
      point[c.key] = y[c.key];
      if (truth) point[`sim_${c.key}`] = truth[c.key];
      const ceiling = autoCeiling(s, c.key);
      if (ceiling !== undefined) point[`auto_${c.key}`] = ceiling;
    }
    s.history.push(point);
    while (s.history.length && s.history[0].t < s.t - WINDOW_MIN) s.history.shift();
  }

  let last = performance.now();
  function tick() {
    const now = performance.now();
    const dt = Math.min(now - last, 1000);
    last = now;
    const s = plantState();
    advance(s, dt, now);
    // The simulator gets the operating point once it has settled for half a second. Open proposals
    // and applied ones are checked too (again if the service started after they were made).
    const x = currentX(s), key = pointKey(s.id, x);
    if (key !== app.pointKey) { app.pointKey = key; app.pointSince = now; }
    else if (!s.ramp && now - app.pointSince >= 450) requestSim(s.id, x, "plant");
    if (s.proposal && s.mode !== "auto") {
      const opt = optimumFor(s.id, s.objective, s.disturbance);
      if (usable(opt)) requestSim(s.id, withCondition(s, decisionValues(s.id, opt.x)), "check");
    }
    if (s.result) { requestSim(s.id, s.result.before, "check"); requestSim(s.id, s.result.after, "check"); }
    sendPrefetch(s, now);
    if (now - app.lastSample >= SAMPLE_MS) { sample(s); app.lastSample = now; renderCharts(); }
    renderLive();
  }

  // ------------------------------------------------------------------ SVG building blocks

  function flowPipe(id, d, thin = false) {
    return `<path class="${thin ? "pipe-thin" : "pipe"}" d="${d}"/><path class="flow" id="${id}" d="${d}" style="--dur:2s"/>`;
  }
  function arrow(x, y, dir) {
    const a = 6, b = 9;
    const pts = {
      right: [[x, y], [x - b, y - a], [x - b, y + a]],
      left: [[x, y], [x + b, y - a], [x + b, y + a]],
      up: [[x, y], [x - a, y + b], [x + a, y + b]],
      down: [[x, y], [x - a, y - b], [x + a, y - b]],
    }[dir].map((p) => p.join(",")).join(" ");
    return `<polygon class="arrowhead" points="${pts}"/>`;
  }
  function tag(id, x, y, w, label, unit, cls = "") {
    return `<g id="${id}"><title>${esc(label)}</title><rect class="tag-box ${cls}" id="${id}-box" x="${x}" y="${y}" width="${w}" height="34" rx="3"/>`
      + `<text class="tag-label" id="${id}-l" x="${x + 6}" y="${y + 12}">${esc(label)}</text>`
      + `<text x="${x + 6}" y="${y + 28}"><tspan class="tag-value" id="${id}-v">–</tspan><tspan class="tag-unit" dx="5">${esc(unit)}</tspan></text></g>`;
  }
  function eqLabel(x, y, text, id, anchor = "middle") {
    return `<text class="eq-label" x="${x}" y="${y}" text-anchor="${anchor}">${esc(text)}</text>`
      + (id ? `<text class="eq-id" x="${x}" y="${y + 13}" text-anchor="${anchor}">${esc(id)}</text>` : "");
  }
  function pump(x, y, r, dir = "right") {
    const tri = {
      right: `M${x - r * 0.45} ${y - r * 0.62} L${x + r * 0.72} ${y} L${x - r * 0.45} ${y + r * 0.62} Z`,
      left: `M${x + r * 0.45} ${y - r * 0.62} L${x - r * 0.72} ${y} L${x + r * 0.45} ${y + r * 0.62} Z`,
      up: `M${x - r * 0.62} ${y + r * 0.45} L${x} ${y - r * 0.72} L${x + r * 0.62} ${y + r * 0.45} Z`,
    }[dir];
    return `<circle class="eq" cx="${x}" cy="${y}" r="${r}"/><path class="eq-thin" d="${tri}"/>`;
  }
  function rotor(id, x, y, r, blades = 3) {
    // The invisible circle centres the bounding box on the hub, so the rotor spins in place.
    let paths = `<circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="none"/>`;
    for (let k = 0; k < blades; k++) {
      const a = (2 * Math.PI * k) / blades;
      paths += `<line x1="${x}" y1="${y}" x2="${(x + r * Math.cos(a)).toFixed(1)}" y2="${(y + r * Math.sin(a)).toFixed(1)}"/>`;
    }
    return `<g class="rotor eq-thin" id="${id}" style="--spin:2s">${paths}</g>`;
  }

  // ------------------------------------------------------------------ BSM2 diagram

  function diagramBsm2() {
    const x0 = 232, x1 = 756, top = 110, bottom = 226;
    const w = (x1 - x0) / 5;
    const c = [0, 1, 2, 3, 4].map((k) => x0 + w * (k + 0.5));
    const names = ["ANOXIC 1", "ANOXIC 2", "AEROBIC 3", "AEROBIC 4", "AEROBIC 5"];
    let s = '<svg viewBox="0 0 1120 540" role="img" aria-labelledby="dg-title"><title id="dg-title">Process diagram of the wastewater plant</title>';

    // influent and primary clarifier
    s += `<text class="eq-label" x="16" y="168">INFLUENT</text>` + flowPipe("f-in", "M16 180 H100") + arrow(100, 180, "right");
    s += tag("t-in", 8, 196, 88, "FI-101 FLOW", "m³/d");
    if (RAIN.bsm2) s += tag("t-rain", 8, 238, 88, "OF WHICH RAIN", "m³/d");
    s += eqLabel(140, 118, "PRIMARY CLARIFIER", "PC-101");
    s += `<rect class="eq" x="100" y="140" width="80" height="60"/><rect class="liquid" x="101.5" y="150" width="77" height="49"/>`
      + `<path class="eq" d="M100 200 L180 200 L140 236 Z"/><path class="sludge" d="M112 210 L168 210 L140 235 Z"/>`;
    s += flowPipe("f-pc", "M180 170 H232");

    // internal recycle (drawn first so tanks and tags sit on top)
    s += flowPipe("f-ir", "M754 110 V50 H260 V108") + arrow(260, 110, "down") + pump(472, 50, 11, "left");
    s += tag("t-ir", 500, 6, 178, "FIC-201 INTERNAL RECYCLE", "% of tank-5 outflow", "setpoint");

    // bioreactor basin
    s += `<rect class="eq" x="${x0}" y="${top}" width="${x1 - x0}" height="${bottom - top}"/>`
      + `<rect class="liquid" x="${x0 + 2}" y="${top + 12}" width="${x1 - x0 - 4}" height="${bottom - top - 14}"/>`
      + `<rect class="liquid-air" x="${(x0 + 2 * w + 1).toFixed(1)}" y="${top + 12}" width="${(3 * w - 3).toFixed(1)}" height="${bottom - top - 14}"/>`;
    for (let k = 1; k < 5; k++) s += `<line class="eq-thin" x1="${(x0 + w * k).toFixed(1)}" y1="${top}" x2="${(x0 + w * k).toFixed(1)}" y2="${bottom - 22}"/>`;
    for (let k = 0; k < 5; k++) s += eqLabel(c[k].toFixed(1), 140, names[k], `R${k + 1}`);

    // mixers in the anoxic tanks
    for (const k of [0, 1]) {
      s += `<rect class="eq" x="${(c[k] - 8).toFixed(1)}" y="92" width="16" height="12" rx="2"/>`
        + `<line class="eq-thin" x1="${c[k].toFixed(1)}" y1="104" x2="${c[k].toFixed(1)}" y2="192"/>`
        + `<g class="rotor" id="mix-${k}" style="--spin:1.4s"><ellipse class="eq-thin" cx="${c[k].toFixed(1)}" cy="196" rx="12" ry="3.2"/></g>`;
    }

    // diffusers, bubbles and DO controllers in the aerobic tanks
    for (const k of [2, 3, 4]) {
      s += `<line class="eq-thin" x1="${(c[k] - 40).toFixed(1)}" y1="216" x2="${(c[k] + 40).toFixed(1)}" y2="216"/>`;
      for (let i = 0; i < 8; i++) {
        const bx = (c[k] - 35 + i * 10 + (i % 2) * 3).toFixed(1);
        const r = (1.8 + (i % 3) * 0.6).toFixed(1);
        s += `<circle class="bubble" id="b${k}-${i}" cx="${bx}" cy="210" r="${r}" style="animation-delay:${(-i * 0.37).toFixed(2)}s"/>`;
      }
      s += `<line class="eq-thin" x1="${c[k].toFixed(1)}" y1="96" x2="${c[k].toFixed(1)}" y2="${top}"/>`;
      s += tag(`t-do${k + 1}`, +(c[k] - 44).toFixed(1), 62, 88, `AIC-30${k + 1} DO`, "mg/L", "setpoint");
    }

    // aeration: blower and air header
    s += `<path class="pipe-air" d="M444 262 H${c[4].toFixed(1)}"/>`;
    for (const k of [2, 3, 4]) s += `<path class="pipe-air" d="M${c[k].toFixed(1)} 262 V217"/>`;
    s += `<circle class="eq" cx="430" cy="262" r="14"/>` + rotor("blower", 430, 262, 11, 3);
    s += eqLabel(430, 296, "BLOWERS", "B-101");
    s += tag("t-sec", 276, 246, 112, "JI-101 ENERGY", "kWh/m³");

    // to the secondary clarifier and the effluent analyzers
    s += flowPipe("f-ml", "M756 170 H812");
    s += eqLabel(857, 118, "SECONDARY CLARIFIER", "SC-101");
    s += `<rect class="eq" x="812" y="140" width="90" height="60"/><rect class="liquid" x="813.5" y="150" width="87" height="49"/>`
      + `<path class="eq" d="M812 200 L902 200 L857 240 Z"/><path class="sludge" d="M826 212 L888 212 L857 239 Z"/>`;
    s += `<text class="eq-label" x="1104" y="141" text-anchor="end">EFFLUENT</text>` + flowPipe("f-eff", "M902 152 H1104") + arrow(1104, 152, "right");
    const analyzers = [["nh4", "AIT-501 NH₄"], ["tn", "AIT-502 TOTAL N"], ["cod", "AIT-503 COD"], ["tss", "AIT-504 TSS"], ["bod5", "AIT-505 BOD₅"]];
    analyzers.forEach(([key, label], i) => { s += tag(`t-${key}`, 930, 166 + i * 38, 176, label, "mg/L"); });

    // return and waste sludge
    s += flowPipe("f-ras", "M857 240 V318 H252 V228") + arrow(252, 228, "up") + pump(560, 318, 11, "left");
    s += eqLabel(560, 345, "RETURN SLUDGE", "P-202");
    s += `<circle class="arrowhead" cx="857" cy="318" r="4"/>`;
    s += flowPipe("f-was", "M857 318 V392", true);
    s += tag("t-was", 740, 278, 110, "FIC-401 WASTAGE", "%", "setpoint");
    s += `<rect class="eq" x="822" y="392" width="70" height="40"/><path class="eq" d="M822 432 L892 432 L857 458 Z"/><path class="sludge" d="M832 440 L882 440 L857 457 Z"/>`;
    s += eqLabel(900, 410, "THICKENER", "TK-301", "start");

    // digestion, biogas and dewatering
    s += flowPipe("f-thk", "M857 458 V470 H680", true) + arrow(680, 470, "left");
    s += flowPipe("f-ps", "M140 236 V522 H640 V499", true) + arrow(640, 498, "up");
    s += `<text class="eq-id" x="150" y="514">PRIMARY SLUDGE</text>`;
    s += `<ellipse class="eq" cx="640" cy="440" rx="44" ry="56"/><ellipse class="sludge" cx="640" cy="452" rx="39" ry="42"/><ellipse class="gasfill" cx="640" cy="404" rx="26" ry="12"/>`;
    s += eqLabel(588, 414, "DIGESTER", "AD-401", "end");
    s += flowPipe("f-gas", "M640 384 V364 H790", true) + arrow(790, 364, "right");
    s += `<text class="eq-id" x="715" y="356" text-anchor="middle">BIOGAS TO CHP</text>`;
    s += tag("t-gas", 692, 392, 112, "FI-402 BIOGAS", "m³/d");
    s += flowPipe("f-dig", "M596 440 H472", true) + arrow(472, 440, "left");
    s += `<rect class="eq" x="400" y="420" width="70" height="40" rx="6"/><line class="eq-thin" x1="408" y1="440" x2="462" y2="440"/><circle class="eq-thin" cx="435" cy="440" r="7"/>`;
    s += eqLabel(435, 478, "DEWATERING", "DW-501");
    s += flowPipe("f-cake", "M400 440 H302", true) + arrow(302, 440, "left");
    s += `<text class="eq-id" x="304" y="428">SLUDGE CAKE</text>`;
    s += "</svg>";
    return s;
  }

  // Values for the diagram tags: the network's prediction, or WaterTAP's solution when the operator
  // shows the simulator (dimmed while it belongs to the previous operating point).
  function displayOutputs(s) {
    if (app.source === "nn") return { y: s.outputs, stale: false, missing: false };
    const sim = simFor(s);
    if (sim.result && sim.result.outputs) return { y: sim.result.outputs, stale: !sim.current, missing: false };
    return { y: s.outputs, stale: false, missing: true };
  }

  function updateBsm2Diagram(s) {
    const sp = s.setpoints;
    const shown = displayOutputs(s), y = shown.y;
    const value = (key, digits) => (shown.missing ? "…" : fmt(y[key], digits));
    const flow = s.disturbance + s.rain;   // what the influent meter reads: sewage and rain
    setTag("t-in", fmt(flow, 0));
    if (RAIN.bsm2) setTag("t-rain", fmt(s.rain, 0));
    setTag("t-ir", fmt(sp.recycle * 100, 0));
    setTag("t-was", fmt(sp.wastage * 100, 2));
    setTag("t-sec", value("sec", 3), undefined, shown.stale);
    setTag("t-gas", value("biogas", 0), undefined, shown.stale);
    for (const k of [3, 4, 5]) setTag(`t-do${k}`, fmt(sp[`do${k}`], 2));
    const states = Object.fromEntries(limitList(s, y).map((l) => [l.key, shown.missing ? "ok" : l.status]));
    for (const key of ["nh4", "tn", "cod", "tss", "bod5"]) {
      const meta = DEFS.bsm2.outputs[key];
      setTag(`t-${key}`, value(key, meta.digits), states[key], shown.stale);
    }
    const out = s.outputs;
    for (const k of [2, 3, 4]) {
      const visible = clamp(Math.round(2 + (6 * (sp[`do${k + 1}`] - 0.5)) / 2.5), 2, 8);
      for (let i = 0; i < 8; i++) { const b = $(`b${k}-${i}`); if (b) b.style.display = i < visible ? "" : "none"; }
    }
    setFlow("f-in", flow / 20648);
    setFlow("f-pc", flow / 20648);
    setFlow("f-ml", flow / 20648 * 1.6);
    setFlow("f-eff", flow / 20648);
    setFlow("f-ir", sp.recycle / 0.6 * 1.4);
    setFlow("f-ras", 1);
    setFlow("f-was", sp.wastage / 0.015 * 0.6);
    for (const id of ["f-thk", "f-ps", "f-dig", "f-cake"]) setFlow(id, 0.45);
    setFlow("f-gas", out.biogas / 1216 * 0.8);
    const meanDo = (sp.do3 + sp.do4 + sp.do5) / 3;
    const blower = $("blower");
    if (blower) blower.style.setProperty("--spin", `${(2.6 - meanDo * 0.6).toFixed(2)}s`);
  }

  // ------------------------------------------------------------------ RO diagram

  function diagramRo() {
    let s = '<svg viewBox="0 0 1120 400" role="img" aria-labelledby="dg-title"><title id="dg-title">Process diagram of the desalination plant</title>';
    s += `<text class="eq-label" x="16" y="188">SEAWATER</text>` + flowPipe("f-in", "M16 200 H110");
    s += tag("t-sal", 8, 214, 96, "AIT-001 SALINITY", "g/kg");
    s += tag("t-feed", 8, 252, 96, "FI-001 FEED", "m³/h");
    s += `<circle class="arrowhead" cx="110" cy="200" r="4"/>`;

    // high-pressure branch
    s += flowPipe("f-hp1", "M110 200 V150 H172");
    s += pump(190, 150, 18, "right") + eqLabel(190, 186, "HP PUMP", "P-101");
    s += flowPipe("f-hp", "M208 150 H518") + arrow(520, 150, "right");
    s += `<circle class="arrowhead" cx="470" cy="150" r="4"/>`;

    // pressure exchanger branch and booster
    s += flowPipe("f-lp", "M110 200 V310 H298") + arrow(300, 310, "right");
    s += `<rect class="eq" x="300" y="280" width="100" height="60" rx="4"/><circle class="eq-thin" cx="350" cy="310" r="15"/>` + rotor("px-rotor", 350, 310, 13, 4);
    s += eqLabel(350, 358, "PRESSURE EXCHANGER", "PX-101");
    s += flowPipe("f-px", "M400 290 H470 V152");
    s += pump(470, 232, 12, "up") + eqLabel(488, 236, "BOOSTER", "P-102", "start");

    // RO train
    s += tag("t-lcow", 170, 66, 118, "COST OF WATER", "$/m³");
    s += tag("t-sec", 300, 66, 120, "JI-101 ENERGY", "kWh/m³");
    s += tag("t-p", 520, 66, 108, "PIC-101 PRESSURE", "bar", "setpoint");
    s += tag("t-rec", 636, 66, 108, "FIC-101 RECOVERY", "%", "setpoint");
    s += tag("t-area", 752, 66, 108, "MEMBRANE AREA", "m²");
    s += `<text class="eq-label" x="690" y="114" text-anchor="middle">RO-101 MEMBRANE TRAIN</text>`;
    s += `<rect class="eq" x="520" y="120" width="340" height="60" rx="28"/><rect class="liquid" x="534" y="126" width="312" height="48" rx="22"/>`
      + `<path class="eq-thin" d="M546 168 L834 132"/><path class="eq-thin" d="M546 172 L834 136" opacity="0.5"/>`;
    s += tag("t-fx", 560, 196, 132, "AVERAGE FLUX", "kg/m²·h");
    s += tag("t-fo", 700, 196, 168, "BRINE-END FLUX · MIN 1", "kg/m²·h");

    // permeate
    s += `<text class="eq-label" x="1104" y="122" text-anchor="end">PERMEATE · PRODUCT WATER</text>`;
    s += flowPipe("f-perm", "M860 135 H1104") + arrow(1104, 135, "right");
    s += tag("t-perm", 930, 148, 174, "AIT-201 PERMEATE · MAX 500", "mg/kg");
    s += tag("t-pflow", 930, 186, 174, "FI-201 PERMEATE FLOW", "m³/h");

    // brine back through the pressure exchanger
    s += flowPipe("f-br", "M860 170 H900 V330 H402") + arrow(402, 330, "left");
    s += flowPipe("f-dis", "M300 330 H16") + arrow(16, 330, "left");
    s += `<text class="eq-label" x="16" y="348">BRINE</text>`;
    s += tag("t-brine", 130, 342, 150, "AIT-301 BRINE (CALC.)", "g/kg");
    s += "</svg>";
    return s;
  }

  function updateRoDiagram(s) {
    const sp = s.setpoints;
    const shown = displayOutputs(s), y = shown.y;
    const value = (key, digits) => (shown.missing ? "…" : fmt(y[key], digits));
    const states = Object.fromEntries(limitList(s, y).map((l) => [l.key, shown.missing && l.key !== "pressure" ? "ok" : l.status]));
    const feed = 3.6;   // m3/h: WaterTAP's feed of 1 L/s
    setTag("t-sal", fmt(s.disturbance, 1));
    setTag("t-feed", fmt(feed, 1));
    setTag("t-lcow", value("lcow", 4), undefined, shown.stale);
    setTag("t-sec", value("sec", 3), undefined, shown.stale);
    setTag("t-p", fmt(sp.pressure, 1), states.pressure);
    setTag("t-rec", fmt(sp.recovery * 100, 1));
    setTag("t-area", value("area", 1), undefined, shown.stale);
    setTag("t-fx", value("flux_avg", 1), undefined, shown.stale);
    setTag("t-fo", value("flux_out", 2), states.flux_out, shown.stale);
    setTag("t-perm", value("permeate_ppm", 0), states.permeate_ppm, shown.stale);
    setTag("t-pflow", `≈ ${fmt(sp.recovery * feed * (1 - s.disturbance / 1000), 2)}`);
    // The analyzer tags name the limit in force, the permit's or the operator's.
    const limitText = (key, name) => {
      const l = s.limits.find((x) => x.key === key);
      return l && l.enabled ? `${name} · ${l.upper ? "MAX" : "MIN"} ${fmtBound(l.bound)}` : name;
    };
    setLabel("t-fo", limitText("flux_out", "BRINE-END FLUX"));
    setLabel("t-perm", limitText("permeate_ppm", "AIT-201 PERMEATE"));
    const brine = (s.disturbance - sp.recovery * y.permeate_ppm / 1000) / (1 - sp.recovery);
    setTag("t-brine", shown.missing ? "…" : fmt(brine, 1), undefined, shown.stale);
    setFlow("f-in", 1);
    setFlow("f-hp1", sp.recovery * 1.8);
    setFlow("f-hp", sp.recovery * 1.8);
    setFlow("f-lp", (1 - sp.recovery) * 1.8);
    setFlow("f-px", (1 - sp.recovery) * 1.8);
    setFlow("f-perm", sp.recovery * 1.8);
    setFlow("f-br", (1 - sp.recovery) * 1.8);
    setFlow("f-dis", (1 - sp.recovery) * 1.8);
    const px = $("px-rotor");
    if (px) px.style.setProperty("--spin", `${(1.2 / Math.max(0.2, 1 - sp.recovery)).toFixed(2)}s`);
  }

  function setTag(id, value, status, stale = false) {
    const v = $(`${id}-v`);
    if (v && v.textContent !== value) v.textContent = value;
    if (v) v.classList.toggle("is-stale", stale);
    const box = $(`${id}-box`);
    if (box && status !== undefined) {
      box.classList.toggle("is-alarm", status === "alarm");
      box.classList.toggle("is-warn", status === "warn");
    }
  }

  function setLabel(id, text) {
    const label = $(`${id}-l`);
    if (label && label.textContent !== text) label.textContent = text;
  }

  function setFlow(id, factor) {
    const el = $(id);
    if (!el) return;
    const dur = `${(2.2 / clamp(factor, 0.15, 4)).toFixed(2)}s`;
    if (el.style.getPropertyValue("--dur") !== dur) el.style.setProperty("--dur", dur);
  }

  // ------------------------------------------------------------------ operator panel

  function buildControls() {
    const s = plantState(), def = DEFS[s.id];
    const dist = def.disturbance;

    $("disturbance-block").innerHTML = `
      <div class="block-title"><span>Plant condition</span><span>${esc(dist.tag)}</span></div>
      <div class="field">
        <div class="field-row"><label for="dist">${esc(dist.label)}</label><span class="value"><span id="dist-v"></span> <small>${esc(dist.unit)}</small></span></div>
        <div class="track"><input type="range" id="dist" min="${dist.min}" max="${dist.max}" step="${dist.step}"></div>
        <div class="range-ends"><span>${fmt(dist.min, dist.digits)}</span><span>${fmt(dist.max, dist.digits)}</span></div>
      </div>
      <div class="row-wrap">
        <div class="segmented" role="group" aria-label="Condition over time">
          <button type="button" id="pattern-off">Constant</button>
          <button type="button" id="pattern-on">${esc(dist.patternLabel)}</button>
        </div>
        <div class="segmented" role="group" aria-label="Simulation speed">
          ${[1, 10, 30].map((v) => `<button type="button" data-speed="${v}" id="speed-${v}">${v} min/s</button>`).join("")}
        </div>
      </div>
      ${RAIN[s.id] ? `<div class="row-wrap">
        <div class="segmented" role="group" aria-label="Weather">
          <button type="button" id="weather-dry">Dry weather</button>
          <button type="button" id="weather-storm">Storm</button>
        </div>
        <span class="hint" id="rain-note"></span>
      </div>` : ""}`;

    $("setpoint-block").innerHTML = `
      <div class="block-title"><span>Set-points</span><span id="sp-owner">Operator</span></div>
      ${def.decisions.map((d) => `
        <div class="field">
          <div class="field-row"><label for="sp-${d.name}">${esc(d.label)}</label><span class="value"><span id="sp-${d.name}-v"></span> <small>${esc(d.unit)}</small></span></div>
          <div class="track"><input type="range" id="sp-${d.name}" min="${d.min}" max="${d.max}" step="${d.step}"><span class="target" id="tg-${d.name}" hidden></span></div>
        </div>`).join("")}
      <div class="row-wrap">
        <button type="button" class="btn" id="new-default">New default operation</button>
        <button type="button" class="btn ghost" id="back-default">Back to default</button>
      </div>`;

    $("optimizer-block").innerHTML = `
      <div class="block-title"><span>OpenNN optimizer</span><span>Response optimization</span></div>
      <div class="field">
        <label for="objective">Objective</label>
        <select class="select" id="objective">${def.objectives.map((o) => `<option value="${o.id}">${esc(o.label)}</option>`).join("")}</select>
      </div>
      <fieldset class="constraints">
        <legend>Constraints to respect</legend>
        ${s.limits.map((l) => {
          const meta = limitMeta(s.id, l), [lo, hi, step] = BOUND_RANGE[l.key];
          const name = l.kind === "output" ? meta.label : `${meta.label} (pump)`;
          return `<div class="c-row">
            <input type="checkbox" id="c-on-${l.key}" data-limit="${l.key}" aria-label="Respect the ${esc(asPhrase(name))} limit">
            <label class="c-name" for="c-bound-${l.key}">${esc(name)}</label>
            <span class="c-op" aria-hidden="true">${l.upper ? "≤" : "≥"}</span>
            <input type="number" class="c-bound" id="c-bound-${l.key}" data-limit="${l.key}" min="${lo}" max="${hi}" step="${step}" inputmode="decimal">
            <span class="c-unit">${esc(unitOf(meta))}</span>
          </div>`;
        }).join("")}
        <div class="c-foot">
          <span class="hint" id="c-mode"></span>
          <button type="button" class="btn ghost small" id="c-reset">Reset to permit</button>
        </div>
      </fieldset>
      <button type="button" class="btn primary" id="optimize">Optimize with OpenNN</button>
      <label class="switch" for="auto">
        <span class="switch-text"><b>AUTO</b><span>Set-points follow the OpenNN optimum as conditions change</span></span>
        <input type="checkbox" id="auto"><span class="knob" aria-hidden="true"></span>
      </label>
      <div class="row-wrap">
        <button type="button" class="btn ghost" id="demo">Play guided demo</button>
        <span class="hint" id="demo-step"></span>
      </div>`;

    $("dist").addEventListener("input", (e) => {
      const st = plantState();
      st.pattern = false;
      st.disturbance = snapToGrid(st.id, +e.target.value);
      st.outputs = predict(st.id, st.setpoints, st.disturbance);
      renderLive();
    });
    $("dist").addEventListener("change", () => {
      const st = plantState();
      logEvent(st, "info", `${DEFS[st.id].disturbance.label} set to ${fmt(st.disturbance, DEFS[st.id].disturbance.digits)} ${DEFS[st.id].disturbance.unit}`);
    });
    $("pattern-on").addEventListener("click", () => {
      const st = plantState();
      if (!st.pattern) { st.pattern = true; logEvent(st, "info", `${DEFS[st.id].disturbance.patternLabel} on`); }
      renderLive();
    });
    $("pattern-off").addEventListener("click", () => {
      const st = plantState();
      if (st.pattern) { st.pattern = false; logEvent(st, "info", `${DEFS[st.id].disturbance.patternLabel} off: condition held at ${fmt(st.disturbance, DEFS[st.id].disturbance.digits)} ${DEFS[st.id].disturbance.unit}`); }
      renderLive();
    });
    for (const v of [1, 10, 30]) $(`speed-${v}`).addEventListener("click", () => { app.speed = v; renderLive(); });
    if (RAIN[s.id]) {
      $("weather-storm").addEventListener("click", () => {
        const st = plantState();
        if (!st.storm) { st.storm = true; logEvent(st, "info", `Storm: rain inflow rising to ${fmt(stormRain(st.id), 0)} m³/d, diluting the influent`); }
        renderLive();
      });
      $("weather-dry").addEventListener("click", () => {
        const st = plantState();
        if (st.storm) { st.storm = false; logEvent(st, "info", "Rain stopping: inflow falling to none"); }
        renderLive();
      });
    }

    for (const d of def.decisions) {
      const input = $(`sp-${d.name}`);
      input.addEventListener("input", (e) => {
        const st = plantState();
        if (st.mode === "auto") return;
        st.ramp = null;
        st.setpoints[d.name] = +e.target.value;
        st.outputs = predict(st.id, st.setpoints, st.disturbance);
        renderLive();
      });
      input.addEventListener("change", () => {
        const st = plantState();
        logEvent(st, "info", `Operator set ${d.label.toLowerCase()} to ${fmt(st.setpoints[d.name] * (d.scale || 1), d.digits)} ${d.unit}`);
      });
    }

    $("new-default").addEventListener("click", () => { const st = plantState(); loadDefault(st); st.outputs = predict(st.id, st.setpoints, st.disturbance); renderLive(); });
    $("back-default").addEventListener("click", () => {
      const st = plantState();
      if (!st.baseline) return;
      if (st.mode === "auto") setMode(st, "manual");
      st.ramp = { from: { ...st.setpoints }, to: decisionValues(st.id, st.baseline.x), start: performance.now(), duration: reduceMotion ? 1 : RAMP_MS, label: "the default operation" };
      st.proposal = false;
      logEvent(st, "info", "Operator returned the set-points to the default operation");
    });
    $("objective").addEventListener("change", (e) => {
      const st = plantState();
      st.objective = e.target.value;
      const o = DEFS[st.id].objectives.find((x) => x.id === st.objective);
      logEvent(st, "opt", `Objective: ${o.label.toLowerCase()}`);
      renderLive();
    });
    for (const l of s.limits) {
      $(`c-on-${l.key}`).addEventListener("change", (e) => {
        const st = plantState(), lim = st.limits.find((x) => x.key === l.key);
        lim.enabled = e.target.checked;
        const meta = limitMeta(st.id, lim);
        limitsChanged(st, `Operator ${lim.enabled ? "enforces" : "stopped enforcing"} the ${asPhrase(meta.label)} limit`);
      });
      $(`c-bound-${l.key}`).addEventListener("change", (e) => {
        const st = plantState(), lim = st.limits.find((x) => x.key === l.key);
        const [lo, hi, step] = BOUND_RANGE[lim.key];
        const value = parseFloat(e.target.value);
        if (!Number.isFinite(value)) { e.target.value = lim.bound; return; }
        const bound = +(Math.round(clamp(value, lo, hi) / step) * step).toFixed(6);
        e.target.value = bound;
        if (bound === lim.bound) return;
        lim.bound = bound;
        const meta = limitMeta(st.id, lim);
        limitsChanged(st, `Operator set the ${asPhrase(meta.label)} limit to ${lim.upper ? "≤" : "≥"} ${fmtBound(bound)} ${unitOf(meta)} (permit ${fmtBound(lim.permit)})`);
      });
    }
    $("c-reset").addEventListener("click", () => {
      const st = plantState();
      if (isPermit(st)) return;
      st.limits = permitLimits(st.id);
      limitsChanged(st, "Operator reset the limits to the permit");
    });

    $("optimize").addEventListener("click", () => { const st = plantState(); propose(st); renderLive(); });
    $("demo").addEventListener("click", () => (demo.timers.length ? stopDemo(true) : runDemo()));
    $("auto").addEventListener("change", (e) => { const st = plantState(); setMode(st, e.target.checked ? "auto" : "manual"); renderLive(); });
  }

  function updateControls() {
    const s = plantState(), def = DEFS[s.id];
    const dist = $("dist");
    if (document.activeElement !== dist) dist.value = s.disturbance;
    $("dist-v").textContent = fmt(s.disturbance, def.disturbance.digits);
    $("pattern-on").setAttribute("aria-pressed", String(s.pattern));
    $("pattern-off").setAttribute("aria-pressed", String(!s.pattern));
    for (const v of [1, 10, 30]) $(`speed-${v}`).setAttribute("aria-pressed", String(app.speed === v));
    if (RAIN[s.id]) {
      $("weather-storm").setAttribute("aria-pressed", String(s.storm));
      $("weather-dry").setAttribute("aria-pressed", String(!s.storm));
      const note = s.rain > 0
        ? `Rain ${fmt(s.rain, 0)} m³/d: ${fmt(s.disturbance + s.rain, 0)} m³/d reach the plant, diluted`
        : s.storm ? "Rain starting" : "";
      if ($("rain-note").textContent !== note) $("rain-note").textContent = note;
    }

    const auto = s.mode === "auto";
    const opt = (auto || s.proposal) ? optimumFor(s.id, s.objective, s.disturbance) : null;
    $("sp-owner").textContent = auto ? "OpenNN (AUTO)" : s.ramp ? "Ramping" : "Operator";
    for (const d of def.decisions) {
      const input = $(`sp-${d.name}`);
      input.disabled = auto;
      if (document.activeElement !== input || auto || s.ramp) input.value = s.setpoints[d.name];
      $(`sp-${d.name}-v`).textContent = fmt(s.setpoints[d.name] * (d.scale || 1), d.digits);
      const marker = $(`tg-${d.name}`);
      if (usable(opt)) {
        marker.hidden = false;
        marker.style.left = `${(100 * (opt.x[d.name] - d.min)) / (d.max - d.min)}%`;
      } else marker.hidden = true;
    }
    $("objective").value = s.objective;
    $("objective").disabled = def.objectives.length < 2;
    $("optimize").disabled = auto || !!s.ramp;
    $("auto").checked = auto;
    $("back-default").disabled = !s.baseline;
    updateConstraints(s);
    renderProposal();
  }

  function updateConstraints(s) {
    for (const l of s.limits) {
      const on = $(`c-on-${l.key}`), input = $(`c-bound-${l.key}`);
      if (!on || !input) continue;
      on.checked = l.enabled;
      if (document.activeElement !== input && +input.value !== l.bound) input.value = l.bound;
      input.disabled = !l.enabled;
      const row = input.closest(".c-row");
      row.classList.toggle("is-custom", l.enabled && l.bound !== l.permit);
      row.classList.toggle("is-off", !l.enabled);
      const meta = limitMeta(s.id, l);
      const title = l.kind === "output"
        ? `Permit ${fmtBound(l.permit)} ${meta.unit}. The optimizer keeps ${fmtBound(marginFor(s.id, l.key, l.bound))} ${meta.unit} of safety margin (the network's validation error near this bound).`
        : `Permit ${fmtBound(l.permit)} ${meta.unit} (the pump's rating). Set-points are exact, so there is no safety margin.`;
      if (row.title !== title) row.title = title;
    }
    const permit = isPermit(s);
    $("c-reset").disabled = permit;
    const mode = permit ? "Permit limits: optima precomputed by OpenNN and checked in WaterTAP."
      : optimizing(s) ? "Your limits: optimizing in this browser…"
      : "Your limits: optima computed in this browser on the OpenNN network.";
    if ($("c-mode").textContent !== mode) $("c-mode").textContent = mode;
  }

  // The optimizer card has two phases: the proposal (what OpenNN suggests and predicts, and what
  // WaterTAP gives at those set-points), then the result once applied (before and after, both in
  // WaterTAP, next to what OpenNN predicted).
  function renderProposal() {
    const s = plantState();
    const box = $("proposal");
    const html = s.proposal && s.mode !== "auto" ? proposalCard(s) : s.result ? resultCard(s) : "";
    if (box.dataset.html !== html) { box.innerHTML = html; box.dataset.html = html; }
  }

  const unitOf = (d) => (d.unit.startsWith("%") ? "%" : d.unit);

  // A limit annotation for an output row, and the alarm icon when WaterTAP exceeds it.
  const fmtBound = (v) => fmt(v, Number.isInteger(v) ? 0 : Math.abs(v) < 10 ? 2 : 1);
  function limitNote(id, key) {
    const l = app.plants[id].limits.find((x) => x.key === key && x.kind === "output");
    if (!l) return "";
    if (!l.enabled) return " · not enforced";
    return `${l.upper ? " · max " : " · min "}${fmtBound(l.bound)}`;
  }
  function simCell(id, key, y, setpoints) {
    if (!y) return "…";
    const meta = DEFS[id].outputs[key];
    const row = limitRows(id, y, setpoints).find((l) => l.key === key);
    const icon = row && row.status === "alarm" ? `<span class="l-state alarm" title="Limit exceeded">${ICON.alarm}<span class="sr">Limit exceeded</span></span> ` : "";
    return `${icon}${fmt(y[key], meta.digits)}`;
  }

  // One sentence on what WaterTAP says about a point a card shows; `at` is "at the new set-points".
  function simVerdict(id, x, setpoints, at) {
    const key = pointKey(id, x);
    const r = SIM.results.get(key);
    if (isSolved(r)) {
      const failed = limitsMet(id, r.outputs, setpoints).failed;
      const how = (r.source === "stored" ? "stored solution" : `solved in ${fmt(r.seconds, 1)} s`)
        + (r.status === "washout" ? ", nitrifiers washed out" : "");
      return failed.length
        ? `${stateChip("alarm", `${failed.length} limit${failed.length > 1 ? "s" : ""} exceeded`)} in WaterTAP ${esc(at)} (${how}): ${esc(failed.map((l) => l.label).join(", "))}.`
        : `${stateChip("ok", "Every limit met")} in WaterTAP ${esc(at)} (${how}).`;
    }
    if (r && r.status === "failed") return `${stateChip("warn", "Not converged")} WaterTAP did not converge ${esc(at)}.`;
    if (SIM.pending.has(key)) return `${simMark(true)}WaterTAP is solving the plant ${esc(at)}…`;
    if (simReady(id)) return `${simMark(true)}WaterTAP solves the plant ${esc(at)} next.`;
    if (SIM.online) return `${simMark()}WaterTAP is starting; it solves the plant ${esc(at)} when ready.`;
    return `${simMark()}No WaterTAP solution ${esc(at)}: the simulator is not running. Start <b>start_simulator.bat</b> to solve it.`;
  }

  function proposalCard(s) {
    const def = DEFS[s.id];
    const opt = optimumFor(s.id, s.objective, s.disturbance);
    const objective = def.objectives.find((o) => o.id === s.objective);
    const discard = `<div class="row-wrap"><button type="button" class="btn ghost" id="discard">Discard</button></div>`;
    if (!opt && !isPermit(s))
      return `<div class="proposal"><div class="proposal-head"><h3>OpenNN proposal · ${esc(objective.label)} · your limits</h3></div>
        <p class="check-line">${simMark(true)}Optimizing for your limits in this browser, on the OpenNN network…</p>${discard}</div>`;
    if (!opt) return `<div class="proposal"><p class="hint">No stored optimum for this condition.</p>${discard}</div>`;
    if (!usable(opt)) {
      // The closest the search came: the limits it still breaks, by the network.
      const missed = limitRows(s.id, opt.y, decisionValues(s.id, opt.x))
        .filter((l) => l.enabled && (l.upper ? l.value > l.bound - l.margin : l.value < l.bound + l.margin));
      return `<div class="proposal"><div class="proposal-head"><h3>OpenNN proposal · ${esc(objective.label)} · your limits</h3></div>
        <p class="check-line">${stateChip("warn", "No feasible set-points")} No set-points within the range the network was trained on meet every limit you set with its safety margin at this ${esc(def.disturbance.label.toLowerCase())}.
        ${missed.length ? `Closest: ${esc(missed.map((l) => `${asPhrase(l.label)} ${fmt(l.value, l.digits)} ${l.unit} (limit ${fmtBound(l.bound)}, margin ${fmtBound(l.margin)})`).join(", "))}.` : ""} Relax a limit or switch one off.</p>${discard}</div>`;
    }
    const key = objective.output, main = def.outputs[key];
    const target = decisionValues(s.id, opt.x);
    const now = s.outputs;
    const then = predict(s.id, target, s.disturbance);
    const change = (100 * (then[key] - now[key])) / now[key];
    const proposedX = withCondition(s, target);
    const check = SIM.results.get(pointKey(s.id, proposedX));
    const truth = isSolved(check) ? check.outputs : null;
    const here = simFor(s);
    const nowTruth = here.current && isSolved(here.result) ? here.result.outputs : null;
    let simLead = "";
    if (truth) {
      const vsNow = nowTruth ? ` (${signed((100 * (truth[key] - nowTruth[key])) / nowTruth[key], 1)} % vs now in WaterTAP)` : "";
      simLead = `<div class="lead sim">${simMark()}WaterTAP at the proposed set-points <b>${fmt(truth[key], main.digits)}</b> ${esc(main.unit)}${vsNow}</div>`;
    }
    return `
      <div class="proposal">
        <div class="proposal-head">
          <h3>OpenNN proposal · ${esc(objective.label)}${opt.custom ? " · your limits" : ""}</h3>
          <div class="leads">
            <div class="lead">${esc(main.label)} predicted by OpenNN <b>${fmt(now[key], main.digits)} → ${fmt(then[key], main.digits)}</b> ${esc(main.unit)} <b>(${signed(change, 1)} %)</b></div>
            ${simLead}
          </div>
        </div>
        <div class="proposal-grid">
          <div class="table-scroll t-sp"><table>
            <tr><th>Set-point</th><th class="r">Now</th><th class="r">Proposed</th></tr>
            ${def.decisions.map((d) => `<tr><td class="name">${esc(d.label)} <span class="note">${esc(unitOf(d))}</span></td><td>${fmt(s.setpoints[d.name] * (d.scale || 1), d.digits)}</td><td class="to">${fmt(target[d.name] * (d.scale || 1), d.digits)}</td></tr>`).join("")}
          </table></div>
          <div class="table-scroll t-out"><table>
            <tr class="groups"><th></th><th class="r">Now</th><th class="r group" colspan="2">Proposed</th></tr>
            <tr><th>Output</th><th class="r">OpenNN</th><th class="r">OpenNN</th><th class="r">${simMark()}WaterTAP</th></tr>
            ${def.checkRows.map((k) => { const m = def.outputs[k]; return `<tr><td class="name">${esc(m.label)} <span class="note">${esc(m.unit)}${esc(limitNote(s.id, k))}</span></td><td>${fmt(now[k], m.digits)}</td><td class="to">${fmt(then[k], m.digits)}</td><td>${simCell(s.id, k, truth, target)}</td></tr>`; }).join("")}
          </table></div>
        </div>
        <p class="check-line">${simVerdict(s.id, proposedX, target, "at the proposed set-points")}</p>
        <p class="hint">${opt.custom
          ? `Optimized for your limits in this browser, on the OpenNN network (${fmt(opt.ms, 0)} ms): the problem OpenNN response optimization solves for the permit, with each limit kept with a safety margin equal to the network's validation error near it.`
          : "Precomputed by OpenNN response optimization for the permit limits, keeping each limit with a safety margin equal to the network's validation error."}</p>
        <div class="row-wrap">
          <button type="button" class="btn primary" id="apply">Apply set-points</button>
          <button type="button" class="btn ghost" id="discard">Discard</button>
        </div>
      </div>`;
  }

  function resultCard(s) {
    const def = DEFS[s.id], r = s.result;
    const objective = def.objectives.find((o) => o.id === r.objective);
    const key = objective.output, main = def.outputs[key];
    const before = SIM.results.get(pointKey(s.id, r.before)), after = SIM.results.get(pointKey(s.id, r.after));
    const b = isSolved(before) ? before.outputs : null, a = isSolved(after) ? after.outputs : null;
    const afterSp = decisionValues(s.id, r.after), beforeSp = decisionValues(s.id, r.before);
    const predicted = (100 * (r.afterY[key] - r.beforeY[key])) / r.beforeY[key];
    const lead = b && a
      ? `<div class="lead sim">${simMark()}${esc(main.label)} in WaterTAP <b>${fmt(b[key], main.digits)} → ${fmt(a[key], main.digits)}</b> ${esc(main.unit)} <b>(${signed((100 * (a[key] - b[key])) / b[key], 1)} %)</b></div>
         <div class="lead">OpenNN predicted <b>${signed(predicted, 1)} %</b></div>`
      : `<div class="lead">${esc(main.label)} predicted by OpenNN <b>${fmt(r.beforeY[key], main.digits)} → ${fmt(r.afterY[key], main.digits)}</b> ${esc(main.unit)} <b>(${signed(predicted, 1)} %)</b></div>`;
    const dist = def.disturbance;
    return `
      <div class="proposal result">
        <div class="proposal-head">
          <h3>Optimization result · ${esc(objective.label)}</h3>
          <div class="leads">${lead}</div>
        </div>
        <div class="table-scroll"><table>
          <tr class="groups"><th></th><th class="r group" colspan="2">${simMark()}WaterTAP</th><th class="r">OpenNN</th></tr>
          <tr><th>Output</th><th class="r">Before</th><th class="r">After</th><th class="r">After, predicted</th></tr>
          ${def.checkRows.map((k) => { const m = def.outputs[k]; return `<tr><td class="name">${esc(m.label)} <span class="note">${esc(m.unit)}${esc(limitNote(s.id, k))}</span></td><td>${simCell(s.id, k, b, beforeSp)}</td><td class="sim-after">${simCell(s.id, k, a, afterSp)}</td><td class="to">${fmt(r.afterY[k], m.digits)}</td></tr>`; }).join("")}
        </table></div>
        <p class="check-line">${simVerdict(s.id, r.after, afterSp, "at the new set-points")}</p>
        ${b ? "" : `<p class="check-line">${simVerdict(s.id, r.before, beforeSp, "at the previous set-points")}</p>`}
        <p class="hint">Both operating points at ${esc(dist.label.toLowerCase())} ${fmt(r.before[dist.name], dist.digits)} ${esc(dist.unit)}, solved in the WaterTAP flowsheet the network was trained on.</p>
        <div class="row-wrap"><button type="button" class="btn ghost" id="dismiss">Dismiss</button></div>
      </div>`;
  }

  // ------------------------------------------------------------------ KPIs, limits, check

  function renderKpis() {
    const s = plantState(), def = DEFS[s.id];
    const y = s.outputs;
    const base = s.baseline ? predict(s.id, decisionValues(s.id, s.baseline.x), s.disturbance) : null;
    const limits = limitList(s, y).filter((l) => l.enabled);
    const alarms = limits.filter((l) => l.status === "alarm").length;
    const warns = limits.filter((l) => l.status === "warn").length;
    const sim = simFor(s);
    const simLine = (key, meta) => {
      if (sim.current && isSolved(sim.result)) {
        const truth = sim.result.outputs[key];
        const gap = (100 * (y[key] - truth)) / Math.abs(truth);
        return `<div class="k-sim">${simMark()}WaterTAP <b>${fmt(truth, meta.digits)}</b> ${esc(meta.unit)} · OpenNN ${signed(gap, 1)} %</div>`;
      }
      if (sim.state === "failed") return `<div class="k-sim">${simMark()}WaterTAP did not converge here</div>`;
      if (sim.state === "solving") return `<div class="k-sim">${simMark(true)}WaterTAP solving…</div>`;
      if (sim.state === "waiting") return `<div class="k-sim">${simMark()}WaterTAP waits for steady set-points</div>`;
      if (sim.state === "warming") return `<div class="k-sim">${simMark()}WaterTAP starting…</div>`;
      return "";
    };
    let html = "";
    for (const k of def.kpis) {
      const meta = def.outputs[k.output];
      let delta = "", note = "";
      if (base && k.better) {
        const change = (100 * (y[k.output] - base[k.output])) / base[k.output];
        const good = k.better === "lower" ? change < -0.05 : change > 0.05;
        const bad = k.better === "lower" ? change > 0.05 : change < -0.05;
        delta = `<div class="k-delta ${good ? "better" : bad ? "worse" : ""}">${signed(change, 1)} % vs default operation</div>`;
        const diff = y[k.output] - base[k.output];
        if (k.annual === "energy" && Math.abs(diff) > 1e-6)
          note = `${diff < 0 ? "Saves" : "Uses"} ≈ ${fmt(Math.abs(diff) * (s.disturbance + s.rain) * 365 / 1000, 0)} MWh/year ${diff < 0 ? "" : "more "}at this flow`;
        if (k.annual === "cost" && Math.abs(diff) > 1e-7)
          note = `${diff < 0 ? "Saves" : "Costs"} ≈ $${fmt(Math.abs(diff) * (s.disturbance + s.rain) * 365, 0)} per year ${diff < 0 ? "" : "more "}at this flow`;
        if (k.annual === "biogas" && Math.abs(diff) > 0.5)
          note = `${diff > 0 ? "+" : "−"}${fmt(Math.abs(diff) * 365 / 1000, 0)} thousand m³ of biogas per year`;
        if (k.annual === "per1000" && Math.abs(diff) > 1e-7)
          note = `${diff < 0 ? "−" : "+"}$${fmt(Math.abs(diff) * 1000, 2)} per 1,000 m³ of permeate`;
      } else if (base) {
        delta = `<div class="k-delta">${signed(y[k.output] - base[k.output], meta.digits)} ${esc(meta.unit)} vs default</div>`;
      }
      html += `<div class="kpi"><div class="k-label">${esc(meta.label)} <span class="k-source">OpenNN</span></div>
        <div class="k-value">${fmt(y[k.output], meta.digits)}<small>${esc(meta.unit)}</small></div>${delta}<div class="k-note">${esc(note)}</div>${simLine(k.output, meta)}</div>`;
    }
    const status = alarms ? "alarm" : warns ? "warn" : "ok";
    const statusText = alarms ? `${alarms} limit${alarms > 1 ? "s" : ""} exceeded` : warns ? `${warns} inside the safety margin` : "All limits met";
    html += `<div class="kpi compliance"><div class="k-label">Compliance</div>
      <div class="k-value">${limits.length - alarms} / ${limits.length}<small>limits met</small></div>
      <div>${stateChip(status, statusText)}</div>
      <div class="k-note">${s.mode === "auto" ? "AUTO: following the OpenNN optimum" : s.ramp ? "Ramping to new set-points" : "Operator set-points"}</div></div>`;
    $("kpis").innerHTML = html;
  }

  function renderLimits() {
    const s = plantState();
    const title = `${DEFS[s.id].limitsTitle}${isPermit(s) ? "" : " · your limits"}`;
    if ($("limits-title").textContent !== title) $("limits-title").textContent = title;
    $("limits-note").innerHTML = '<span class="key-tri">▲</span> OpenNN · <span class="key-tri sim">▼</span> WaterTAP · shaded: safety margin';
    const rows = limitList(s, s.outputs);
    const sim = simFor(s);
    const simY = sim.current && sim.result.outputs ? sim.result.outputs : null;
    let html = "";
    for (const l of rows) {
      const W = 300;
      let lo = 0, hi;
      if (l.upper) hi = Math.max(l.bound * 1.5, l.value * 1.08);
      else hi = Math.max(l.bound * 3, l.value * 1.15);
      if (l.key === "pressure") { lo = 30; hi = 90; }
      const X = (v) => (W * (clamp(v, lo, hi) - lo)) / (hi - lo);
      const xb = X(l.bound);
      const zones = !l.enabled ? "" : l.upper
        ? `<rect class="l-margin" x="${X(l.bound - l.margin).toFixed(1)}" y="10" width="${(xb - X(l.bound - l.margin)).toFixed(1)}" height="9"/><rect class="l-over" x="${xb.toFixed(1)}" y="10" width="${(W - xb).toFixed(1)}" height="9"/>`
        : `<rect class="l-over" x="0" y="10" width="${xb.toFixed(1)}" height="9"/><rect class="l-margin" x="${xb.toFixed(1)}" y="10" width="${(X(l.bound + l.margin) - xb).toFixed(1)}" height="9"/>`;
      // The permit's value, when the operator moved the limit away from it.
      const permit = l.enabled && l.bound !== l.permit
        ? `<line class="l-permit" x1="${X(l.permit).toFixed(1)}" y1="7" x2="${X(l.permit).toFixed(1)}" y2="22"><title>Permit ${fmtBound(l.permit)} ${esc(l.unit)}</title></line>` : "";
      const xv = X(l.value);
      let pointer = `<path class="l-pointer ${l.status === "alarm" ? "is-alarm" : l.status === "warn" ? "is-warn" : ""}" d="M${xv.toFixed(1)} 20 l-5 7 h10 z"/><line x1="${xv.toFixed(1)}" y1="8" x2="${xv.toFixed(1)}" y2="21" stroke="currentColor" stroke-width="2"/>`;
      const simValue = simY && DEFS[s.id].outputs[l.key] ? simY[l.key] : NaN;
      if (Number.isFinite(simValue)) {
        const xs = X(simValue);
        pointer += `<path class="l-sim" d="M${xs.toFixed(1)} 9 l-5 -7 h10 z"/>`;
      }
      const flagged = l.status === "warn" || l.status === "alarm";
      const mark = flagged ? `<span class="l-state ${l.status}" title="${STATE_TEXT[l.status]}">${ICON[l.status]}<span class="sr">${STATE_TEXT[l.status]}</span></span>` : "";
      const boundText = l.enabled ? `${l.upper ? "max" : "min"} ${fmt(l.bound, l.digits)}${l.bound !== l.permit ? " (yours)" : ""}` : "not enforced";
      html += `<div class="limit${l.enabled ? "" : " is-off"}">
        <span class="l-name">${mark}${esc(l.label)}</span>
        <span class="l-value">${fmt(l.value, l.digits)} <small>${esc(l.unit)} · ${boundText}</small></span>
        <svg viewBox="0 0 ${W} 28" preserveAspectRatio="none" role="img" aria-label="${esc(`${l.label}: OpenNN ${fmt(l.value, l.digits)}${Number.isFinite(simValue) ? `, WaterTAP ${fmt(simValue, l.digits)}` : ""} ${l.unit}, ${l.enabled ? `${l.upper ? "maximum" : "minimum"} ${fmt(l.bound, l.digits)}` : "limit not enforced"}`)}">
          <rect class="l-track" x="0.5" y="9.5" width="${W - 1}" height="10" rx="2"/>${zones}${permit}<line class="l-limit" x1="${xb.toFixed(1)}" y1="5" x2="${xb.toFixed(1)}" y2="24"/>${pointer}
        </svg></div>`;
    }
    $("limits").innerHTML = html;
  }

  // The stored WaterTAP checks of a network: the default operations (dry-weather network) and its optima.
  function verificationSentence(facts) {
    const n = facts.optima_unsolved;
    const unsolved = n === 1
      ? " WaterTAP did not converge at the remaining one, so it has no simulator check."
      : n > 1 ? ` WaterTAP did not converge at the remaining ${n}, so they have no simulator check.` : "";
    const checked = facts.defaults === undefined
      ? `${facts.optima_feasible} of the ${facts.optima} stored storm optima`
      : `all ${facts.defaults} default operations and ${facts.optima_feasible} of the ${facts.optima} stored optima`;
    return `In WaterTAP, ${checked} meet every limit.${unsolved}`;
  }

  const twoFigures = (v) => { const p = Math.pow(10, Math.floor(Math.log10(v)) - 1); return Math.round(v / p) * p; };

  // OpenNN and WaterTAP side by side at the current operating point.
  function renderCheck() {
    const s = plantState(), def = DEFS[s.id];
    const sim = simFor(s);
    const advisory = modelAdvisory(s, s.outputs);
    const facts = net(s.id, s.rain).facts, storm = isStorm(s.id, s.rain);
    const equations = SIM.status && SIM.status.equations ? SIM.status.equations[s.id] : null;
    const r = sim.result;
    const truth = sim.current && isSolved(r) ? r.outputs : null;
    let html = "";

    if (sim.state === "solved") {
      const failed = limitsMet(s.id, truth, s.setpoints).failed;
      const how = r.source === "stored" ? "Stored WaterTAP solution of this operating point" : `WaterTAP solved this operating point in ${fmt(r.seconds, 1)} s`;
      html += `<p>${failed.length ? stateChip("alarm", `${failed.length} limit${failed.length > 1 ? "s" : ""} exceeded in WaterTAP`) : stateChip("ok", "Every limit met in WaterTAP")} ${esc(how)}${r.status === "washout" ? " (the nitrifiers wash out here)" : ""}.</p>`;
    } else if (sim.state === "failed") {
      html += `<p>${stateChip("warn", "Not converged")} WaterTAP did not converge at this operating point. The network still answers.</p>`;
    } else if (sim.state === "solving") {
      html += `<p>${simMark(true)}WaterTAP is solving this operating point${equations ? ` (${fmt(equations, 0)} equations)` : ""}. The network answered at once.</p>`;
    } else if (sim.state === "waiting") {
      html += `<p>${simMark()}WaterTAP solves the operating point once the set-points hold still for half a second.</p>`;
    } else if (sim.state === "warming") {
      html += `<p>${simMark(true)}The WaterTAP models are starting; the wastewater model takes about a minute.</p>`;
    } else if (!launching() && canLaunch) {
      html += `<p>${simMark()}The WaterTAP simulator is not running. ${START_BUTTON} to solve every operating point next to the network. Without it, only the default operations and the stored optima show WaterTAP solutions.</p>`;
      const where = pageFolders();
      if (where) html += `<p class="note">First time on this computer? Run <b>setup.bat</b> in <code>${esc(where.project)}</code> once.</p>`;
    } else if (!launching()) {
      html += `<p>${simMark()}The WaterTAP simulator is not running. Without it, only the default operations and the stored optima show WaterTAP solutions.</p><p class="note">${launchHelp()}</p>`;
    }
    // After the Start button, whatever the operating point shows.
    if (launching()) {
      html += `<p>${simMark(true)}Starting the WaterTAP simulator on this computer.${launchUnanswered() ? "" : " If the browser asks, allow it to open the simulator."}</p>`;
      if (launchUnanswered()) html += `<p class="note">Nothing started? ${launchHelp()}</p>`;
    }

    if (sim.state !== "offline" && sim.state !== "warming") {
      html += `<div class="table-scroll"><table><tr><th>Output</th><th class="r">OpenNN</th><th class="r">${simMark()}WaterTAP</th><th class="r">Difference</th></tr>`;
      for (const key of def.checkRows) {
        const meta = def.outputs[key];
        const nn = s.outputs[key];
        const diff = truth ? signed(nn - truth[key], meta.digits) : "";
        html += `<tr><td>${esc(meta.label)} <span class="note">${esc(meta.unit)}</span></td><td class="r">${fmt(nn, meta.digits)}</td><td class="r">${truth ? simCell(s.id, key, truth, s.setpoints) : sim.state === "failed" ? "–" : "…"}</td><td class="r diff">${diff}</td></tr>`;
      }
      html += "</table></div>";
    }

    // How long each takes: the reason for the network.
    const micros = app.networkMicros[s.id];
    if (micros) {
      const seconds = truth && r.source !== "stored" ? r.seconds : null;
      let speed = `OpenNN: ${fmt(micros, micros < 10 ? 1 : 0)} µs per prediction in this browser.`;
      if (equations) speed += ` WaterTAP: ${fmt(equations, 0)} equations`
        + (seconds ? `, ${fmt(seconds, 1)} s for this point, about ${fmt(twoFigures((seconds * 1e6) / micros), 0)} times longer.` : ".");
      html += `<p class="note speed">${speed}</p>`;
    }
    html += `<p class="note">${storm ? "It is raining, so the storm network answers. It" : "The network"} was trained on ${fmt(facts.rows, 0)} WaterTAP simulations; on held-out simulations its R² is ${facts.r2_text}.${sim.state === "offline" ? ` ${verificationSentence(facts)}` : ""}</p>`;
    if (advisory) html += `<p>${stateChip("warn", "Model advisory")} ${esc(advisory)}</p>`;
    if ($("check").dataset.html !== html) { $("check").innerHTML = html; $("check").dataset.html = html; }
  }

  function renderBanner() {
    const s = plantState();
    const limits = limitList(s, s.outputs).filter((l) => l.enabled);
    const alarms = limits.filter((l) => l.status === "alarm");
    const warns = limits.filter((l) => l.status === "warn");
    const advisory = modelAdvisory(s, s.outputs);
    const banner = $("alarm-banner");
    banner.classList.toggle("is-alarm", alarms.length > 0);
    banner.classList.toggle("is-warn", !alarms.length && (warns.length > 0 || !!advisory));
    let html;
    if (alarms.length)
      html = `${ICON.alarm}<strong>Alarm</strong> ${alarms.map((l) => `${esc(l.label)} ${fmt(l.value, l.digits)} ${esc(l.unit)} (${l.upper ? "max" : "min"} ${fmt(l.bound, l.digits)})`).join(" · ")}`;
    else if (warns.length)
      html = `${ICON.warn}<strong>Near limit</strong> ${warns.map((l) => `${esc(l.label)} ${fmt(l.value, l.digits)} ${esc(l.unit)}`).join(" · ")} inside the safety margin`;
    else if (advisory)
      html = `${ICON.warn}<strong>Model advisory</strong> Outside the region the network knows well`;
    else
      html = `${ICON.ok}<strong>No active alarms</strong> All ${limits.length} limits met`;
    if (banner.dataset.html !== html) { banner.innerHTML = html; banner.dataset.html = html; }
    const ac = $("alarm-count"), wc = $("warn-count");
    ac.textContent = `${alarms.length} alarm${alarms.length === 1 ? "" : "s"}`;
    ac.className = `chip${alarms.length ? " is-alarm" : ""}`;
    wc.textContent = `${warns.length} near limit`;
    wc.className = `chip${warns.length ? " is-warn" : ""}`;
    const pill = $("mode-pill");
    pill.textContent = s.mode === "auto" ? "Auto · OpenNN" : s.proposal ? "Proposal" : s.ramp ? "Ramping" : "Manual";
    pill.className = `pill${s.mode === "auto" || s.proposal || s.ramp ? " auto" : ""}`;
    $("clock").textContent = clockText(s.t);

    // The simulator service, as the operator would see a connection to another system.
    const chip = $("sim-chip"), st = SIM.status;
    const solving = [...SIM.pending].some((k) => k.startsWith(`${s.id}|`)) || !!(st && st.busy && st.busy[s.id]);
    let text, title, busy = false;
    if (!SIM.online && launching()) {
      text = "WaterTAP starting";
      title = "Waiting for the WaterTAP simulator on this computer to answer";
      busy = true;
    } else if (!SIM.online) {
      text = "WaterTAP offline";
      title = canLaunch
        ? "The WaterTAP simulator is not running: Start WaterTAP solves operating points next to the network. Stored solutions are still shown."
        : "The WaterTAP simulator is not running (start_demo.sh starts it). Stored solutions are still shown.";
    } else if (!simReady(s.id)) {
      const failed = st && st.error && st.error[s.id];
      text = failed ? "WaterTAP error" : "WaterTAP starting";
      title = failed ? `The WaterTAP model failed to start: ${st.error[s.id]}` : "The WaterTAP model is being built";
      busy = !failed;
    } else {
      text = solving ? "WaterTAP solving" : "WaterTAP live";
      busy = solving;
      title = `WaterTAP simulator running on this computer: ${fmt(SIM.live, 0)} operating point${SIM.live === 1 ? "" : "s"} solved for this page`;
    }
    const chipHtml = `${simMark(busy)}${text}`;
    if (chip.dataset.html !== chipHtml) { chip.innerHTML = chipHtml; chip.dataset.html = chipHtml; }
    chip.className = `chip sim-chip${SIM.online && simReady(s.id) ? " is-live" : ""}`;
    if (chip.title !== title) chip.title = title;
    const start = $("sim-start"), showStart = canLaunch && !SIM.online && !launching();
    if (start.hidden === showStart) start.hidden = !showStart;
  }

  function renderSource() {
    const s = plantState();
    $("src-nn").setAttribute("aria-pressed", String(app.source === "nn"));
    $("src-sim").setAttribute("aria-pressed", String(app.source === "sim"));
    let note = "Values: OpenNN predictions, instant";
    if (app.source === "sim") {
      const sim = simFor(s);
      note = sim.current && isSolved(sim.result) ? "Values: WaterTAP solution of this operating point"
        : sim.state === "failed" ? "WaterTAP did not converge at this operating point"
        : isSolved(sim.result) ? "Values: WaterTAP at the previous operating point (dimmed) while it solves this one"
        : sim.state === "offline" ? "WaterTAP is not running: no solution for this operating point"
        : "WaterTAP is solving this operating point";
    }
    const el = $("process-note");
    if (el.textContent !== note) el.textContent = note;

    // On the trends: what WaterTAP is working on, so a dot that has not arrived reads as pending.
    const sim = simFor(s), st = SIM.status;
    const ahead = st && st.queued && st.busy ? Math.max(0, (st.busy[s.id] || 0) + (st.queued[s.id] || 0) - (sim.state === "solving" ? 1 : 0)) : 0;
    let trend = "";
    if (sim.state === "solving") trend = `${simMark(true)}WaterTAP solving the current point${ahead ? `, ${ahead} ahead` : ""}`;
    else if (ahead && SIM.online) trend = `${simMark(true)}WaterTAP solving ${ahead} point${ahead > 1 ? "s" : ""} ahead`;
    const box = $("trend-sim");
    if (box.dataset.html !== trend) { box.innerHTML = trend; box.dataset.html = trend; }
  }

  function renderEvents() {
    const s = plantState();
    const kindClass = { alarm: "e-alarm", normal: "e-normal", opt: "e-opt", sim: "e-sim", info: "" };
    const kindText = { alarm: "Alarm", normal: "Normal", opt: "OpenNN", sim: "WaterTAP", info: "" };
    $("events").innerHTML = s.events.slice(0, 40).map((e) =>
      `<li><time>${clockText(e.t)}</time><span>${kindText[e.kind] ? `<span class="${kindClass[e.kind]}">${kindText[e.kind]}</span> ` : ""}${esc(e.text)}</span></li>`).join("");
  }

  // ------------------------------------------------------------------ trends

  function niceTicks(lo, hi, count = 4) {
    const span = hi - lo || Math.abs(hi) || 1;
    const raw = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= raw) || 10 * mag;
    const first = Math.ceil(lo / step) * step;
    const ticks = [];
    for (let v = first; v <= hi + step * 1e-6; v += step) ticks.push(+v.toFixed(10));
    return { ticks, step };
  }

  function buildCharts() {
    const s = plantState();
    $("trend-grid").innerHTML = DEFS[s.id].trends.map((c, i) => `
      <div class="chart" id="chart-${i}">
        <div class="chart-title"><b>${esc(c.label)}</b><span class="num" id="chart-${i}-now"></span></div>
        <svg id="chart-${i}-svg" role="img" aria-label="${esc(c.label)} trend"></svg>
        <div class="tooltip" id="chart-${i}-tip" hidden></div>
      </div>`).join("");
    DEFS[s.id].trends.forEach((c, i) => {
      const svg = $(`chart-${i}-svg`);
      svg.addEventListener("pointermove", (e) => { app.hover[i] = e.clientX - svg.getBoundingClientRect().left; drawChart(i); });
      svg.addEventListener("pointerleave", () => { delete app.hover[i]; drawChart(i); });
    });
    renderCharts();
  }

  function renderCharts() {
    DEFS[app.active].trends.forEach((_, i) => drawChart(i));
    renderTrendWhy();
  }

  // In AUTO, where the optimizer keeps an output with a limit: the limit less its safety margin.
  function autoCeiling(s, key) {
    if (s.mode !== "auto") return undefined;
    const l = s.limits.find((x) => x.key === key && x.enabled && x.kind === "output");
    if (!l) return undefined;
    const m = marginFor(s.id, l.key, l.bound);
    return l.upper ? l.bound - m : l.bound + m;
  }

  // Why a trend stays flat in AUTO: the optimizer holds the output on its ceiling, because that
  // limit is what stops it going further, and moves the set-points with the condition instead.
  function renderTrendWhy() {
    const s = plantState(), def = DEFS[s.id], box = $("trend-why");
    let text = "";
    for (const c of def.trends) {
      const ceiling = autoCeiling(s, c.key), value = s.outputs[c.key];
      if (ceiling === undefined || !Number.isFinite(value)) continue;
      if (Math.abs(value - ceiling) > 0.03 * Math.abs(ceiling)) continue;
      const l = s.limits.find((x) => x.key === c.key), margin = Math.abs(l.bound - ceiling);
      const objective = def.objectives.find((o) => o.id === s.objective);
      const storm = isStorm(s.id, s.rain);
      text = `${c.label} stays flat because AUTO holds it at ${fmt(ceiling, c.digits)} ${c.unit}: the ${fmtBound(l.bound)} ${c.unit} limit `
        + `${l.upper ? "minus" : "plus"} a ${fmt(margin, c.digits)} ${c.unit} margin for the ${storm ? "storm network's" : "network's"} error. That limit is what stops the optimizer `
        + `(${objective.label.toLowerCase()}), so it uses all the room the limit allows, and the set-points follow the ${asPhrase(def.disturbance.label)} instead.`
        + (storm ? " The storm network is less sure near the limit than the dry-weather one, so the margin is wider while it rains." : "");
      break;
    }
    if (box.textContent !== text) box.textContent = text;
    box.hidden = !text;
  }

  function drawChart(i) {
    const s = plantState();
    const c = DEFS[s.id].trends[i];
    const svg = $(`chart-${i}-svg`);
    if (!svg) return;
    const W = Math.max(200, Math.round(svg.getBoundingClientRect().width || 360));
    const H = 150, L = 48, R = 12, T = 10, B = 22;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const pts = s.history;
    // With rain the influent trend shows what reaches the plant, sewage and rain, with the rain hatched.
    const rainy = c.key === "disturbance" && RAIN[s.id];
    const val = (p) => (rainy ? p.disturbance + (p.rain || 0) : p[c.key]);
    const now = pts.length ? val(pts[pts.length - 1]) : NaN;
    $(`chart-${i}-now`).textContent = Number.isFinite(now) ? `${fmt(now, c.digits)} ${c.unit}` : "";
    if (pts.length < 2) { svg.innerHTML = `<text class="c-axis" x="${L}" y="${H / 2}">Collecting samples…</text>`; return; }

    const t1 = pts[pts.length - 1].t, t0 = Math.max(pts[0].t, t1 - WINDOW_MIN);
    const simKey = `sim_${c.key}`, autoKey = `auto_${c.key}`;
    let lo = Infinity, hi = -Infinity;
    for (const p of pts) {
      lo = Math.min(lo, val(p), rainy ? p.disturbance : Infinity); hi = Math.max(hi, val(p));
      for (const k of [simKey, autoKey])
        if (Number.isFinite(p[k])) { lo = Math.min(lo, p[k]); hi = Math.max(hi, p[k]); }
    }
    // The limit in force on this output (the permit's or the operator's), if any, and in AUTO the
    // line the optimizer keeps the prediction behind: the limit less the safety margin of the
    // network in use, drawn as it was at each sample (it steps when the storm network takes over).
    const active = s.limits.find((l) => l.key === c.key && l.enabled);
    const limit = active ? active.bound : undefined;
    const ceiling = autoCeiling(s, c.key);
    for (const v of [limit, ceiling]) if (v !== undefined) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    // At least 6 % of the level, so that a fraction of a percent between OpenNN and WaterTAP does
    // not fill the whole axis.
    const minSpan = Math.abs(lo + hi) * 0.03;
    if (hi - lo < minSpan) { const mid = (lo + hi) / 2; lo = mid - minSpan / 2; hi = mid + minSpan / 2; }
    const pad = (hi - lo) * 0.12 || Math.abs(hi) * 0.02 || 1;
    lo -= pad; hi += pad;
    if (c.key !== "disturbance" && lo < 0 && Math.min(...pts.map(val)) >= 0) lo = 0;
    const { ticks } = niceTicks(lo, hi, 3);
    const X = (t) => L + ((W - L - R) * (t - t0)) / Math.max(1e-9, t1 - t0);
    const Y = (v) => T + ((H - T - B) * (hi - v)) / (hi - lo);

    let g = "";
    for (const v of ticks) {
      if (v < lo || v > hi) continue;
      g += `<line class="c-grid" x1="${L}" x2="${W - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/>`;
      g += `<text class="c-axis" x="${L - 6}" y="${(Y(v) + 3.5).toFixed(1)}" text-anchor="end">${fmt(v, Math.max(0, -Math.floor(Math.log10(Math.abs(ticks[1] - ticks[0] || 1)))))}</text>`;
    }
    const hourTicks = [];
    for (let h = Math.ceil(t0 / 120) * 120; h <= t1; h += 120) hourTicks.push(h);
    for (const h of hourTicks) g += `<text class="c-axis" x="${X(h).toFixed(1)}" y="${H - 6}" text-anchor="middle">${clockText(h)}</text>`;

    const shown = pts.filter((p) => p.t >= t0);
    const line = shown.map((p) => `${X(p.t).toFixed(1)},${Y(val(p)).toFixed(1)}`);
    const first = shown[0];
    const area = `M${X(first.t).toFixed(1)},${(H - B).toFixed(1)} L${line.join(" L")} L${X(t1).toFixed(1)},${(H - B).toFixed(1)} Z`;
    g += `<path class="c-area" d="${area}"/>`;
    if (rainy && shown.some((p) => p.rain > 0)) {
      const sewage = shown.map((p) => `${X(p.t).toFixed(1)},${Y(p.disturbance).toFixed(1)}`);
      g += `<defs><pattern id="rain-hatch-${i}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line class="c-rain-hatch" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>`;
      g += `<path class="c-rain" fill="url(#rain-hatch-${i})" d="M${sewage.join(" L")} L${[...line].reverse().join(" L")} Z"/>`;
    }
    g += `<path class="c-line" d="M${line.join(" L")}"/>`;
    if (limit !== undefined) {
      g += `<line class="c-limit" x1="${L}" x2="${W - R}" y1="${Y(limit).toFixed(1)}" y2="${Y(limit).toFixed(1)}"/>`;
      g += `<text class="c-limit-label" x="${W - R - 2}" y="${(Y(limit) - 4).toFixed(1)}" text-anchor="end">limit ${fmtBound(limit)}</text>`;
    }
    let steps = "", before;
    for (const p of shown) {
      const v = p[autoKey];
      if (!Number.isFinite(v)) { before = undefined; continue; }
      const x = X(p.t).toFixed(1);
      steps += before === undefined ? `M${x},${Y(v).toFixed(1)}` : `${v !== before ? ` L${x},${Y(before).toFixed(1)}` : ""} L${x},${Y(v).toFixed(1)}`;
      before = v;
    }
    if (steps) g += `<path class="c-ceiling" d="${steps}"/>`;
    if (ceiling !== undefined) {
      const away = active.upper ? 12 : -5;   // the label on the side away from the limit
      g += `<text class="c-ceiling-label" x="${W - R - 12}" y="${(Y(ceiling) + away).toFixed(1)}" text-anchor="end">AUTO ${active.upper ? "≤" : "≥"} ${fmt(ceiling, c.digits)}</text>`;
    }
    const last = pts[pts.length - 1];
    g += `<circle class="c-end" cx="${X(last.t).toFixed(1)}" cy="${Y(val(last)).toFixed(1)}" r="4"/>`;

    // WaterTAP solutions of the sampled operating points, newest first and thinned so that the
    // markers never overlap.
    let lastX = Infinity;
    for (let k = pts.length - 1; k >= 0; k--) {
      const p = pts[k];
      if (p.t < t0 || !Number.isFinite(p[simKey])) continue;
      const x = X(p.t);
      if (lastX - x < 14) continue;
      g += `<circle class="c-sim" cx="${x.toFixed(1)}" cy="${Y(p[simKey]).toFixed(1)}" r="4"/>`;
      lastX = x;
    }

    const tip = $(`chart-${i}-tip`);
    if (app.hover[i] !== undefined) {
      const hx = clamp(app.hover[i], L, W - R);
      const th = t0 + ((hx - L) / (W - L - R)) * (t1 - t0);
      let best = pts[0];
      for (const p of pts) if (Math.abs(p.t - th) < Math.abs(best.t - th)) best = p;
      const px = X(best.t), py = Y(val(best));
      const sv = best[simKey];
      g += `<line class="c-cross" x1="${px.toFixed(1)}" x2="${px.toFixed(1)}" y1="${T}" y2="${H - B}"/><circle class="c-dot" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5"/>`;
      if (Number.isFinite(sv)) g += `<circle class="c-sim" cx="${px.toFixed(1)}" cy="${Y(sv).toFixed(1)}" r="4.5"/>`;
      tip.hidden = false;
      tip.textContent = c.key === "disturbance"
        ? `${clockText(best.t)}  ${fmt(val(best), c.digits)} ${c.unit}${rainy && best.rain > 0 ? ` (rain ${fmt(best.rain, 0)})` : ""}`
        : `${clockText(best.t)}  OpenNN ${fmt(best[c.key], c.digits)}${Number.isFinite(sv) ? ` · WaterTAP ${fmt(sv, c.digits)}` : ""} ${c.unit}`;
      const box = svg.getBoundingClientRect(), host = $(`chart-${i}`).getBoundingClientRect();
      const tw = tip.offsetWidth || 150;
      const at = box.left - host.left + (px / W) * box.width;
      const left = at + 10 + tw <= host.width - 4 ? at + 10 : at - 10 - tw;
      tip.style.left = `${clamp(left, 4, Math.max(4, host.width - tw - 4))}px`;
      tip.style.top = `${box.top - host.top + 4}px`;
    } else tip.hidden = true;
    // invisible hit area for the pointer, larger than the line
    g += `<rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>`;
    svg.innerHTML = g;
  }

  // ------------------------------------------------------------------ guided demo

  // One minute that tells the whole story: a feasible default, the OpenNN proposal, the set-points
  // applied, the condition changing with the set-points held, then AUTO re-optimizing.
  const demo = { timers: [], step: "" };

  function stopDemo(announce = false) {
    demo.timers.forEach(clearTimeout);
    demo.timers = [];
    demo.step = "";
    if (announce) logEvent(plantState(), "info", "Demo stopped");
    renderDemo();
  }

  function renderDemo() {
    const button = $("demo"), step = $("demo-step");
    if (!button) return;
    button.textContent = demo.timers.length ? "Stop demo" : "Play guided demo";
    step.textContent = demo.step;
  }

  function runDemo() {
    stopDemo();
    const id = app.active, s = app.plants[id], def = DEFS[id];
    const stage = (text) => { demo.step = text; logEvent(s, "info", `Demo: ${text}`); renderDemo(); };
    const at = (sec, fn) => demo.timers.push(setTimeout(() => {
      if (app.active !== id) return;
      fn();
      s.outputs = predict(id, s.setpoints, s.disturbance);
      renderLive();
    }, sec * 1000));

    if (s.mode === "auto") setMode(s, "manual");
    if (!isPermit(s)) { s.limits = permitLimits(id); logEvent(s, "info", "Demo: limits reset to the permit"); }
    s.pattern = false;
    if (s.storm || s.rain) { s.storm = false; s.rain = 0; s.rainFlow = 0; logEvent(s, "info", "Demo: dry weather"); }
    app.speed = 10;
    s.objective = def.objectives[0].id;
    loadDefault(s, true, true);
    s.outputs = predict(id, s.setpoints, s.disturbance);
    stage("1 of 4, a random default operation that meets every limit");
    at(4, () => { stage("2 of 4, OpenNN proposes the optimal set-points and WaterTAP checks them"); propose(s); });
    at(8, () => applyProposal(s));
    at(16, () => {
      app.speed = 30;
      s.pattern = true;
      stage(`3 of 4, ${def.disturbance.patternLabel.toLowerCase()} with the set-points held fixed`);
    });
    at(38, () => { stage("4 of 4, AUTO lets OpenNN re-optimize as the condition changes"); setMode(s, "auto"); });
    at(62, () => { demo.timers = []; demo.step = "Demo finished: AUTO stays on"; renderDemo(); });
    renderLive();
  }

  // ------------------------------------------------------------------ page rendering

  function renderLive() {
    const s = plantState();
    if (s.id === "bsm2") updateBsm2Diagram(s); else updateRoDiagram(s);
    updateControls();
    renderKpis();
    renderLimits();
    renderCheck();
    renderBanner();
    renderSource();
  }

  function renderAbout() {
    const s = plantState(), facts = DATA.plants[s.id].facts, storm = STORM[s.id];
    const levels = storm ? storm.rain_levels.map((v) => fmt(v, 0)) : [];
    const levelText = levels.length > 1 ? `${levels.slice(0, -1).join(", ")} and ${levels[levels.length - 1]}` : levels.join("");
    const stormRuns = storm ? ` While it rains, a second network takes over: the storm network (${esc(storm.facts.architecture)}, the rain flow being the seventh input). In dry weather the first one is more accurate, so the page switches between them with the weather.` : "";
    const stormLearned = storm ? ` ${esc(storm.facts.source)}${storm.facts.comparison ? ` ${esc(storm.facts.comparison)}` : ""}` : "";
    const stormOptima = storm ? ` For a storm it did the same at ${levelText} m³/d of rain, on the storm network: ${esc(verificationSentence(storm.facts).replace(/^In WaterTAP, /, "in WaterTAP, "))}` : "";
    $("about").innerHTML = `
      <div><h3>What runs here</h3><p>An OpenNN neural network (${esc(facts.architecture)}, <span class="num">${fmt(facts.parameters, 0)}</span> weights) predicts the plant from its set-points. It runs in this page from its exported weights and answers at once.${stormRuns}</p></div>
      <div><h3>The simulator next to it</h3><p>When the WaterTAP service runs on this computer (<b>Start WaterTAP</b>, after <b>setup.bat</b> once), each operating point that holds still and each OpenNN proposal is also solved in the WaterTAP flowsheet, and the page shows both. Without it, only the stored WaterTAP solutions are shown.</p></div>
      <div><h3>Where it learned</h3><p>${esc(facts.source)} The network was trained on <span class="num">${fmt(facts.rows, 0)}</span> simulations.${facts.comparison ? ` ${esc(facts.comparison)}` : ""}${stormLearned}</p></div>
      <div><h3>The optimizer</h3><p>For the permit limits, OpenNN response optimization found the set-points for each ${esc(DEFS[s.id].disturbance.label.toLowerCase())} beforehand, keeping each limit with a safety margin equal to the network's validation error. ${esc(verificationSentence(facts))}${stormOptima} For limits you set, the page solves the same problem on the OpenNN network in use, in the browser.</p></div>
      <div><h3>Read with care</h3><p>The models are steady state: each moment shows the plant settled at the current set-points and condition. Ramps and patterns are sequences of steady states, not process dynamics.${RAIN[s.id] ? " A storm is therefore shown as a plant settled into wet weather: the diluted influent and the extra flow, which also wastes more sludge (wastage is a share of the clarifier underflow), so NH₄ rises. The first hours of a real storm (first flush, clarifier overload) are not modelled; WaterTAP's clarifiers have fixed splits." : ""}</p></div>`;
  }

  function renderLegend(id) {
    const item = (svg, text) => `<span><svg viewBox="0 0 26 14" aria-hidden="true">${svg}</svg>${esc(text)}</span>`;
    $("legend").innerHTML = [
      item('<line class="lg-line" x1="1" y1="7" x2="25" y2="7"/>', "Process line"),
      id === "bsm2" ? item('<line class="lg-air" x1="1" y1="7" x2="25" y2="7"/>', "Air") : "",
      item('<rect class="lg-sp" x="1.5" y="2" width="23" height="10" rx="2"/>', "Set-point"),
      item('<rect class="lg-tag" x="1.5" y="2" width="23" height="10" rx="2"/>', "Measurement"),
      item('<path class="lg-target" d="M7 3 h12 l-6 8 z"/>', "OpenNN target"),
      item('<rect class="lg-warn" x="1.5" y="2" width="23" height="10" rx="2"/>', "Inside safety margin"),
      item('<rect class="lg-alarm" x="1.5" y="2" width="23" height="10" rx="2"/>', "Limit exceeded"),
    ].join("");
  }

  function switchPlant(id) {
    if (demo.timers.length) stopDemo();
    app.active = id;
    app.pointKey = "";
    for (const b of document.querySelectorAll(".tabs button")) b.setAttribute("aria-selected", String(b.dataset.plant === id));
    $("process-title").textContent = DEFS[id].title;
    $("diagram").innerHTML = id === "bsm2" ? diagramBsm2() : diagramRo();
    renderLegend(id);
    const s = plantState();
    s.outputs = predict(s.id, s.setpoints, s.disturbance);
    buildControls();
    buildCharts();
    renderAbout();
    renderEvents();
    renderDemo();
    renderLive();
    try { history.replaceState(null, "", `#${id}`); } catch (e) { /* file:// in some browsers */ }
  }

  // ------------------------------------------------------------------ theme

  function applyTheme(theme) {
    if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    $("theme-toggle").textContent = theme ? `Theme: ${theme}` : "Theme: system";
  }
  function initTheme() {
    let theme = null;
    try { theme = localStorage.getItem("hmi-theme"); } catch (e) { theme = null; }
    applyTheme(theme === "light" || theme === "dark" ? theme : null);
    $("theme-toggle").addEventListener("click", () => {
      const current = document.documentElement.dataset.theme || null;
      const next = current === null ? "dark" : current === "dark" ? "light" : null;
      applyTheme(next);
      try { if (next) localStorage.setItem("hmi-theme", next); else localStorage.removeItem("hmi-theme"); } catch (e) { /* storage blocked */ }
      renderCharts();
    });
  }

  // ------------------------------------------------------------------ start

  preloadStored();
  for (const id of Object.keys(DEFS)) {
    const s = newPlantState(id);
    app.plants[id] = s;
    loadDefault(s, false);
    s.outputs = predict(id, s.setpoints, s.disturbance);
    for (const l of limitList(s, s.outputs)) s.limitStates[l.key] = l.status;
    logEvent(s, "info", `Default operation ${s.defaultIndex + 1} of ${DATA.plants[id].defaults.length} loaded (random feasible set-points, solved in WaterTAP): ${describeSetpoints(id, s.setpoints)}`);
    for (let k = 0; k < 3; k++) { sample(s); s.t += 1; }
  }
  measureNetwork();
  startOptimizer();
  for (const b of document.querySelectorAll(".tabs button")) b.addEventListener("click", () => switchPlant(b.dataset.plant));
  $("proposal").addEventListener("click", (e) => {
    const st = plantState();
    if (e.target.closest("#apply")) applyProposal(st);
    if (e.target.closest("#discard")) { st.proposal = false; logEvent(st, "info", "Operator discarded the OpenNN proposal"); }
    if (e.target.closest("#dismiss")) st.result = null;
    renderLive();
  });
  for (const [button, source] of [["src-nn", "nn"], ["src-sim", "sim"]])
    $(button).addEventListener("click", () => { app.source = source; renderLive(); });
  $("sim-start").addEventListener("click", startSimulator);
  $("check").addEventListener("click", (e) => { if (e.target.closest("[data-action='start-sim']")) startSimulator(); });
  initTheme();
  // #ro opens the desalination plant; #bsm2-demo or #ro-demo also starts the guided demo.
  const [startPlant, startDemo] = (location.hash || "").replace("#", "").split("-");
  switchPlant(DEFS[startPlant] ? startPlant : "bsm2");
  if (startDemo === "demo") setTimeout(runDemo, 400);
  window.addEventListener("resize", () => renderCharts());
  setInterval(tick, TICK_MS);
  pollSimulator();
})();
