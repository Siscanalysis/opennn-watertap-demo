# Notes for coding agents

This repository holds neural-network surrogates of WaterTAP water-treatment plants, trained and optimized with OpenNN, and a browser demo, `to_show/water_treatment_hmi.html`, that runs the networks next to a live WaterTAP simulator. [README.md](README.md) is the overview. [to_show/README.md](to_show/README.md) documents the demo, the simulator service and the rebuild pipeline.

## Run the demo

From the repository root:

| Step | Windows | Linux, macOS |
|---|---|---|
| Set up once (exit code 0 = ready) | `setup.bat --yes` | `./setup.sh` |
| Start the simulator and serve the page | `start_demo.bat --no-browser` | `./start_demo.sh --no-browser` |

- Setup creates the Python environment (WaterTAP 1.8.0, IDAES 2.13, about 1 GB) and fetches the IPOPT solver. It then checks that both WaterTAP models build and solve. On Windows it also registers the page's Start WaterTAP button for the current user. `setup.bat --yes` installs Miniforge for the current user if no conda is found. `setup.sh` needs Python 3.11 to 3.13 (or conda) and creates `.venv`. The Python's `ensurepip` is optional. When IPOPT's system libraries are missing, `setup.sh` installs them with `apt-get` as root, or otherwise puts conda-forge's copies into `.venv/system-libs`, without sudo. `start_demo.sh` then sets `LD_LIBRARY_PATH` for them.
- The service listens on `http://127.0.0.1:8765/` only. It serves the page at `/` and keeps running until its process is stopped. Without `--no-browser` it also opens the page in the default browser.
- Ready when `GET /status` reports `"ready": {"ro": true, "bsm2": true}`. The desalination models need seconds; the wastewater models need up to a minute.
- Solve one operating point. The body is JSON, and the content type is not checked:

  ```
  curl -s -X POST http://127.0.0.1:8765/simulate -d "{\"plant\": \"ro\", \"x\": {\"salinity\": 35, \"recovery\": 0.45, \"pressure\": 60}}"
  ```

  The wastewater plant (`"plant": "bsm2"`) takes `do3`, `do4`, `do5` (mg/L), `recycle` and `wastage` (fractions), `influent` (m³/d) and, optionally, `rain` (m³/d, 0 when left out). The answer gives `status` (`ok`, `washout` or `failed`), `outputs` and `seconds`.
- Check without serving: `python to_show/simulator/server.py --check`, with the environment's Python. On Windows that is the path in `to_show/simulator/python_path.txt`; on Linux and macOS, `.venv/bin/python`, after `source to_show/simulator/system_libs.sh`.
- Stop: on Windows close the "WaterTAP simulator" window, or end the `python` process running `to_show/simulator/server.py` together with its worker processes. On Linux and macOS use Ctrl+C or kill the process.
- The HTML file also works opened directly, without the service. It then shows the stored WaterTAP solutions only.

## Change the page

- Edit the sources in `to_show/src/`: `index.html`, `style.css`, `app.js`, `model.js` and `optimizer.js`. Never edit the built `to_show/water_treatment_hmi.html`.
- Rebuild with `python to_show/tools/build_dashboard.py`, using the environment's Python. It inlines the sources, the network weights and the stored WaterTAP data into the HTML file.
- `node to_show/tools/check_optimizer.mjs bsm2` (and `ro`) checks the page's optimizer against OpenNN's stored optima. It exits 1 if the page's optimizer does worse.

## Retrain and recompute

Follow "Retraining and rebuilding" in [to_show/README.md](to_show/README.md). `build_surrogates.bat` builds the C++ surrogate programs: it downloads OpenNN from GitHub and builds it with them (Windows, Visual Studio 2022 or later with the C++ workload; about 15 minutes the first time). `OPENNN_SOURCE_DIR` points it at another OpenNN source tree. Generating WaterTAP data takes from tens of minutes to hours of CPU. The generation scripts save as they go and take worker counts and time limits.

## Conventions

- `.bat` files keep CRLF line endings, because cmd.exe misreads LF-only scripts; `.gitattributes` stores them as they are. `.sh` files keep LF.
- No executables or other build products go in Git (see `.gitignore`).
- Each simulator session appends its solves to `to_show/models/<plant>/data/session_simulations_local.csv`, which Git ignores. `tools/prepare_training.py` adds them to the next training set.
- The Python pins are in `environment.yml` and `requirements.txt`.

## Layout

| Path | Contents |
|---|---|
| `ro_flowsheet.py`, `generate_dataset.py`, `model/` | The reverse-osmosis toy: the WaterTAP wrapper, dataset generation and the OpenNN surrogate (C++) |
| `bsm2_steady/` | The steady-state BSM2 toy: `bsm2_flowsheet.py` (the WaterTAP wrapper), data and surrogate |
| `bsm2_dynamic/` | The plan for the dynamic benchmark |
| `to_show/` | The demo: the built page, `src/`, `simulator/server.py`, `tools/`, the retrained networks (`models/`), the browser weights (`weights/`) and the WaterTAP-verified points (`data/`) |
| `setup.bat`, `setup.sh`, `start_demo.*`, `environment.yml`, `requirements.txt` | Setup and launch |
| `CMakeLists.txt`, `build_surrogates.bat` | Building the two C++ trainers with OpenNN |
