// In-browser forward pass of the OpenNN networks exported by tools/export_weights.py.
// Same arithmetic as OpenNN's layers: Scaling -> Dense (tanh) -> Dense (identity) -> Unscaling
// (-> Clamping when the bounds are finite). Also used by tools/check_forward.mjs under Node.

const PlantModel = (() => {
  const EPSILON = 1e-7;

  const activations = {
    Tanh: Math.tanh,
    Identity: (v) => v,
    Sigmoid: (v) => 1 / (1 + Math.exp(-v)),
    RectifiedLinear: (v) => (v > 0 ? v : 0),
  };

  function scale(value, input) {
    switch (input.scaler) {
      case "MeanStandardDeviation":
        return input.std > EPSILON ? (value - input.mean) / input.std : 0;
      case "MinimumMaximum":
        return input.max - input.min > EPSILON ? -1 + (2 * (value - input.min)) / (input.max - input.min) : 0;
      case "Logarithm":
        return Math.log(Math.max(value, EPSILON));
      default:
        return value;
    }
  }

  function unscale(value, output) {
    switch (output.scaler) {
      case "MeanStandardDeviation":
        return value * output.std + output.mean;
      case "MinimumMaximum":
        return output.min + ((value + 1) * (output.max - output.min)) / 2;
      case "Logarithm":
        return Math.exp(value);
      default:
        return value;
    }
  }

  // values: an object keyed by input name, or an array in input order.
  // Returns an object keyed by output name.
  function predict(model, values) {
    let layer = model.inputs.map((input, i) =>
      scale(Array.isArray(values) ? values[i] : values[input.name], input));

    for (const { activation, biases, weights } of model.layers) {
      const f = activations[activation];
      if (!f) throw new Error(`Unsupported activation ${activation}`);
      const next = new Array(biases.length);
      for (let j = 0; j < biases.length; j++) {
        let sum = biases[j];
        for (let i = 0; i < layer.length; i++) sum += weights[i][j] * layer[i];
        next[j] = f(sum);
      }
      layer = next;
    }

    const result = {};
    model.outputs.forEach((output, k) => {
      let v = unscale(layer[k], output);
      if (model.clamping) v = Math.min(Math.max(v, model.clamping.lower[k]), model.clamping.upper[k]);
      result[output.name] = v;
    });
    return result;
  }

  return { predict };
})();

if (typeof module !== "undefined") module.exports = PlantModel;
