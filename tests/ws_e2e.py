#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
except ImportError:
    print("missing dependency: pip install websockets")
    raise SystemExit(1)

PASSED = 0
FAILED: List[str] = []

def check(condition: bool, label: str) -> None:
    global PASSED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED.append(label)
        print(f"  [FAIL] {label}")

class Client:

    def __init__(self, ws) -> None:
        self.ws = ws
        self.messages: Dict[str, Any] = {}
        self.counts: Dict[str, int] = {}

    async def _store(self, msg: Dict[str, Any]) -> None:
        mtype = msg.get("type")
        self.counts[mtype] = self.counts.get(mtype, 0) + 1
        self.messages[mtype] = msg.get("data")

    async def recv_until(self, msg_type: str, timeout: float = 10.0,
                         predicate=None) -> Optional[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                return None
            msg = json.loads(raw)
            await self._store(msg)
            if msg.get("type") == msg_type and (
                    predicate is None or predicate(msg.get("data"))):
                return msg.get("data")

    async def drain(self, seconds: float = 1.5) -> None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                return
            await self._store(json.loads(raw))

    async def send(self, action: str, **params) -> None:
        await self.ws.send(json.dumps({"action": action, "params": params}))

async def run(host: str, port: int) -> int:
    url = f"ws://{host}:{port}"
    print()
    print("=" * 74)
    print(f"  RCDS WebSocket end-to-end test  ({url})")
    print("=" * 74)

    try:
        ws = await asyncio.wait_for(websockets.connect(url), timeout=10)
    except Exception as exc:
        print(f"\n[ERROR] cannot connect to the backend {url}: {exc}")
        print("        start the backend first: "
              "python run.py online -n 4 --tasks 20")
        return 1

    async with ws:
        client = Client(ws)

        print("\n1. Connection handshake")
        network = await client.recv_until("network", timeout=15)
        node_count = len(network.get("nodes", [])) if network else 0
        edge_count = len(network.get("edges", [])) if network else 0
        check(node_count > 1000, f"road network received ({node_count} nodes)")
        check(edge_count > 1000, f"edge list received ({edge_count} edges)")
        job_points = await client.recv_until("jobPoints", timeout=10)
        check(bool(job_points),
              f"job points received ({len(job_points or {})})")
        state = await client.recv_until("state_update", timeout=10)
        check(state is not None, "first state frame received")
        if state:
            for key in ("time", "agvs", "tasks", "risks", "rescheduleLog",
                        "kpis", "agvEfficiency", "statusDistribution",
                        "apiStatus", "jobLocationStates", "stats"):
                check(key in state, f"state_update contains field {key}")
            ids = [a["id"] for a in state["agvs"]]
            check(len(ids) == len(set(ids)) and len(ids) > 0,
                  f"AGV list is non-empty and unique ({len(ids)})")
            check(state["kpis"]["taskTotal"] == len(state["tasks"]),
                  f"KPI task total matches the task list "
                  f"({len(state['tasks'])})")
            check(state["stats"]["totalTasks"] == len(state["tasks"]),
                  "stats task total matches the task list")
            check(state["kpis"]["taskCompleted"]
                  == sum(1 for t in state["tasks"]
                         if t["status"] == "COMPLETED"),
                  "KPI completed count matches the task statuses")
            check(len(state["agvEfficiency"]) == len(ids),
                  "efficiency table covers all vehicles")
            check(len(state["apiStatus"]["endpoints"]) == 5,
                  "API panel lists 5 model endpoints")
            check(all("statusLabel" in a for a in state["agvs"]),
                  "every AGV carries a status label")

        print("\n2. start / clock advance")
        await client.send("reset", numAgvs=4, numTasks=20)
        fresh = await client.recv_until(
            "state_update", timeout=25,
            predicate=lambda d: len(d.get("agvs", [])) == 4 and d["time"] <= 2)
        check(fresh is not None,
              "reset to the test baseline (4 AGVs / 20 tasks / t<=2)")

        await client.send("start")
        first = await client.recv_until(
            "state_update", timeout=15, predicate=lambda d: d["time"] >= 3)
        check(first is not None, "ticks advance after start")
        t_a = first["time"] if first else 0
        positions_a = ({a["id"]: a["currentWp"] for a in first["agvs"]}
                       if first else {})

        later = await client.recv_until(
            "state_update", timeout=25,
            predicate=lambda d: d["time"] >= t_a + 15)
        check(later is not None, "the clock keeps advancing")
        if later and first:
            positions_b = {a["id"]: a["currentWp"] for a in later["agvs"]}
            moved = sum(1 for aid in positions_a
                        if positions_a[aid] != positions_b.get(aid))
            check(moved > 0, f"{moved} AGVs really moved")
            check(later["kpis"]["time"] == later["time"],
                  "KPI time matches the message time")
            check(later["kpis"]["completionRate"] >= 0,
                  "completion rate field is usable")

        print("\n3. pause")
        await client.send("pause")
        paused = await client.recv_until("state_update", timeout=10)
        check(paused is not None and paused["isRunning"] is False,
              "isRunning=false after pause")
        t_pause = paused["time"] if paused else 0
        await client.drain(1.2)
        still = client.messages.get("state_update")
        check(still is None or still["time"] == t_pause,
              f"the clock is frozen after pause (t={t_pause})")

        print("\n4. risk injection (6 types)")
        await client.send("start")
        await client.recv_until("state_update", timeout=10)

        for risk_type in ["FIRE", "SMOKING", "NO_HELMET",
                          "PERSONNEL_INTRUSION", "TRAFFIC_CONGESTION"]:
            await client.send("addRisk", riskType=risk_type)
            data = await client.recv_until(
                "state_update", timeout=10,
                predicate=lambda d, rt=risk_type: any(
                    r["type"] == rt for r in d.get("risks", [])))
            check(data is not None,
                  f"{risk_type} appears in state_update after injection")

        await client.send("addRisk", riskType="AGV_FAILURE")
        broken = await client.recv_until(
            "state_update", timeout=12,
            predicate=lambda d: any(
                a["status"] in ("BROKEN_DOWN", "BROKEN_RETURNING")
                for a in d.get("agvs", [])))
        check(broken is not None, "AGV_FAILURE puts a vehicle into a failure state")
        if broken:
            check(any(r["type"] == "AGV_FAILURE" for r in broken["risks"]),
                  "the failure risk appears in the risk list")
            check(any(a["broken"] for a in broken["agvs"]),
                  "the AGV payload carries the broken flag "
                  "(used for the failure icon)")
            released = [t for t in broken["tasks"]
                        if t["status"] == "PENDING"]
            check(bool(released),
                  "the failure moves a task back to the PENDING queue")
        check(client.messages.get("state_update", {})
              .get("rescheduleLog") is not None,
              "the reschedule log is pushed with the state")

        latest = client.messages.get("state_update") or {}
        target_wp, target_agv = None, None
        for agv in latest.get("agvs", []):
            path = agv.get("path") or []
            if agv["status"] in ("MOVE_TO_PICKUP", "MOVE_TO_DROPOFF",
                                 "RETURNING") and len(path) > 3:
                target_wp, target_agv = path[3], agv["id"]
                break
        check(target_wp is not None,
              "found a waypoint ahead of a moving AGV to inject congestion")
        # Congestion must sit on the next waypoints of a moving AGV, or no reroute is observable.
        await client.send("addRisk", riskType="TRAFFIC_CONGESTION",
                          locationWp=target_wp)
        blocked = await client.recv_until(
            "state_update", timeout=25,
            predicate=lambda d: any(
                a["status"] == "BLOCKED_BY_RISK" for a in d.get("agvs", []))
            or any("blocked" in e["reason"] for e in d.get("rescheduleLog", [])))
        check(blocked is not None,
              f"congestion on the next waypoint {target_wp} of {target_agv} "
              f"triggers a blocking/reroute event")
        if blocked:
            events = [e for e in blocked["rescheduleLog"]
                      if e["reason"] == "Path blocked by risk"]
            check(bool(events),
                  "the reschedule log records the path being blocked by risk")
            check(all(e["method"] == "A* replan" for e in events),
                  "blocking events use A* replanning")
            check(any(e["result"].startswith("OK") for e in events),
                  "at least one replanning succeeded")
            congest = [r for r in blocked["risks"]
                       if r["type"] == "TRAFFIC_CONGESTION"]
            check(bool(congest) and congest[0]["affectedCount"] > 0,
                  f"congestion blocked "
                  f"{congest[0]['affectedCount'] if congest else 0} waypoints")

        print("\n5. clearRisks")
        await client.send("clearRisks")
        cleared = await client.recv_until(
            "state_update", timeout=10,
            predicate=lambda d: len(d.get("risks", [])) == 0)
        check(cleared is not None, "the risk list is empty after clearRisks")

        print("\n6. setApiSimulation")
        await client.send("setApiSimulation", enabled=True)
        api_on = await client.recv_until(
            "state_update", timeout=10,
            predicate=lambda d: d.get("apiStatus", {}).get("enabled") is True)
        check(api_on is not None,
              "the API simulation switch is on and pushed to the frontend")
        if api_on:
            check(any(ep.get("lastTime") is not None
                      for ep in api_on["apiStatus"]["endpoints"]),
                  "a poll result is available right after switching on")
        await client.send("setApiSimulation", enabled=False)
        api_off = await client.recv_until(
            "state_update", timeout=10,
            predicate=lambda d: d.get("apiStatus", {}).get("enabled") is False)
        check(api_off is not None, "API simulation can be switched off")

        print("\n7. reset")
        await client.send("reset", numAgvs=3, numTasks=12)
        reset = await client.recv_until(
            "state_update", timeout=25,
            predicate=lambda d: len(d.get("agvs", [])) == 3
            and d["time"] <= 2)
        check(reset is not None,
              "reset takes effect (AGV count and clock are rebuilt)")
        if reset:
            check(reset["kpis"]["taskTotal"] == 12,
                  "the task count is rebuilt from the new parameters")
            check(len(reset["risks"]) == 0, "reset cleared the risks")
            check(all(a["status"] == "IDLE" for a in reset["agvs"]),
                  "all vehicles are IDLE after reset")
            check(all(not a["broken"] for a in reset["agvs"]),
                  "failure flags are cleared after reset")

        print("\n8. step")
        await client.drain(0.6)
        t_before = client.messages["state_update"]["time"]
        await client.send("step")
        stepped = await client.recv_until(
            "state_update", timeout=10,
            predicate=lambda d: d["time"] == t_before + 1)
        check(stepped is not None, "step advances exactly one tick")

    print()
    print("=" * 74)
    print(f"  passed {PASSED} / failed {len(FAILED)}")
    if FAILED:
        print("-" * 74)
        for label in FAILED:
            print(f"  [FAIL] {label}")
    print("=" * 74)
    return 1 if FAILED else 0

def main() -> int:
    parser = argparse.ArgumentParser(prog="tests/ws_e2e.py")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        return 130

if __name__ == "__main__":
    sys.exit(main())
