"""Checks that the browser model reproduces OpenNN: 2,000 random inputs per plant inside the
training box, predicted by OpenNN (`<surrogate> predict`) and by src/model.js under Node.

    python check_forward.py [scratch folder] [bsm2|ro]
"""

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from plants import EXE, ROOT, TO_SHOW

PLANTS = {plant: (ROOT[plant], EXE[plant]) for plant in ROOT}


def main():
    scratch = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    scratch.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1)
    failures = 0
    for plant in sys.argv[2:] or list(PLANTS):
        root, exe = PLANTS[plant]
        weights = TO_SHOW / "weights" / f"{plant}_network.json"
        inputs = json.loads(weights.read_text())["inputs"]
        sample = scratch / f"{plant}_inputs.csv"
        predictions = scratch / f"{plant}_predictions.csv"
        with open(sample, "w") as f:
            f.write(",".join(i["name"] for i in inputs) + "\n")
            for _ in range(2000):
                f.write(",".join(f"{rng.uniform(i['min'], i['max']):.7g}" for i in inputs) + "\n")
        subprocess.run([str(exe), "predict", str(root), str(sample), str(predictions)], check=True)
        print(f"--- {plant}")
        result = subprocess.run(["node", str(TO_SHOW / "tools" / "check_forward.mjs"), str(weights), str(predictions)])
        failures += result.returncode != 0
    sys.exit(failures)


if __name__ == "__main__":
    main()
