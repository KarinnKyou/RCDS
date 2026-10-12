"""WebSocket service exposing the simulation state to the frontend."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from rcds.models.config import Config
from rcds.models.logger import get_logger

logger = get_logger("rcds.server")

# The launcher waits for this line on stdout before opening the browser.
READY_MARK = "RCDS_BACKEND_READY"

class SimulationServer:
    def __init__(self, sim, host: str, port: int) -> None:
        self.sim = sim
        self.host = host
        self.port = port
        self.connections: List[Any] = []
        self._loop_task: Optional[asyncio.Task] = None

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        dead = []
        for ws in list(self.connections):
            try:
                await ws.send(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            if ws in self.connections:
                self.connections.remove(ws)

    async def push_state(self) -> None:
        await self.broadcast({"type": "state_update",
                              "data": self.sim.get_frontend_state()})

    async def simulation_loop(self) -> None:
        try:
            while self.sim.is_running:
                self.sim.step()
                await self.push_state()
                if self.sim.is_finished:
                    self.sim.is_running = False
                    await self.broadcast({"type": "finished",
                                          "data": self.sim.get_summary()})
                    break
                await asyncio.sleep(max(0.02, 0.5 / self.sim.speed))
        except asyncio.CancelledError:
            raise
        except Exception:
            import traceback
            traceback.print_exc()
            await self.broadcast({"type": "error", "data": {
                "code": "SIMULATION_ERROR",
                "message": "simulation step failed, see the backend console",
            }})

    def cancel_loop(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
        self._loop_task = None

    def _start_loop(self) -> None:
        self.cancel_loop()
        self._loop_task = asyncio.create_task(self.simulation_loop())

    async def reset(self, params: Dict[str, Any]) -> None:
        self.cancel_loop()
        self.sim.is_running = False
        try:
            self.sim.initialize(
                num_agvs=params.get("numAgvs"),
                num_tasks=params.get("numTasks"),
                seed=params.get("seed"),
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            await self.broadcast({"type": "error", "data": {
                "code": "RESET_FAILED",
                "message": f"reset failed: {exc}",
            }})
            return

        await self._push_static()
        await self.push_state()

    async def _push_static(self) -> None:
        await self.broadcast({"type": "network",
                              "data": self.sim.get_network_data()})
        await self.broadcast({"type": "jobPoints",
                              "data": self.sim.get_job_points_data()})

    async def handle_message(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return

        action = message.get("action")
        params = message.get("params") or {}

        if action == "start":
            if not self.sim.is_planned:
                await self.reset(params)
            if self.sim.is_planned and not self.sim.is_running \
                    and not self.sim.is_finished:
                self.sim.is_running = True
                self._start_loop()

        elif action == "pause":
            self.sim.is_running = False
            self.cancel_loop()
            await self.push_state()

        elif action == "reset":
            await self.reset(params)

        elif action == "step":
            self.sim.step()
            await self.push_state()

        elif action == "setSpeed":
            self.sim.speed = max(0.1, min(10.0,
                                          float(params.get("speed", 1.0))))
            await self.broadcast({"type": "speed",
                                  "data": {"speed": self.sim.speed}})

        elif action == "addRisk":
            risk_type = params.get("riskType")
            if risk_type:
                self.sim.add_risk(
                    risk_type,
                    zone=params.get("zone"),
                    job_point_id=params.get("jobPointId"),
                    agv_id=params.get("agvId"),
                    source=params.get("source", "manual"),
                    duration=params.get("duration"),
                    location_wp=params.get("locationWp"),
                )
                await self.push_state()

        elif action == "clearRisks":
            self.sim.clear_risks()
            await self.push_state()

        elif action == "setApiSimulation":
            self.sim.set_api_simulation(bool(params.get("enabled")))
            await self.push_state()

        elif action == "triggerRiskSequence":
            self.sim.trigger_risk_sequence()
            await self.push_state()

    async def handler(self, ws) -> None:
        self.connections.append(ws)
        try:
            await self.broadcast_one(ws, "network",
                                     self.sim.get_network_data())
            await self.broadcast_one(ws, "jobPoints",
                                     self.sim.get_job_points_data())
            await self.broadcast_one(ws, "state_update",
                                     self.sim.get_frontend_state())

            async for raw in ws:
                await self.handle_message(raw)
        except Exception:
            pass
        finally:
            if ws in self.connections:
                self.connections.remove(ws)

    @staticmethod
    async def broadcast_one(ws, msg_type: str, data: Any) -> None:
        await ws.send(json.dumps({"type": msg_type, "data": data},
                                 ensure_ascii=False))

    async def serve(self) -> None:
        try:
            import websockets
        except ImportError:
            print("missing dependency: run  pip install websockets")
            raise SystemExit(1)

        async with websockets.serve(self.handler, self.host, self.port,
                                    ping_interval=30, ping_timeout=30,
                                    max_size=64 * 1024 * 1024):
            print("=" * 72)
            print("RCDS  Risk-Responsive Coordinated Dispatch Simulation  "
                  f"WebSocket  ws://{self.host}:{self.port}")
            print(f"  AGVs / tasks    : {self.sim.num_agvs} / "
                  f"{self.sim.num_tasks}")
            print("  Path planning   : A* (reactive incremental rescheduling)")
            print("  Risk linkage    : fire/smoking/helmet/intrusion/"
                  "congestion/failure")
            model_backend = ("real HTTP" if self.sim.cfg.api.use_real_api
                             else "built-in mock detector")
            print(f"  Model service   : {model_backend}")
            print(f"  Initial speed   : {self.sim.speed}x")
            print("=" * 72)

            print(READY_MARK, flush=True)
            await asyncio.Future()

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m rcds.server",
        description="RCDS WebSocket service",
    )
    p.add_argument("-n", "--agvs", type=int, default=5,
                   help="number of AGVs")
    p.add_argument("--tasks", type=int, default=100, help="total tasks")
    p.add_argument("--host", type=str, default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-ticks", type=int, default=20000)
    p.add_argument("--real-api", action="store_true",
                   help="really call the model service (default: built-in "
                        "mock detector)")
    p.add_argument("--model-server", type=str, default=None,
                   help="model service base URL, e.g. http://127.0.0.1:8800")
    return p

def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    cfg = Config.apply_args(args)

    from rcds.core.simulation import PortSimulation

    sim = PortSimulation()
    sim.speed = max(0.1, min(10.0, args.speed))

    print("[BOOT] initializing the scenario ...")
    try:
        sim.initialize(num_agvs=args.agvs,
                       num_tasks=args.tasks,
                       seed=cfg.simulation.seed)
    except Exception:
        import traceback
        traceback.print_exc()
        return 1

    server = SimulationServer(sim, args.host, args.port)
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("\nServer stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())
