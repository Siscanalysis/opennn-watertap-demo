"""Writes the trained OpenNN networks (to_show/models/<plant>/model) as compact weight files for the
browser.

Reads each network's OpenNN JSON (scaling and unscaling statistics, layer activations) and the
parameters written by `<surrogate> export <root>` (biases and weights), and writes
to_show/weights/<plant>_network.json:

    inputs   name, mean, std, min, max, scaler   (min/max = the training box, used for the sliders)
    layers   activation, biases[j], weights[i][j] (i = layer input, j = layer output)
    outputs  name, scaler, mean, std, min, max   (scaler MeanStandardDeviation or Logarithm)

    python export_weights.py [bsm2] [ro]
"""

import json
import sys

from plants import NETWORK as PLANTS, TO_SHOW


def numbers(text):
    return [float(v) for v in text.split()]


def convert(network_path):
    network = json.loads(network_path.read_text())["Network"]
    parameters = json.loads((network_path.parent / "parameters.json").read_text())["layers"]
    by_label = {layer["label"]: layer["parameters"] for layer in parameters}

    items = network["Layers"]["Items"]
    scaling = next(item["Scaling"] for item in items if "Scaling" in item)
    unscaling = next(item["Unscaling"] for item in items if "Unscaling" in item)
    clamping = next((item["Clamping"] for item in items if "Clamping" in item), None)

    input_names = [entry["Text"] for entry in network["Inputs"]["Input"]]
    output_names = [entry["Text"] for entry in network["Outputs"]["Output"]]

    inputs = [{"name": name, "scaler": scaler, "mean": mean, "std": std, "min": lo, "max": hi}
              for name, scaler, mean, std, lo, hi in zip(
                  input_names, scaling["Scalers"].split(), numbers(scaling["Means"]),
                  numbers(scaling["StandardDeviations"]), numbers(scaling["Minimums"]),
                  numbers(scaling["Maximums"]))]

    layers = []
    for item in items:
        if "Dense" not in item:
            continue
        dense = item["Dense"]
        tensors = by_label[dense["Label"]]
        biases = next(t["values"] for t in tensors if len(t["shape"]) == 1)
        weights = next(t["values"] for t in tensors if len(t["shape"]) == 2)
        assert len(weights) == int(dense["InputDimensions"]) and len(biases) == int(dense["OutputDimensions"])
        layers.append({"activation": dense["Activation"], "biases": biases, "weights": weights})

    outputs = []
    for name, neuron in zip(output_names, unscaling["Neurons"]):
        lo, hi, mean, std = numbers(neuron["Descriptives"])
        outputs.append({"name": name, "scaler": neuron["Scaler"], "mean": mean, "std": std, "min": lo, "max": hi})

    if clamping is not None:
        lower, upper = numbers(clamping["LowerBounds"]), numbers(clamping["UpperBounds"])
        if all(abs(v) > 1e30 for v in lower + upper):
            clamping = None
        else:
            clamping = {"lower": lower, "upper": upper}

    return {"inputs": inputs, "layers": layers, "outputs": outputs, "clamping": clamping}


def main():
    folder = TO_SHOW / "weights"
    folder.mkdir(exist_ok=True)
    for plant in sys.argv[1:] or list(PLANTS):
        model = convert(PLANTS[plant])
        target = folder / f"{plant}_network.json"
        target.write_text(json.dumps(model, separators=(",", ":")))
        count = sum(len(l["biases"]) + sum(len(row) for row in l["weights"]) for l in model["layers"])
        print(f"{plant}: {len(model['inputs'])} inputs, {[len(l['biases']) for l in model['layers']]} neurons, "
              f"{count} parameters -> {target.name} ({target.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
