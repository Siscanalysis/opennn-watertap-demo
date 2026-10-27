"""Where the dashboard's networks live, for the tools in this folder.

The page uses the networks retrained on the extra simulations, in to_show/models/<plant>/ (data/,
model/, results/), trained and queried with the toy's OpenNN surrogate executables. The toy
folders keep the original networks untouched. bsm2_rain is the storm network, the wastewater
network with a seventh input, rain (storm_simulations.py, run_storm.py): the page carries it next
to the dry-weather network and uses it while it rains.
"""

from pathlib import Path

TO_SHOW = Path(__file__).resolve().parents[1]
TOY = TO_SHOW.parent

ROOT = {"bsm2": TO_SHOW / "models" / "bsm2", "ro": TO_SHOW / "models" / "ro",
        "bsm2_rain": TO_SHOW / "models" / "bsm2_rain"}
EXE = {"bsm2": TOY / "bsm2_steady" / "model" / "bsm2_surrogate.exe", "ro": TOY / "model" / "ro_surrogate.exe",
       "bsm2_rain": TOY / "bsm2_steady" / "model" / "bsm2_surrogate.exe"}
NETWORK = {"bsm2": ROOT["bsm2"] / "model" / "bsm2_network.json", "ro": ROOT["ro"] / "model" / "ro_network.json",
           "bsm2_rain": ROOT["bsm2_rain"] / "model" / "bsm2_network.json"}
DATASET = {plant: ROOT[plant] / "data" / f"{plant.split('_')[0]}_dataset.csv" for plant in ROOT}

# The original networks, for comparisons.
ORIGINAL_ROOT = {"bsm2": TOY / "bsm2_steady", "ro": TOY}
