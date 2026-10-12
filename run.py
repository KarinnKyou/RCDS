#!/usr/bin/env python3
"""Unified entry point: launcher, backend-only mode, headless simulation and risk scenario."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcds.models import Config  # noqa: E402

def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-n", "--agvs", type=int, default=5,
                   help="number of AGVs")
    p.add_argument("--tasks", type=int, default=100, help="total tasks")
    p.add_argument("--seed", type=int, default=42, help="random seed")
    p.add_argument("--max-ticks", type=int, default=20000,
                   help="max ticks per run")
    p.add_argument("--real-api", action="store_true",
                   help="call the model service over real HTTP "
                        "(default: built-in mock detector)")
    p.add_argument("--model-server", type=str, default=None,
                   help="model service base URL, e.g. http://127.0.0.1:8800")

def _add_server_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", type=str, default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--speed", type=float, default=1.0,
                   help="initial playback speed")

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcds",
        description="RCDS - port AGV risk-responsive dispatch rehearsal "
                    "(A* + reactive rescheduling)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_web = sub.add_parser(
        "web", help="launch backend + frontend 3D view in one command "
                    "(default action)")
    _add_common_args(p_web)
    _add_server_args(p_web)
    p_web.add_argument("--no-browser", action="store_true",
                       help="do not open the browser automatically")

    p_online = sub.add_parser(
        "online", help="start the backend WebSocket service only "
                       "(start the frontend yourself)")
    _add_common_args(p_online)
    _add_server_args(p_online)

    p_sim = sub.add_parser("sim", help="headless offline simulation (no risks)")
    _add_common_args(p_sim)

    p_risk = sub.add_parser(
        "risk", help="run the risk linkage scenario offline and print the "
                     "effect of every risk type")
    _add_common_args(p_risk)

    _add_common_args(parser)
    _add_server_args(parser)
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the browser automatically")

    return parser

def run_web(args) -> int:
    from rcds.launcher import launch

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

def run_online(args) -> int:
    from rcds.server import main as server_main

    argv = [
        "-n", str(args.agvs),
        "--tasks", str(args.tasks),
        "--host", args.host,
        "--port", str(args.port),
        "--speed", str(args.speed),
        "--seed", str(args.seed),
        "--max-ticks", str(args.max_ticks),
    ]
    if args.real_api:
        argv.append("--real-api")
    if args.model_server:
        argv += ["--model-server", args.model_server]
    return server_main(argv)

def _build_sim(args):
    from rcds.core.simulation import PortSimulation

    Config.apply_args(args)
    sim = PortSimulation()
    sim.initialize(num_agvs=args.agvs,
                   num_tasks=args.tasks,
                   seed=Config.get().simulation.seed)
    return sim

def _print_summary(sim, title: str, wall: float) -> None:
    summary = sim.get_summary()
    kpis = summary["kpis"]
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(f"  Sim time        : {summary['time']} ticks  "
          f"(wall clock {wall:.2f} s)")
    print(f"  AGVs / tasks    : {summary['agvs']} / {summary['tasks']}")
    print(f"  Tasks completed : {kpis['taskCompleted']} / {kpis['taskTotal']}"
          f"   completion rate {kpis['completionRate']}%")
    print(f"  Utilization     : {kpis['utilizationRate']}%"
          f"   blocked {kpis['blockedRate']}%")
    print(f"  Avg task time   : {kpis['avgTaskDuration']} ticks")
    print(f"  Total mileage   : {kpis['totalDistanceKm']} km")
    print(f"  Avg battery     : {kpis['avgBattery']}%")
    print(f"  Risks injected / active : "
          f"{summary['riskTotal']} / {summary['riskActive']}")
    if summary["riskByType"]:
        detail = "  ".join(f"{k}={v}" for k, v in
                           sorted(summary["riskByType"].items()))
        print(f"  Risk breakdown  : {detail}")
    print(f"  Reschedule log  : {summary['rescheduleEvents']} entries")
    if not summary["finished"]:
        print("  ! did not converge (hit the max-ticks limit); "
              "some risk may never expire")
    print("=" * 72)

def run_sim(args) -> int:
    import time as _time

    sim = _build_sim(args)
    t0 = _time.time()
    sim.run_to_completion(args.max_ticks)
    _print_summary(sim, "OFFLINE SIMULATION SUMMARY (no risks)",
                   _time.time() - t0)
    return 0

# Rows are (tick, action, params, note); actions: RISK / CONGEST / CLEAR.
SCENARIO_STEPS = [
    (25, "CONGEST", {}, "congestion pinned on the route of an AGV in transit -> A* detour"),
    (90, "RISK_ON_TASK", {"riskType": "FIRE", "duration": 200},
     "fire pinned on the job point of an active task -> that task is released"),
    (140, "RISK", {"riskType": "PERSONNEL_INTRUSION", "duration": 150},
     "intrusion -> vehicles inside the highway area become PAUSED_BY_RISK"),
    (200, "RISK", {"riskType": "AGV_FAILURE"},
     "AGV failure -> task released + wait for recovery + return and retire"),
    (260, "RISK_ON_TASK", {"riskType": "NO_HELMET", "duration": 120},
     "no helmet pinned on the job point of an active task -> task blocked"),
    (320, "RISK", {"riskType": "SMOKING", "duration": 60},
     "smoking alert -> alarm only, dispatch untouched"),
    (420, "CLEAR", {}, "manual clear of remaining risks -> fleet resumes work"),
]

NOTABLE_TRANSITIONS = {
    "PAUSED_BY_RISK": "paused by risk",
    "BLOCKED_BY_RISK": "path blocked",
    "BROKEN_DOWN": "AGV failure",
    "BROKEN_RETURNING": "failure returning",
    "DECOMMISSIONED": "decommissioned",
}

def _pick_congestion_waypoint(sim, lookahead: int = 3):
    for agv in sim.agv_states:
        path = agv.get("path") or []
        idx = agv.get("path_step", 0) + lookahead
        if agv["status"] in ("MOVE_TO_PICKUP", "MOVE_TO_DROPOFF",
                             "RETURNING") and idx < len(path):
            return agv["id"], path[idx]
    return None, None

def _pick_active_task_location(sim):
    for agv in sim.agv_states:
        if not agv.get("current_task_id"):
            continue
        loc = agv.get("task_dropoff_job_loc_id") or \
            agv.get("task_pickup_job_loc_id")
        if loc:
            return agv["id"], agv["current_task_id"], loc
    return None, None, None

def run_risk(args) -> int:
    import time as _time

    sim = _build_sim(args)
    print()
    print("=" * 72)
    print("RISK LINKAGE SCENARIO")
    print("=" * 72)

    steps = {t: (action, params, note)
             for t, action, params, note in SCENARIO_STEPS}
    log_cursor = 0
    t0 = _time.time()
    cleared = False

    while sim.current_time < args.max_ticks and not sim.is_finished:
        tick = sim.current_time
        if tick in steps:
            action, params, note = steps[tick]
            if action == "CONGEST":
                agv_id, wp = _pick_congestion_waypoint(sim)
                if wp:
                    sim.add_risk("TRAFFIC_CONGESTION", location_wp=wp,
                                 duration=180)
                    risk = list(sim.risk_manager.active_risks.values())[-1]
                    print(f"\n[t={tick:>4}] injected TRAFFIC_CONGESTION   {note}")
                    print(f"          target = {agv_id} waypoint ahead {wp}"
                          f", blocked {len(risk['affected_waypoints'])} waypoints")
                else:
                    print(f"\n[t={tick:>4}] skipped congestion injection "
                          f"(no AGV was in transit)")
            elif action in ("RISK", "RISK_ON_TASK"):
                job_point = None
                target_desc = ""
                if action == "RISK_ON_TASK":
                    agv_id, task_id, loc = _pick_active_task_location(sim)
                    if loc:
                        job_point = loc
                        target_desc = (f" (pinned on {task_id} job point "
                                       f"{loc} of {agv_id})")
                    else:
                        print(f"\n[t={tick:>4}] skipped (no task in transit)")
                        sim.step()
                        continue
                risk_id = sim.add_risk(params["riskType"],
                                       job_point_id=job_point,
                                       duration=params.get("duration"))
                risk = (sim.risk_manager.active_risks.get(risk_id, {})
                        if risk_id else {})
                print(f"\n[t={tick:>4}] injected {params['riskType']:<20} {note}"
                      f"{target_desc}")
                print(f"          location: {risk.get('location_wp')} "
                      f"({risk.get('zone') or risk.get('target_id')})"
                      f"  blocked waypoints {len(risk.get('affected_waypoints', []))}")
            elif action == "CLEAR":
                sim.clear_risks()
                cleared = True
                print(f"\n[t={tick:>4}] cleared all risks         {note}")

        prev_status = {a["id"]: a["status"] for a in sim.agv_states}
        sim.step()

        for agv in sim.agv_states:
            before = prev_status.get(agv["id"])
            if before != agv["status"] and agv["status"] in NOTABLE_TRANSITIONS:
                print(f"           ~ {agv['id']:<6} {before} -> "
                      f"{agv['status']} ({NOTABLE_TRANSITIONS[agv['status']]})")

        new_entries = sim.reschedule_log[log_cursor:]
        log_cursor = len(sim.reschedule_log)
        for entry in new_entries:
            print(f"           . [{entry['time']:>4}] {entry['agvId']:<6} "
                  f"{entry['reason']:<14} {entry['method']:<12} "
                  f"{entry['result']}")

    if sim.current_time >= args.max_ticks and not sim.is_finished:
        print(f"\n[warning] max-ticks={args.max_ticks} reached without "
              f"convergence"
              + (" (expected while the scenario leaves risks active)"
                 if not cleared else ""))
        pending = [t["id"] for t in sim.tasks
                   if t["status"] not in ("COMPLETED", "FAILED")]
        print(f"        unfinished tasks {len(pending)}: {pending[:12]}")
        for agv in sim.agv_states:
            if agv["status"] not in ("IDLE", "DECOMMISSIONED") or \
                    agv["current_wp"] != agv["home_seat_wp"]:
                print(f"        stuck: {agv['id']} {agv['status']} "
                      f"@ {agv['current_wp']} (home seat {agv['home_seat_wp']}) "
                      f"task {agv.get('current_task_id')}")

    _print_summary(sim, "RISK LINKAGE SUMMARY", _time.time() - t0)

    print("\nAGV status sample (end of scenario):")
    for agv in sim.agv_states:
        print(f"  {agv['id']:<6} {agv['status']:<18} "
              f"battery {agv['battery']:5.1f}%  mileage {agv['distance_traveled']:8.1f} m"
              f"  task {agv.get('current_task_id') or '-'}")

    print("\nReschedule log (last 24 entries):")
    for entry in sim.reschedule_log[-24:]:
        print(f"  [{entry['time']:>4}] {entry['agvId']:<6} | "
              f"{entry['reason']:<14} | method: {entry['method']:<12} | "
              f"result: {entry['result']}")
    print()
    return 0

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "web":
        return run_web(args)
    if args.command == "online":
        return run_online(args)
    if args.command == "sim":
        return run_sim(args)
    if args.command == "risk":
        return run_risk(args)

    return run_web(args)

if __name__ == "__main__":
    sys.exit(main())
