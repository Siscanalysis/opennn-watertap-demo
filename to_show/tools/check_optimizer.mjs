// Checks the page's optimizer (src/optimizer.js) against OpenNN's stored optima at the permit
// limits: for every condition and objective, the objective value each reaches on the same network
// and whether the answer meets every limit with its safety margin.
//
//   node check_optimizer.mjs <plant: bsm2|ro> [--cold]
//
// --cold: no starting point (by default OpenNN's optimum seeds the search, as the page seeds it with
// the permit optimum for the condition).
//
// Reads weights/<plant>_network.json, models/<plant>/results/validation_predictions.csv (margins),
// models/<plant>/results/dashboard_optima.csv (OpenNN's optima) and, for RO, models/ro/data/ro_dataset.csv
// (the domain guard). Exits 1 if the optimizer is worse than OpenNN by more than 0.5 % anywhere.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
globalThis.PlantModel = require(join(root, "src", "model.js"));
const solveOptimum = require(join(root, "src", "optimizer.js"));

const plant = process.argv[2];
const csv = (path) => {
  const [head, ...lines] = readFileSync(path, "utf8").trim().split(/\r?\n/);
  const keys = head.split(",");
  return lines.map((line) => Object.fromEntries(line.split(",").map((v, i) => [keys[i], v])));
};

const model = JSON.parse(readFileSync(join(root, "weights", `${plant}_network.json`), "utf8"));
const validation = csv(join(root, "models", plant, "results", "validation_predictions.csv"));
const margin = (key, bound) => {
  const errors = validation.filter((r) => +r[key] >= 0.5 * bound && +r[key] <= 2 * bound)
    .map((r) => Math.abs(+r[`${key}_predicted`] - +r[key])).sort((a, b) => a - b);
  return errors.length ? errors[Math.ceil(0.95 * errors.length) - 1] : 0;
};
const box = Object.fromEntries(model.inputs.map((i) => [i.name, i]));

const SETUP = {
  bsm2: {
    disturbance: "influent",
    decisions: ["do3", "do4", "do5", "recycle", "wastage"],
    objectives: { min_energy: ["sec", "min"], min_cost: ["lcow", "min"], max_biogas: ["biogas", "max"] },
    limits: [["nh4", true, 4], ["tn", true, 18], ["cod", true, 100], ["tss", true, 30], ["bod5", true, 10]],
    inputs: [],
  },
  ro: {
    disturbance: "salinity",
    decisions: ["recovery", "pressure"],
    objectives: { min_cost: ["lcow", "min"] },
    limits: [["permeate_ppm", true, 500], ["flux_out", false, 1]],
    inputs: [["pressure", 80]],
  },
}[plant];

const constraints = SETUP.limits.map(([key, upper, bound]) => {
  const m = margin(key, bound);
  return { kind: "output", key, upper, threshold: upper ? bound - m : bound + m };
});
for (const [key, bound] of SETUP.inputs)
  constraints.push({ kind: "input", key, upper: true, threshold: bound, span: box[key].max - box[key].min });
if (plant === "ro") {
  const data = csv(join(root, "models", "ro", "data", "ro_dataset.csv"));
  constraints.push({ kind: "guard", min: Math.min(...data.map((r) => (+r.pressure * (1 - +r.recovery)) / +r.salinity)) });
}

const meets = (y, x) => constraints.every((c) => c.kind === "output"
  ? (c.upper ? y[c.key] <= c.threshold + 1e-6 * Math.abs(c.threshold) : y[c.key] >= c.threshold - 1e-6 * Math.abs(c.threshold))
  : c.kind === "input" ? x[c.key] <= c.threshold + 1e-9
  : (x.pressure * (1 - x.recovery)) / x.salinity >= c.min - 1e-9);

let worst = 0, failures = 0, count = 0, ms = 0;
for (const row of csv(join(root, "models", plant, "results", "dashboard_optima.csv"))) {
  const spec = SETUP.objectives[row.objective];
  if (!spec) continue;
  const [output, sense] = spec;
  const condition = +row[SETUP.disturbance];
  const opennnX = Object.fromEntries(model.inputs.map((i) => [i.name, +row[i.name]]));
  const opennnY = PlantModel.predict(model, opennnX);
  const start = Date.now();
  const result = solveOptimum({
    model, constraints, seed: 7,
    decisions: SETUP.decisions.map((name) => ({ name, min: box[name].min, max: box[name].max })),
    fixed: { [SETUP.disturbance]: condition },
    objective: { output, sense },
    starts: process.argv.includes("--cold") ? [] : [Object.fromEntries(SETUP.decisions.map((n) => [n, opennnX[n]]))],
  });
  ms += Date.now() - start;
  count++;
  const a = opennnY[output], b = result.y[output];
  const gain = (100 * (sense === "min" ? a - b : b - a)) / Math.abs(a);
  const ok = result.feasible && meets(result.y, result.x);
  if (!ok) failures++;
  worst = Math.min(worst, gain);
  if (!ok || gain < -0.2)
    console.log(`  ${row.objective} ${SETUP.disturbance} ${condition}: OpenNN ${a.toFixed(5)} (limits ${meets(opennnY, opennnX) ? "met" : "MISSED"}), page ${b.toFixed(5)} (${ok ? "feasible" : "INFEASIBLE"}), ${gain.toFixed(2)} %`);
}
console.log(`${plant}: ${count} optima; page optimizer ${failures ? `${failures} infeasible` : "always feasible"}; `
  + `worst objective vs OpenNN ${worst.toFixed(2)} % (positive = better); ${(ms / count).toFixed(0)} ms each`);
process.exit(failures || worst < -0.5 ? 1 : 0);
