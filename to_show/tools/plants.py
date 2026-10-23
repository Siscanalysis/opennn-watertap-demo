"""Where the dashboard's networks live, for the tools in this folder.

The page uses the networks retrained on the extra simulations, in to_show/models/<plant>/ (data/,
model/, results/), trained and queried with the toy's OpenNN surrogate executables. The toy
folders keep the original networks untouched.
"""

from pathlib import Path

TO_SHOW = Path(__file__).resolve().parents[1]
TOY = TO_SHOW.parent

ROOT = {"bsm2": TO_SHOW / "models" / "bsm2", "ro": TO_SHOW / "models" / "ro"}
EXE = {"bsm2": TOY / "bsm2_steady" / "model" / "bsm2_surrogate.exe", "ro": TOY / "model" / "ro_surrogate.exe"}
NETWORK = {plant: ROOT[plant] / "model" / f"{plant}_network.json" for plant in ROOT}
DATASET = {plant: ROOT[plant] / "data" / f"{plant}_dataset.csv" for plant in ROOT}

# The original networks, for comparisons.
ORIGINAL_ROOT = {"bsm2": TOY / "bsm2_steady", "ro": TOY}
