"""One-command launcher: starts the Vite frontend and the WebSocket backend, then opens the browser."""

from __future__ import annotations

import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from typing import List, Optional

from rcds.models.config import PROJECT_ROOT
from rcds.models.logger import get_logger

logger = get_logger("rcds.launcher")

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

VITE_PORT = 5173
VITE_HOST = "127.0.0.1"
VITE_URL = f"http://{VITE_HOST}:{VITE_PORT}/"

BACKEND_READY_MARK = "RCDS_BACKEND_READY"

_VITE_URL_RE = re.compile(r"(https?://(?:localhost|127\.0\.0\.1|\[::1\]):\d+)/?")

# Readiness is decided by probing the port, never by parsing Vite output.
def _port_is_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """
    Probe whether a TCP connection to host:port succeeds.

    This is the only readiness criterion for the frontend - Vite stdout is
    never parsed for it, because its output varies with Vite version, terminal
    and buffering (colour codes, clear-screen sequences, TUI, npm.cmd wrapper)
    while "the port accepts a connection" is an objective fact.
    """
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def _npm_executable() -> Optional[str]:

    for name in (("npm.cmd", "npm.exe", "npm") if os.name == "nt" else ("npm",)):
        path = shutil.which(name)
        if path:
            return path
    return None

def _node_executable() -> Optional[str]:
    for name in (("node.exe", "node") if os.name == "nt" else ("node",)):
        path = shutil.which(name)
        if path:
            return path
    return None

def _popen(cmd: List[str], cwd: str, **kwargs) -> subprocess.Popen:

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["FORCE_COLOR"] = "0"
    env["CI"] = "1"
    return subprocess.Popen(
        cmd, cwd=cwd, env=env,
        # DEVNULL keeps Vite's interactive TUI from holding its stdout pipe open.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        bufsize=1, **kwargs
    )

class _OutputPump:
    def __init__(self, proc: subprocess.Popen, prefix: str,
                 echo: bool = True) -> None:
        self.proc = proc
        self.prefix = prefix
        self.echo = echo
        self.queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self.history: List[str] = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self.proc.stdout is not None
        try:
            for raw in self.proc.stdout:
                line = raw.rstrip("\n")
                if not line:
                    continue
                self.history.append(line)
                if len(self.history) > 400:
                    del self.history[:100]
                self.queue.put(line)
                if self.echo:
                    print(f"{self.prefix} {line}", flush=True)
        except Exception:
            pass
        finally:

            self.queue.put(None)

    def wait_for(self, predicate, timeout: float,
                 on_tick=None) -> Optional[str]:

        deadline = time.time() + timeout
        last_tick = time.time()
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                line = self.queue.get(timeout=min(0.5, remaining))
            except queue.Empty:
                if on_tick is not None and time.time() - last_tick >= 1.0:
                    last_tick = time.time()
                    on_tick()
                continue
            if line is None:
                return None
            if predicate(line):
                return line

    def tail(self, n: int = 25) -> List[str]:
        return self.history[-n:]

_ERROR_PATTERNS = (
    "already in use",
    "EADDRINUSE",
    "error when starting",
    "Error:",
    "error:",
    "not found",
    "No such file",
    "Missing script",
    "Traceback (most recent call last)",
)

def _first_error_line(history: List[str]) -> Optional[str]:
    for pat in _ERROR_PATTERNS:
        for line in history:
            if pat in line:
                return line.strip()
    return None

def launch(num_agvs: int, num_tasks: int, port: int, host: str,
           open_browser: bool = True, speed: float = 1.0,
           seed: int = 42, real_api: bool = False,
           model_server: Optional[str] = None,
           skip_install_check: bool = False) -> int:
    """
    Launch frontend and backend together; returns the process exit code.
    """
    print("=" * 74)
    print("  RCDS  Risk-Responsive Coordinated Dispatch Simulation  "
          "one-command launch")
    print("=" * 74)

    node = _node_executable()
    npm = _npm_executable()
    if not node or not npm:
        print("\n[error] Node.js / npm not found.")
        print("        The frontend is a React + Vite project and needs "
              "Node.js (>= 18).")
        print("        Download: https://nodejs.org/")
        print("\n        To run the backend only (no 3D frontend), use:")
        print(f"         python run.py online -n {num_agvs} --tasks {num_tasks}")
        return 1
    print(f"  Node  : {node}")
    print(f"  npm   : {npm}")

    if not os.path.isdir(FRONTEND_DIR):
        print(f"\n[error] frontend directory not found: {FRONTEND_DIR}")
        return 1

    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not skip_install_check and not os.path.isdir(node_modules):
        print("\n[1/4] first run, installing frontend dependencies "
              "(npm install) ...")
        rc = subprocess.call([npm, "install", "--no-audit", "--no-fund"],
                             cwd=FRONTEND_DIR)
        if rc != 0:
            print(f"\n[error] npm install failed (code={rc})")
            return 1
    else:
        print("\n[1/4] frontend dependencies ready")

    procs: List[subprocess.Popen] = []

    def shutdown(*_args) -> None:
        print("\n[exit] shutting down frontend and backend ...")
        for p in procs:
            if p.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        p.terminate()
                except Exception:
                    pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        print("[exit] done")

    try:
        signal.signal(signal.SIGINT, lambda *a: (shutdown(), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda *a: (shutdown(), sys.exit(0)))
    except (ValueError, AttributeError):
        pass

    print("\n[2/4] starting frontend (Vite dev server) ...")
    frontend_url = VITE_URL

    if _port_is_open(VITE_HOST, VITE_PORT):
        print(f"\n[error] {VITE_HOST}:{VITE_PORT} is already in use, "
              f"cannot start the frontend.")
        print("        Find and stop the process holding it first:")
        print(f"         netstat -ano | findstr :{VITE_PORT}")
        print("         taskkill /F /PID <PID from the last column>")
        print("        Or start the backend only and serve the frontend "
              "elsewhere:")
        print("         python run.py online")
        return 1

    vite = _popen(
        [npm, "run", "dev", "--",
         "--host", VITE_HOST, "--port", str(VITE_PORT),
         "--strictPort", "--clearScreen", "false"],
        cwd=FRONTEND_DIR,
    )
    procs.append(vite)
    vite_pump = _OutputPump(vite, "[web]")

    vite_started = time.time()
    vite_ok = False
    while time.time() - vite_started < 60.0:
        if vite.poll() is not None:
            break
        if _port_is_open(VITE_HOST, VITE_PORT):
            vite_ok = True
            break
        time.sleep(0.25)
        el = time.time() - vite_started
        if int(el) != int(el - 0.25) and int(el) % 5 == 0:
            print(f"  ... waiting for the frontend ({el:.0f}s)", flush=True)

    if not vite_ok:
        real_error = _first_error_line(vite_pump.history)
        if real_error:
            print(f"\n[error] frontend failed to start: {real_error}")
        elif vite.poll() is not None:
            print(f"\n[error] Vite failed to start (code={vite.returncode})")
        else:
            print(f"\n[error] {VITE_HOST}:{VITE_PORT} was not ready within 60s")
        if _port_is_open(VITE_HOST, VITE_PORT):
            print(f"       port {VITE_PORT} is held by another process.")
            print("       Find and stop it first:")
            print(f"         netstat -ano | findstr :{VITE_PORT}")
            print("         taskkill /F /PID <PID from the last column>")
        print("\n  frontend output (last 25 lines):")
        for line in vite_pump.tail(25):
            print(f"    {line}")
        shutdown()
        return 1

    print(f"\n  frontend URL: {frontend_url}  "
          f"({VITE_HOST}:{VITE_PORT} accepts connections)")

    print("\n[3/4] starting backend (A* reactive rescheduling + WebSocket) ...")
    backend_cmd = [
        sys.executable, "-m", "rcds.server",
        "-n", str(num_agvs),
        "--tasks", str(num_tasks),
        "--host", host,
        "--port", str(port),
        "--speed", str(speed),
        "--seed", str(seed),
    ]
    if real_api:
        backend_cmd.append("--real-api")
    if model_server:
        backend_cmd += ["--model-server", model_server]

    backend = _popen(backend_cmd, cwd=PROJECT_ROOT)
    procs.append(backend)
    backend_pump = _OutputPump(backend, "[api]")

    started = time.time()

    def _backend_tick() -> None:
        el = time.time() - started
        print(f"  ... backend still starting ({el:.0f}s)", flush=True)

    ready_line = backend_pump.wait_for(
        lambda ln: BACKEND_READY_MARK in ln,
        timeout=120.0,
        on_tick=_backend_tick,
    )
    if ready_line is None:
        real_error = _first_error_line(backend_pump.history)
        if real_error:
            print(f"\n[error] backend failed to start: {real_error}")
        elif backend.poll() is not None:
            print(f"\n[error] backend failed to start "
                  f"(code={backend.returncode})")
        else:
            print("\n[error] backend was not ready within 120s; check whether "
                  "port 8000 is in use.")
        for line in backend_pump.tail(30):
            print(f"    {line}")
        shutdown()
        return 1

    model_desc = (f"real HTTP {model_server or 'http://127.0.0.1:8800'}"
                  if real_api else "built-in mock detector")
    print("\n[4/4] ready")
    print("=" * 74)
    print(f"  3D frontend : {frontend_url}")
    print(f"  backend     : ws://{host}:{port}")
    print(f"  AGVs / tasks: {num_agvs} / {num_tasks}")
    print(f"  model service: {model_desc}")
    print("=" * 74)
    print("  Press START in the browser to begin the simulation.")
    print("  The six Risk Simulation buttons inject risks at any time:")
    print("    congestion -> path blocked and detour / intrusion -> area paused")
    print("    fire -> task released / failure -> vehicle retired to the yard")
    print("    no helmet -> job point blocked / smoking -> alarm only")
    print("  With Connect API on, the backend polls the model service and")
    print("  discovers risks automatically.")
    print("  Changing the Control Panel values and pressing RESET starts a new "
          "run.")
    print("  Press Ctrl+C to stop every process.")
    print("=" * 74)

    if open_browser:
        try:
            webbrowser.open(frontend_url)
        except Exception:
            pass

    try:
        while True:
            for p, label in ((vite, "frontend"), (backend, "backend")):
                if p.poll() is not None:
                    print(f"\n[{label}] process exited (code={p.returncode}), "
                          f"shutting the other one down ...")
                    shutdown()
                    return p.returncode or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()
        return 0

def launch_from_args(args) -> int:
    return launch(
        num_agvs=args.agvs,
        num_tasks=args.tasks,
        port=args.port,
        host=args.host,
        open_browser=not getattr(args, "no_browser", False),
        speed=getattr(args, "speed", 1.0),
        seed=getattr(args, "seed", 42),
        real_api=getattr(args, "real_api", False),
        model_server=getattr(args, "model_server", None),
    )
