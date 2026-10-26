#!/usr/bin/env bash
# One-time setup of the demo on Linux or macOS. Running it again only repairs what is missing.
#   1. A Python environment with WaterTAP 1.8.0 and IDAES 2.13: .venv, from requirements.txt, with
#      Python 3.11 to 3.13 ($PYTHON, python3.11, python3.12, python3.13 or python3); without one,
#      the conda environment "watertap" from environment.yml.
#   2. The IDAES solvers (IPOPT), if missing.
#   3. A check that both WaterTAP models build and solve.
# Options: --no-check (skip step 3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK=1
for arg in "$@"; do
  if [ "$arg" = "--no-check" ]; then CHECK=0; fi
done

good_python() {
  "$1" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)' >/dev/null 2>&1
}

echo "[1/3] Python environment"
PY=""
if [ -x "$ROOT/.venv/bin/python" ] && good_python "$ROOT/.venv/bin/python"; then
  PY="$ROOT/.venv/bin/python"
else
  BASE=""
  for candidate in "${PYTHON:-}" python3.11 python3.12 python3.13 python3; do
    if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1 && good_python "$candidate"; then
      BASE="$candidate"
      break
    fi
  done
  if [ -n "$BASE" ]; then
    echo "      creating .venv with $BASE"
    if ! "$BASE" -m venv "$ROOT/.venv" >/dev/null 2>&1; then
      # Debian and Ubuntu ship Python without ensurepip unless python3-venv is installed: create
      # the environment without pip, then fetch pip into it.
      echo "      (no ensurepip here: fetching pip into the environment)"
      rm -rf "$ROOT/.venv"
      "$BASE" -m venv --without-pip "$ROOT/.venv"
      "$BASE" -c "import urllib.request, sys; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', sys.argv[1])" "$ROOT/.venv/get-pip.py"
      "$ROOT/.venv/bin/python" "$ROOT/.venv/get-pip.py" --quiet
    fi
    PY="$ROOT/.venv/bin/python"
  elif command -v conda >/dev/null 2>&1; then
    if ! conda env list | grep -q '^watertap '; then
      echo "      creating the conda environment \"watertap\" (about 700 MB; a few minutes)"
      conda env create -n watertap -f "$ROOT/environment.yml"
    fi
    PY="$(conda run -n watertap python -c 'import sys; print(sys.executable)')"
  else
    echo "      Python 3.11 to 3.13, or conda, is needed (Ubuntu: sudo apt install python3.12 python3.12-venv)."
    exit 1
  fi
fi
if [ "$PY" = "$ROOT/.venv/bin/python" ]; then
  echo "      installing the packages (about 700 MB the first time; a few minutes)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$ROOT/requirements.txt"
fi
echo "      $PY"

echo "[2/3] Solvers"
ipopt_path() {
  "$PY" -c "import shutil, idaes; print(shutil.which('ipopt') or '')" 2>/dev/null
}
ipopt_runs() {
  local exe
  exe="$(ipopt_path)"
  [ -n "$exe" ] && "$exe" --version >/dev/null 2>&1
}
if [ -z "$(ipopt_path)" ]; then
  echo "      downloading the IDAES solvers (about 110 MB)"
  "$(dirname "$PY")/idaes" get-extensions
fi
# A previous run may have fetched the system libraries below into the environment.
SYSLIBS="$ROOT/.venv/system-libs"
if [ -d "$SYSLIBS" ]; then
  # shellcheck source=/dev/null
  . "$ROOT/to_show/simulator/system_libs.sh"
fi
if ! ipopt_runs && [ -n "$(ipopt_path)" ] && [ "$(uname)" = "Linux" ]; then
  # The IDAES binaries use the system's Fortran runtime, LAPACK, BLAS and OpenMP libraries.
  missing="$(ldd "$(ipopt_path)" | awk '/not found/ {print $1}' | tr '\n' ' ')"
  echo "      IPOPT cannot start; missing system libraries: $missing"
  if [ "$(id -u)" = 0 ] && command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq libgfortran5 liblapack3 libblas3 libgomp1
  else
    # Without root: the same libraries from conda-forge, into the environment, with micromamba (a
    # single program, also kept in the environment). No sudo needed.
    echo "      fetching them from conda-forge into .venv/system-libs (no sudo needed)"
    case "$(uname -m)" in x86_64) PLATFORM=linux-64 ;; aarch64) PLATFORM=linux-aarch64 ;; *) PLATFORM="" ;; esac
    rm -rf "$SYSLIBS"
    if [ -n "$PLATFORM" ] && "$PY" - "$PLATFORM" "$ROOT/.venv" <<'EOF'
import io, sys, tarfile, urllib.request
platform, target = sys.argv[1], sys.argv[2]
data = urllib.request.urlopen(f"https://micro.mamba.pm/api/micromamba/{platform}/latest").read()
tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2").extract("bin/micromamba", target)
EOF
    then
      MAMBA_ROOT_PREFIX="$ROOT/.venv/mamba" "$ROOT/.venv/bin/micromamba" create -y -q -p "$SYSLIBS" \
        -c conda-forge libgfortran5 liblapack libblas libgomp >/dev/null || rm -rf "$SYSLIBS"
      rm -rf "$ROOT/.venv/mamba/pkgs"
      # shellcheck source=/dev/null
      . "$ROOT/to_show/simulator/system_libs.sh"
    fi
  fi
  if ! ipopt_runs; then
    echo "      Install them, then run ./setup.sh again:"
    echo "        Debian, Ubuntu:  sudo apt-get install -y libgfortran5 liblapack3 libblas3 libgomp1"
    echo "        Fedora, RHEL:    sudo dnf install -y libgfortran lapack blas libgomp"
    exit 1
  fi
fi
if ! ipopt_runs; then
  echo "      IPOPT does not run; see the messages above"
  exit 1
fi
echo "      IPOPT runs"
echo "$PY" > "$ROOT/to_show/simulator/python_path_posix.txt"

if [ "$CHECK" = 1 ]; then
  echo "[3/3] Checking WaterTAP: both models are built and solve one operating point each (about two minutes)"
  "$PY" -B "$ROOT/to_show/simulator/server.py" --check
fi
echo
echo "Setup complete. ./start_demo.sh starts the simulator and opens the page (--no-browser on a machine without one)."
