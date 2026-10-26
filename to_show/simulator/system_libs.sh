# Sourced by setup.sh and start_demo.sh: when setup put the solver's system libraries (Fortran
# runtime, LAPACK, BLAS, OpenMP) into .venv/system-libs, on Linux without root, the solver finds
# them through LD_LIBRARY_PATH.
SYSLIBS="${SYSLIBS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.venv/system-libs}"
if [ -d "$SYSLIBS/lib" ]; then
  export LD_LIBRARY_PATH="$SYSLIBS/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
