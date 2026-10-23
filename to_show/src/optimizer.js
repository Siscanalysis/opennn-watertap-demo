// Optimal set-points for the limits the operator sets on the page, on the OpenNN network in the
// browser. The stored optima were computed by OpenNN response optimization for the permit limits;
// this solves the same problem for any other limits: one output minimized or maximized over the
// decision inputs inside the training box, the condition (influent or salinity) fixed, and each
// output limit backed off by its safety margin. Differential evolution with feasibility rules
// (a feasible point beats an infeasible one; between infeasible points the smaller violation wins),
// then a pattern search around the best point. Runs in a Web Worker started by app.js, and under
// Node for tools/check_optimizer.mjs.

function solveOptimum(task) {
  const { model, decisions, fixed, objective, constraints } = task;
  const names = model.inputs.map((input) => input.name);
  const D = decisions.length;
  const lo = decisions.map((d) => d.min);
  const span = decisions.map((d) => d.max - d.min);
  const slot = decisions.map((d) => names.indexOf(d.name));
  const base = names.map((name) => (name in fixed ? fixed[name] : 0));
  const position = (name) => names.indexOf(name);
  let evaluations = 0;

  // Small seeded generator (mulberry32), so a task always gives the same answer.
  let state = (task.seed >>> 0) || 1;
  const random = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  function evaluate(u) {
    const values = base.slice();
    for (let k = 0; k < D; k++) values[slot[k]] = lo[k] + u[k] * span[k];
    const y = PlantModel.predict(model, values);
    evaluations++;
    let violation = 0;
    for (const c of constraints) {
      let excess;
      if (c.kind === "output") excess = (c.upper ? y[c.key] - c.threshold : c.threshold - y[c.key]) / Math.max(Math.abs(c.threshold), 1e-6);
      else if (c.kind === "input") excess = (c.upper ? values[position(c.key)] - c.threshold : c.threshold - values[position(c.key)]) / c.span;
      else {
        // RO domain guard: pressure*(1 - recovery)/salinity at least its smallest value in the data.
        const ratio = values[position("pressure")] * (1 - values[position("recovery")]) / values[position("salinity")];
        excess = (c.min - ratio) / c.min;
      }
      if (excess > 0) violation += excess;
    }
    const f = objective.sense === "min" ? y[objective.output] : -y[objective.output];
    return { u, y, values, f, violation };
  }

  const better = (a, b) => (a.violation <= 1e-12
    ? b.violation > 1e-12 || a.f < b.f
    : b.violation > 1e-12 && a.violation < b.violation);

  const toUnit = (point) => decisions.map((d, k) => Math.min(1, Math.max(0, (point[d.name] - lo[k]) / span[k])));

  function evolve(seedPoints, generations) {
    const NP = Math.max(20, 10 * D);
    const population = [];
    for (const point of seedPoints) if (population.length < NP) population.push(evaluate(toUnit(point)));
    while (population.length < NP) population.push(evaluate(decisions.map(() => random())));
    let best = population.reduce((a, b) => (better(b, a) ? b : a));
    let stale = 0;
    for (let g = 0; g < generations && stale < 40; g++) {
      const before = best;
      for (let i = 0; i < NP; i++) {
        let r1, r2, r3;
        do r1 = Math.floor(random() * NP); while (r1 === i);
        do r2 = Math.floor(random() * NP); while (r2 === i || r2 === r1);
        do r3 = Math.floor(random() * NP); while (r3 === i || r3 === r1 || r3 === r2);
        const F = 0.5 + 0.3 * random();
        const jrand = Math.floor(random() * D);
        const u = population[i].u.slice();
        for (let j = 0; j < D; j++) {
          if (j !== jrand && random() >= 0.9) continue;
          let v = population[r1].u[j] + F * (population[r2].u[j] - population[r3].u[j]);
          if (v < 0) v = -v * random();
          if (v > 1) v = 1 - (v - 1) * random();
          u[j] = Math.min(1, Math.max(0, v));
        }
        const trial = evaluate(u);
        if (!better(population[i], trial)) population[i] = trial;
        if (better(trial, best)) best = trial;
      }
      stale = best === before ? stale + 1 : 0;
    }
    return best;
  }

  function polish(start) {
    let current = start;
    let step = 0.05;
    for (let sweeps = 0; step > 1e-4 && sweeps < 400; sweeps++) {
      let improved = false;
      for (let k = 0; k < D; k++) {
        for (const sign of [1, -1]) {
          const u = current.u.slice();
          u[k] = Math.min(1, Math.max(0, u[k] + sign * step));
          const candidate = evaluate(u);
          if (better(candidate, current)) { current = candidate; improved = true; }
        }
      }
      if (!improved) step /= 2;
    }
    return current;
  }

  const starts = task.starts || [];
  const runs = D > 2 ? 2 : 1;
  let best = null;
  for (let r = 0; r < runs; r++) {
    const found = polish(evolve(r === 0 ? starts : [], D > 2 ? 220 : 90));
    if (!best || better(found, best)) best = found;
  }

  const x = {};
  names.forEach((name, i) => { x[name] = best.values[i]; });
  return { x, y: best.y, feasible: best.violation <= 1e-12, violation: best.violation, evaluations };
}

if (typeof module !== "undefined") module.exports = solveOptimum;
