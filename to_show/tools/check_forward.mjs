// Compares the browser forward pass (src/model.js) with OpenNN's own predictions.
//   node check_forward.mjs <weights.json> <predictions.csv>
// predictions.csv is the output of `<surrogate> predict`: input columns, then output columns.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const PlantModel = require("../src/model.js");

const [weightsPath, csvPath] = process.argv.slice(2);
const model = JSON.parse(readFileSync(weightsPath, "utf8"));
const [header, ...rows] = readFileSync(csvPath, "utf8").trim().split(/\r?\n/);
const columns = header.split(",");

// Differences are judged against each output's spread in the training data (its standard
// deviation): a relative error is meaningless where an output is near zero, such as the RO
// outlet flux near the osmotic limit.
let worstAbsolute = {}, worstScaled = {};
for (const line of rows) {
  const cells = line.split(",").map(Number);
  const record = Object.fromEntries(columns.map((c, i) => [c, cells[i]]));
  const predicted = PlantModel.predict(model, record);
  for (const { name, std } of model.outputs) {
    const a = Math.abs(predicted[name] - record[name]);
    worstAbsolute[name] = Math.max(worstAbsolute[name] ?? 0, a);
    worstScaled[name] = Math.max(worstScaled[name] ?? 0, a / std);
  }
}

const worst = Math.max(...Object.values(worstScaled));
console.log(`${rows.length} points; worst difference per output, in units of the output's standard deviation:`);
for (const name of Object.keys(worstScaled))
  console.log(`  ${name.padEnd(13)} ${worstScaled[name].toExponential(2)}  (absolute ${worstAbsolute[name].toExponential(2)})`);
console.log(worst < 1e-5 ? "PASS: browser model matches OpenNN" : "FAIL: browser model differs from OpenNN");
process.exit(worst < 1e-5 ? 0 : 1);
