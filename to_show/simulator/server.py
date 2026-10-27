"""Local WaterTAP simulator service for water_treatment_hmi.html.

    python server.py [port] [--no-browser] [--workers-bsm2=3] [--workers-ro=2]
    python server.py --check

Serves the dashboard at http://127.0.0.1:<port>/ and solves operating points in WaterTAP. If the
service already runs on that port, it only opens the page. --check builds both WaterTAP models,
solves one operating point of each and exits (0 when both solve); setup.bat runs it.

Endpoints:

    GET  /status    {"ready", "warming", "error", "busy", "workers", "queued", "solved", "equations"},
                     each per plant
    POST /simulate   body {"plant": "bsm2"|"ro", "x": {input: value}, "kind": "plant"|"check"}
                     -> {"status": "ok"|"washout"|"failed"|"superseded"|"unavailable",
                         "outputs": {...}, "seconds": s}
    POST /prefetch   body {"plant", "points": [x, ...]}: points the plant is about to reach, nearest
                     first; replaces the previous list and returns at once
    GET  /results?since=n   solutions finished after sequence number n (prefetched ones included):
                     {"seq": last, "results": [{"plant", "x", "status", "outputs", "seconds"}, ...]}

Each plant has a pool of worker processes, each keeping its own WaterTAP model warm, so several
points solve at once. Checks (an OpenNN proposal, the operating points before and after applying it)
go first, in order; then the plant's current point, where a newer one replaces one still waiting
(answered "superseded"), so the simulator follows the operator instead of a backlog; then the
prefetched points. Results are cached; the points already solved for the dashboard (to_show/data)
and in earlier sessions are loaded at start. Every new solve is appended to
to_show/models/<plant>/data/session_simulations_local.csv (not in Git), which
tools/prepare_training.py adds to the training data, as it did session_simulations.csv. Runs in the
environment setup.bat (or setup.sh) creates and listens on 127.0.0.1 only.
"""

import csv
import json
import math
import sys
import threading
import time
import urllib.request
import webbrowser
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TO_SHOW = Path(__file__).resolve().parents[1]
TOY = TO_SHOW.parent
sys.path.insert(0, str(TOY))
sys.path.insert(0, str(TOY / "bsm2_steady"))
PAGE = TO_SHOW / "water_treatment_hmi.html"

INPUTS = {"bsm2": ["do3", "do4", "do5", "recycle", "wastage", "influent", "rain"], "ro": ["salinity", "recovery", "pressure"]}
OUTPUTS = {"bsm2": ["lcow", "sec", "tss", "cod", "tn", "bod5", "nh4", "biogas"],
           "ro": ["lcow", "sec", "permeate_ppm", "flux_out", "flux_avg", "area"]}
# Inputs a page or a stored file may leave out: the dry-weather network has no rain.
OPTIONAL = {"rain": 0.0}


def complete(plant, x):
    """The point with every input of the plant, optional ones at their default."""
    return {v: float(x[v]) if v in x and x[v] not in ("", None) else OPTIONAL[v] for v in INPUTS[plant]}


def upgrade_log(path, columns):
    """Rewrites a session log begun with fewer columns (before the rain input) with the current
    ones: its rows get the default of each missing input. Rows that already have every column
    (appended under the old header) are kept as they are."""
    if not path.exists():
        return
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] == columns:
        return
    header, out = rows[0], []
    for row in rows[1:]:
        if len(row) == len(columns):
            out.append(row)
        else:
            old = dict(zip(header, row))
            out.append([old[c] if c in old else f"{OPTIONAL[c]:.8g}" if c in OPTIONAL else "" for c in columns])
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(out)


# ------------------------------------------------------------------ worker processes

_WORKER = {}


def _init_worker(plant):
    """Builds this process's WaterTAP model (run once per worker process)."""
    from idaes.core.util.model_statistics import number_activated_constraints
    _WORKER["plant"] = plant
    if plant == "bsm2":
        import bsm2_flowsheet as bf
        bf.quiet()
        _WORKER["model"] = bf.Plant()
        _WORKER["equations"] = number_activated_constraints(_WORKER["model"].m)
    else:
        import ro_flowsheet as rf
        rf.quiet()
        _WORKER["rf"] = rf
        _WORKER["solver"] = rf.get_solver()
        _WORKER["equations"] = number_activated_constraints(rf._build(35.0, 0.5, 1.3, _WORKER["solver"]))


def _warm():
    return _WORKER["equations"]


def _quick_bsm2(model, x):
    """The flowsheet's evaluate() without its slow fallbacks: a walk from where this worker's model
    is, then one from the base case. Near nitrifier washout the full fallback chain (walks one input
    at a time, then a solve without the autotroph floor) can take minutes per point, which would
    starve the operator's current point; here such a point fails within seconds instead."""
    x = complete("bsm2", x)
    if model._walk(x):
        return "ok", model.read_outputs()
    model.restore_base()
    if model._walk(x):
        return "ok", model.read_outputs()
    model.restore_base()
    return "failed", None


def _solve(x):
    plant = _WORKER["plant"]
    start = time.time()
    try:
        if plant == "bsm2":
            status, outputs = _quick_bsm2(_WORKER["model"], x)
        else:
            outputs = _WORKER["rf"].evaluate(x["salinity"], x["recovery"], x["pressure"], solver=_WORKER["solver"])
            status = "ok" if outputs else "failed"
    except Exception as error:
        print(f"{plant}: solve raised {type(error).__name__}: {error}", flush=True)
        status, outputs = "failed", None
    outputs = ({k: float(outputs[k]) for k in OUTPUTS[plant] if k in outputs}
               if outputs and status != "failed" else None)
    return {"status": status, "outputs": outputs, "seconds": round(time.time() - start, 2)}


# ------------------------------------------------------------------ one plant's queue and pool

class Job:
    def __init__(self, x, kind):
        self.x, self.kind = x, kind
        self.event = threading.Event()
        self.result = None


class PlantService:
    def __init__(self, plant, workers):
        self.plant, self.workers = plant, workers
        self.ready, self.error, self.equations = False, None, None
        self.solved = 0
        self.cond = threading.Condition()
        self.checks = deque()
        self.plant_job = None
        self.prefetch = []
        self.running = {}
        self.cache = {}
        # Solves of this computer's sessions; session_simulations.csv holds those already used in training.
        self.log_path = TO_SHOW / "models" / plant / "data" / "session_simulations_local.csv"
        self.log_columns = ["time", "status", "seconds"] + INPUTS[plant] + OUTPUTS[plant]
        upgrade_log(self.log_path, self.log_columns)
        self.preload()

    def key(self, x):
        return tuple(f"{float(x[v]):.6g}" for v in INPUTS[self.plant])

    def remember(self, x, status, outputs):
        self.cache[self.key(x)] = {"status": status, "outputs": outputs, "seconds": None}

    def preload(self):
        files = [TO_SHOW / "data" / f"{self.plant}_defaults_verified.csv", TO_SHOW / "data" / f"{self.plant}_optima_verified.csv",
                 TO_SHOW / "data" / f"{self.plant}_paths_verified.csv", TO_SHOW / "data" / f"{self.plant}_rain_optima_verified.csv"]
        for path in files:
            if path.exists():
                with open(path, newline="") as f:
                    for row in csv.DictReader(f):
                        if row.get("status") in ("ok", "washout") and row.get(f"true_{OUTPUTS[self.plant][0]}"):
                            self.remember(complete(self.plant, row), row["status"],
                                          {k: float(row[f"true_{k}"]) for k in OUTPUTS[self.plant]})
        for path in (self.log_path.with_name("session_simulations.csv"), self.log_path):
            if path.exists():
                with open(path, newline="") as f:
                    for row in csv.DictReader(f):
                        if row["status"] in ("ok", "washout"):
                            self.remember(complete(self.plant, row), row["status"],
                                          {k: float(row[k]) for k in OUTPUTS[self.plant]})

    def start(self):
        self.pool = ProcessPoolExecutor(max_workers=self.workers, initializer=_init_worker, initargs=(self.plant,))
        for _ in range(self.workers):
            self.pool.submit(_warm).add_done_callback(self._warmed)
        threading.Thread(target=self._dispatch, daemon=True, name=f"dispatch-{self.plant}").start()

    def _warmed(self, future):
        try:
            equations = future.result()
        except Exception as error:  # the service keeps answering, with this plant unavailable
            with self.cond:
                if not self.ready:
                    self.error = f"{type(error).__name__}: {error}"
            print(f"{self.plant}: a WaterTAP worker failed to start: {error}", flush=True)
            return
        with self.cond:
            first = not self.ready
            self.ready, self.equations = True, equations
            self.cond.notify_all()
        if first:
            print(f"{self.plant}: WaterTAP model ready ({equations} equations, {self.workers} workers)", flush=True)

    def queued(self, key):
        return (any(self.key(j.x) == key for j in self.checks)
                or (self.plant_job is not None and self.key(self.plant_job.x) == key))

    def submit(self, x, kind):
        key = self.key(x)
        cached = self.cache.get(key)
        if cached:
            job = Job(x, kind)
            job.result = cached
            job.event.set()
            return job
        with self.cond:
            if key in self.running:
                return self.running[key]
            for waiting in self.checks:
                if self.key(waiting.x) == key:
                    return waiting
            if self.plant_job is not None and self.key(self.plant_job.x) == key:
                job = self.plant_job
                if kind == "check":  # a check goes first
                    self.plant_job = None
                    self.checks.append(job)
                    self.cond.notify_all()
                return job
            self.prefetch = [p for p in self.prefetch if self.key(p) != key]
            job = Job(x, kind)
            if kind == "check":
                self.checks.append(job)
            else:
                if self.plant_job is not None:
                    self.plant_job.result = {"status": "superseded"}
                    self.plant_job.event.set()
                self.plant_job = job
            self.cond.notify_all()
        return job

    def set_prefetch(self, points):
        with self.cond:
            self.prefetch = [p for p in points if self.key(p) not in self.cache and self.key(p) not in self.running
                             and not self.queued(self.key(p))][:16]
            self.cond.notify_all()
        return len(self.prefetch)

    def prefetch_allowed(self):
        """Points ahead never take the last free worker: it stays for the operator's point."""
        running_ahead = sum(job.kind == "prefetch" for job in self.running.values())
        return bool(self.prefetch) and running_ahead < max(1, self.workers - 1)

    def _dispatch(self):
        while True:
            with self.cond:
                while not (self.ready and len(self.running) < self.workers
                           and (self.checks or self.plant_job is not None or self.prefetch_allowed())):
                    self.cond.wait()
                if self.checks:
                    job = self.checks.popleft()
                elif self.plant_job is not None:
                    job, self.plant_job = self.plant_job, None
                else:
                    job = Job(self.prefetch.pop(0), "prefetch")
                key = self.key(job.x)
                cached = self.cache.get(key)
                if cached:
                    job.result = cached
                    job.event.set()
                    continue
                if key in self.running:  # the same point is already solving: share its answer
                    other = self.running[key]
                    threading.Thread(target=self._share, args=(other, job), daemon=True).start()
                    continue
                self.running[key] = job
            self.pool.submit(_solve, job.x).add_done_callback(lambda future, job=job, key=key: self._done(job, key, future))

    def _share(self, source, job):
        source.event.wait(900)
        job.result = source.result
        job.event.set()

    def _done(self, job, key, future):
        try:
            result = future.result()
        except Exception as error:
            print(f"{self.plant}: worker failed: {error}", flush=True)
            result = {"status": "failed", "outputs": None, "seconds": None}
        with self.cond:
            if result["status"] != "failed":
                self.cache[key] = result
                self.solved += 1
            self.running.pop(key, None)
            self.cond.notify_all()
        FEED.add(self.plant, job.x, result)
        self.log(job.x, result)
        job.result = result
        job.event.set()
        print(f"{self.plant}: {job.kind} {result['status']} in {result['seconds']} s at "
              + ", ".join(f"{v}={job.x[v]:.4g}" for v in INPUTS[self.plant]), flush=True)

    def log(self, x, result):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        with open(self.log_path, "a", newline="") as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(self.log_columns)
            outputs = result["outputs"] or {}
            writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), result["status"], result["seconds"]]
                            + [f"{x[v]:.8g}" for v in INPUTS[self.plant]]
                            + [f"{outputs[k]:.8g}" if k in outputs else "" for k in OUTPUTS[self.plant]])

    def status(self):
        with self.cond:
            return {"ready": self.ready, "warming": not self.ready and self.error is None, "error": self.error,
                    "busy": len(self.running), "workers": self.workers,
                    "queued": len(self.checks) + (self.plant_job is not None) + len(self.prefetch),
                    "solved": self.solved, "equations": self.equations}


class Feed:
    """Every finished solve, numbered, for pages that poll /results."""

    def __init__(self):
        self.lock = threading.Lock()
        self.items = deque(maxlen=500)
        self.seq = 0

    def add(self, plant, x, result):
        with self.lock:
            self.seq += 1
            self.items.append({"seq": self.seq, "plant": plant, "x": x, **result})

    def since(self, seq):
        with self.lock:
            return self.seq, [item for item in self.items if item["seq"] > seq]


FEED = Feed()
SERVICES = {}


# ------------------------------------------------------------------ HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "WaterTAPSimulator/2.0"

    def log_message(self, fmt, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def send_json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html", "/water_treatment_hmi.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/status":
            statuses = {p: s.status() for p, s in SERVICES.items()}
            self.send_json({field: {p: st[field] for p, st in statuses.items()}
                            for field in ("ready", "warming", "error", "busy", "workers", "queued", "solved", "equations")})
        elif url.path == "/results":
            try:
                since = int(parse_qs(url.query).get("since", ["0"])[0])
            except ValueError:
                since = 0
            seq, items = FEED.since(since)
            self.send_json({"seq": seq, "results": items})
        else:
            self.send_json({"error": "not found"}, 404)

    def read_body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def point(self, plant, x):
        point = complete(plant, x)
        if not all(math.isfinite(v) for v in point.values()):
            raise ValueError("inputs must be finite")
        return point

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/simulate", "/prefetch"):
            self.send_json({"error": "not found"}, 404)
            return
        try:
            body = self.read_body()
            plant = body["plant"]
            service = SERVICES[plant]
            if path == "/prefetch":
                points = [self.point(plant, x) for x in body.get("points", [])[:32]]
            else:
                x = self.point(plant, body["x"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self.send_json({"status": "bad request", "error": str(error)}, 400)
            return
        if not service.ready:
            self.send_json({"status": "unavailable"}, 503)
            return
        if path == "/prefetch":
            self.send_json({"queued": service.set_prefetch(points)})
            return
        job = service.submit(x, "check" if body.get("kind") == "check" else "plant")
        job.event.wait(900)
        self.send_json(job.result or {"status": "timeout"})


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A page closed while its request waited for WaterTAP: nothing to answer.
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


CHECK_POINTS = {
    "ro": {"salinity": 35.0, "recovery": 0.45, "pressure": 60.0},
    "bsm2": {"do3": 1.7, "do4": 2.0, "do5": 1.0, "recycle": 0.6, "wastage": 0.015, "influent": 20648.0},
}


def self_check():
    """Builds each WaterTAP model in this process and solves one operating point with it."""
    passed = True
    for plant, x in CHECK_POINTS.items():
        start = time.time()
        try:
            _init_worker(plant)
            result = _solve(x)
        except Exception as error:
            result = {"status": f"error ({type(error).__name__}: {error})", "outputs": None}
        ok = result["status"] == "ok"
        passed &= ok
        shown = ", ".join(f"{k} {v:.4g}" for k, v in (result["outputs"] or {}).items())
        print(f"{plant}: {'solved' if ok else result['status']} in {time.time() - start:.0f} s"
              + (f" ({shown})" if shown else ""), flush=True)
    print("WaterTAP check passed." if passed else "WaterTAP check FAILED.", flush=True)
    return 0 if passed else 1


def running_here(port):
    """True if this service already answers on the port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as response:
            return "ready" in json.loads(response.read())
    except Exception:
        return False


def main():
    if "--check" in sys.argv:
        sys.exit(self_check())
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    options = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    port = int(args[0]) if args else 8765
    url = f"http://127.0.0.1:{port}/"
    browser = "--no-browser" not in sys.argv
    if running_here(port):
        print(f"The WaterTAP simulator already runs on {url}", flush=True)
        if browser:
            webbrowser.open(url)
        return
    workers = {"bsm2": int(options.get("workers-bsm2", 3)), "ro": int(options.get("workers-ro", 2))}
    for plant in ("ro", "bsm2"):
        SERVICES[plant] = PlantService(plant, workers[plant])
    try:
        server = Server(("127.0.0.1", port), Handler)
    except OSError as error:
        print(f"Port {port} is taken by another program ({error}). Close it, or start this service on "
              f"another port: python server.py <port> (the page looks for port 8765).", flush=True)
        sys.exit(1)
    for service in SERVICES.values():
        service.start()
    print(f"WaterTAP simulator service on {url}", flush=True)
    print(f"The desalination models are ready in seconds; the wastewater models take a minute or two "
          f"({workers['bsm2']} wastewater and {workers['ro']} desalination workers). "
          f"Close this window to stop the simulator.", flush=True)
    if browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
