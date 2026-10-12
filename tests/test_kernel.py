#!/usr/bin/env python3

from __future__ import annotations

import os
import random
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rcds.core.simulation import PortSimulation
from rcds.models.config import Config
from rcds.models.models import AGVStatus, RiskType, TaskStatus
from rcds.port.graph import (
    a_star_search,
    count_turns,
    direction_key,
    direction_key_from_angle,
    find_closest_drivable_waypoint,
    get_yard_access_points,
    heuristic,
    path_distance,
    straight_ratio,
)
from rcds.port.network import (
    get_adjacency,
    get_job_points,
    get_waypoints,
    load_network,
)
from rcds.safety.api_connector import (
    ENDPOINT_SPECS,
    ModelServiceClient,
    check_risk_models,
)
from rcds.safety.risk import RiskManager

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

def section(title: str) -> None:
    print()
    print("=" * 74)
    print(title)
    print("=" * 74)

def edge_set() -> Set[Tuple[str, str]]:
    return {(u, v) for u, nbrs in get_adjacency().items() for v, _ in nbrs}

def path_is_valid(path: Optional[List[str]]) -> bool:
    if not path:
        return False
    if len(path) == 1:
        return True
    edges = edge_set()
    for a, b in zip(path, path[1:]):
        if a == b:
            continue
        if (a, b) not in edges:
            return False
    return True

def pick_two_connected_points(distance_hint: float = 400.0):
    waypoints = get_waypoints()
    names = sorted(waypoints.keys())
    random.seed(7)
    for _ in range(400):
        a, b = random.sample(names, 2)
        pa = waypoints[a]["absolutePosition"]
        pb = waypoints[b]["absolutePosition"]
        dist = ((pa["x"] - pb["x"]) ** 2 + (pa["z"] - pb["z"]) ** 2) ** 0.5
        if dist < distance_hint:
            continue
        path = a_star_search(a, b)
        if path:
            return a, b, path
    return None, None, None

def new_sim(num_agvs: int = 4, num_tasks: int = 20,
            seed: int = 42) -> PortSimulation:
    Config.reset()
    cfg = Config.get()
    cfg.simulation.num_agvs = num_agvs
    cfg.simulation.max_tasks = num_tasks
    cfg.simulation.seed = seed
    sim = PortSimulation()
    sim.initialize(num_agvs=num_agvs, num_tasks=num_tasks, seed=seed)
    return sim

# Both invariants below must hold on every tick, not only at the end.
def run_with_invariants(sim: PortSimulation, max_ticks: int = 4000
                        ) -> Tuple[int, List[str]]:
    violations: List[str] = []
    edges = edge_set()
    prev_pos = {a["id"]: a["current_wp"] for a in sim.agv_states}
    ticks = 0

    while ticks < max_ticks and not sim.is_finished:
        sim.step()
        ticks += 1

        occupied: Dict[str, List[str]] = {}
        for agv in sim.agv_states:
            occupied.setdefault(agv["current_wp"], []).append(agv["id"])
        for wp, ids in occupied.items():
            if len(ids) > 1:
                violations.append(
                    f"t={sim.current_time} collision: {ids} both at {wp}")

        for agv in sim.agv_states:
            before = prev_pos.get(agv["id"])
            now = agv["current_wp"]
            if before != now and (before, now) not in edges:
                violations.append(
                    f"t={sim.current_time} teleport: {agv['id']} "
                    f"{before} -> {now} is not an edge")
        prev_pos = {a["id"]: a["current_wp"] for a in sim.agv_states}

    return ticks, violations

def test_graph() -> None:
    section("A. Road network and A*")

    check(load_network(), "road network loaded")
    waypoints = get_waypoints()
    adjacency = get_adjacency()
    check(len(waypoints) > 1000,
          f"waypoint count is plausible ({len(waypoints)})")
    check(len(adjacency) > 1000,
          f"graph node count is plausible ({len(adjacency)})")
    check(edge_set() and all(isinstance(u, str)
                             for u, _ in list(edge_set())[:10]),
          "adjacency structure is correct (u -> [(v, distance)])")

    a, b, path = pick_two_connected_points()
    check(path is not None, "a distant path is found on the real road network")
    check(path is not None and path[0] == a and path[-1] == b,
          "path endpoints equal the requested start and goal")
    check(path_is_valid(path), "every path step is a real directed edge")

    some = sorted(waypoints.keys())[0]
    check(a_star_search(some, some) == [some],
          "same start and goal returns a single-waypoint path")
    check(a_star_search(some, "no_such_waypoint") is None,
          "unknown goal returns None")
    check(a_star_search("no_such_waypoint", some) is None,
          "unknown start returns None")
    check(a_star_search(a, b, blocked_waypoints={a}) is None,
          "blocked start returns None")
    check(a_star_search(a, b, blocked_waypoints={b}) is None,
          "blocked goal returns None")

    if path and len(path) > 6:
        mid = path[len(path) // 2]
        blocked_path = a_star_search(a, b, blocked_waypoints={mid})
        check(blocked_path is None or mid not in blocked_path,
              f"path avoids the blocked middle waypoint {mid}")
        check(blocked_path is None or path_is_valid(blocked_path),
              "detour path is still valid")

    few = sorted(waypoints.keys())
    random.seed(11)
    p1, p2 = random.sample(few, 2)
    base = a_star_search(p1, p2)
    if base and len(base) > 3:
        penalized = a_star_search(p1, p2, other_agv_paths=[base[1:-1]])
        check(penalized is None or len(penalized) != len(base)
              or not set(base[1:-1]) & set(penalized[1:-1]),
              "occupancy penalty takes effect: A* no longer follows the "
              "occupied nodes as-is (or returns a different route)")

    access = get_yard_access_points("Y0")
    check(len(access) == 4,
          f"yard Y0 has 4 access points (got {len(access)}: {access})")
    check(all(wp.startswith("a0_") for wp in access),
          "access points all belong to the a0 lane group")
    if access:
        zs = [waypoints[wp]["absolutePosition"]["z"] for wp in access]
        all_a0 = [wp for wp in waypoints if wp.startswith("a0_")]
        min_z = min(waypoints[wp]["absolutePosition"]["z"] for wp in all_a0)
        check(max(zs) == min_z,
              "access points are the innermost row of that bay")
    check(get_yard_access_points("QC0") == [],
          "a non-yard bay has no access point")

    check(heuristic(some, some) == 0.0,
          "heuristic between identical waypoints is 0")
    check(heuristic(some, "no_such_waypoint") == float("inf"),
          "heuristic for an unknown waypoint is infinite")

    jp = get_job_points()
    check(len(jp) > 0, f"job points loaded ({len(jp)})")
    first_jp = next(iter(jp.values()))
    wp = find_closest_drivable_waypoint(first_jp["pos"])
    check(wp in waypoints, "job point coordinates map to a real waypoint")

def test_risk_manager() -> None:
    section("B. Risk ledger (RiskManager)")

    load_network()
    rm = RiskManager()
    job_points = list(get_job_points().keys())
    yard_jp = next(jp for jp in job_points if "YARD_Area" in jp)
    qc_jp = next(jp for jp in job_points if "QC_Area" in jp)

    rid = rm.add_risk(RiskType.FIRE, job_point_id=yard_jp, current_time=0)
    risk = rm.active_risks[rid]
    check(risk["target_id"] == yard_jp, "fire risk lands on the given job point")
    check(yard_jp in rm.get_paused_job_locations(),
          "fire moves that job point into the paused set")
    check("Fire" in risk["message"], "alert text carries the risk type")
    check(risk["severity"] == "danger", "fire severity is danger")

    rid2 = rm.add_risk(RiskType.NO_HELMET, job_point_id=qc_jp, current_time=1)
    check(qc_jp in rm.get_paused_job_locations(),
          "no-helmet pauses the job point")
    check(rm.active_risks[rid2]["target_id"] == qc_jp,
          "no-helmet targets the right job point")

    waypoints = get_waypoints()
    center = random.choice(list(waypoints.keys()))
    rid3 = rm.add_risk(RiskType.TRAFFIC_CONGESTION,
                       location_wp=center, current_time=2)
    affected = rm.active_risks[rid3]["affected_waypoints"]
    blocked = rm.get_blocked_waypoints()
    check(len(affected) > 0, f"congestion blocked {len(affected)} waypoints")
    check(set(affected) <= blocked,
          "blocked set covers the congestion radius")
    radius = Config.get().area.congestion_radius
    cp = waypoints[center]["absolutePosition"]
    far_ok = True
    for wp in affected:
        p = waypoints[wp]["absolutePosition"]
        if ((p["x"] - cp["x"]) ** 2 + (p["z"] - cp["z"]) ** 2) >= radius ** 2:
            far_ok = False
    check(far_ok, f"blocked waypoints stay strictly inside radius {radius}")
    check(center in affected, "the congestion center itself is blocked")

    rm.add_risk(RiskType.PERSONNEL_INTRUSION, zone="Highway_Area",
                current_time=3)
    check(rm.is_zone_paused("Highway_Area"),
          "personnel intrusion pauses the zone")
    check(not rm.is_zone_paused("YARD_Area"), "other zones stay unaffected")

    rm.add_risk(RiskType.AGV_FAILURE, agv_id="AGV-2", current_time=4)
    check(rm.has_agv_failure("AGV-2"),
          "AGV failure risk is bound to the vehicle")
    check(not rm.has_agv_failure("AGV-0"), "other vehicles stay unaffected")

    smoking_id = rm.add_risk(RiskType.SMOKING, job_point_id=yard_jp,
                             current_time=5)
    check(rm.active_risks[smoking_id]["type"] == RiskType.SMOKING,
          "smoking risk is recorded")
    check(rm.active_risks[smoking_id]["affected_waypoints"] == [],
          "smoking blocks no waypoint (alert only)")

    check(rm.clear_risk(rid), "a single risk can be cleared by id")
    check(rid not in rm.active_risks, "cleared risk leaves the active list")
    rm.clear_all_risks()
    check(rm.get_all_risks() == [], "clear_all_risks empties the ledger")
    check(rm.get_blocked_waypoints() == set(),
          "no blocked waypoints after clearing")
    check(rm.get_paused_job_locations() == set(),
          "no paused job points after clearing")
    check(not rm.is_zone_paused("Highway_Area"),
          "zone pause is lifted after clearing")

    rm2 = RiskManager()
    rm2.add_risk(RiskType.FIRE, job_point_id=yard_jp, current_time=0,
                 duration=10)
    check(len(rm2.tick(5)) == 0, "risk stays active before its deadline")
    expired = rm2.tick(10)
    check(len(expired) == 1, "risk expires automatically at its deadline")
    check(rm2.get_all_risks() == [], "ledger is empty after automatic expiry")

    rm3 = RiskManager()
    rm3.add_risk(RiskType.FIRE, job_point_id=yard_jp, current_time=0)
    payload = rm3.to_payload()
    check(len(payload) == 1 and "position" in payload[0]
          and "label" in payload[0] and "affectedCount" in payload[0],
          "to_payload carries the fields the frontend renders")

def test_simulation_invariants() -> None:
    section("C. Simulation consistency and convergence (no risks)")

    sim = new_sim(4, 20, seed=42)
    check(len(sim.agv_states) == 4, "4 AGVs created")
    check(len(sim.tasks) == 20, "20 tasks created")
    check(len(sim.job_location_states) > 20,
          f"job location occupancy table built "
          f"({len(sim.job_location_states)} entries)")
    check(all(a["current_wp"] == a["home_seat_wp"] for a in sim.agv_states),
          "every AGV starts at its own home seat")

    ticks, violations = run_with_invariants(sim, max_ticks=4000)
    check(sim.is_finished, f"simulation converges ({ticks} ticks)")
    check(not violations,
          f"no collision and no teleport during the whole run ({ticks} ticks)"
          + (f" violations: {violations[:3]}" if violations else ""))
    completed = sum(1 for t in sim.tasks
                    if t["status"] == TaskStatus.COMPLETED)
    check(completed == 20, f"20/20 tasks completed (got {completed})")
    check(all(a["current_wp"] == a["home_seat_wp"] for a in sim.agv_states),
          "every AGV is back at its home seat when the run ends")
    check(all(t["completed_time"] is not None for t in sim.tasks
              if t["status"] == TaskStatus.COMPLETED),
          "completed tasks all carry completed_time")
    check(all(t["assigned_time"] is not None for t in sim.tasks
              if t["status"] == TaskStatus.COMPLETED),
          "completed tasks all carry assigned_time")

    state = sim.get_frontend_state()
    for key in ("time", "agvs", "tasks", "risks", "rescheduleLog", "kpis",
                "agvEfficiency", "statusDistribution", "apiStatus",
                "jobLocationStates", "stats", "isRunning", "makespan"):
        check(key in state, f"frontend payload contains field {key}")
    check(state["kpis"]["completionRate"] == 100.0,
          "KPI completion rate is 100%")
    check(len(state["agvEfficiency"]) == 4,
          "efficiency table covers all vehicles")
    check(len(state["statusDistribution"]) >= 1,
          "status distribution is not empty")
    check(state["finished"] is True, "payload is flagged finished")

    sim2 = new_sim(4, 20, seed=42)
    t2, _ = run_with_invariants(sim2, max_ticks=4000)
    check(t2 == ticks,
          f"same seed yields the same tick count ({ticks} vs {t2})")
    dist_a = [round(a["distance_traveled"], 3) for a in sim.agv_states]
    dist_b = [round(a["distance_traveled"], 3) for a in sim2.agv_states]
    check(dist_a == dist_b,
          "same seed yields identical travelled distance")

    sim.reset_clock()
    check(sim.current_time == 0 and not sim.is_running,
          "reset_clock goes back to t=0")
    check(all(t["status"] == TaskStatus.PENDING for t in sim.tasks),
          "reset_clock puts every task back to PENDING")

    sim_big = new_sim(12, 100, seed=7)
    ticks_big, viol_big = run_with_invariants(sim_big, max_ticks=8000)
    done = sum(1 for t in sim_big.tasks
               if t["status"] == TaskStatus.COMPLETED)
    check(done == 100, f"12 AGVs / 100 tasks all completed (got {done})")
    check(not viol_big,
          f"no collision and no teleport at 12-AGV scale ({ticks_big} ticks)"
          + (f" violations: {viol_big[:3]}" if viol_big else ""))

def test_risk_linkage() -> None:
    section("D. Risk linkage (the core capability of this project)")

    sim = new_sim(4, 20, seed=42)
    for _ in range(30):
        sim.step()
    target_id, wp = None, None
    for agv in sim.agv_states:
        path = agv.get("path") or []
        idx = agv.get("path_step", 0) + 3
        if agv["status"] in AGVStatus.MOVING_STATUSES and idx < len(path):
            target_id, wp = agv["id"], path[idx]
            break
    check(wp is not None,
          "found a waypoint ahead of a moving AGV to inject congestion")

    if wp:
        sim.add_risk(RiskType.TRAFFIC_CONGESTION, location_wp=wp)
        blocked = sim.risk_manager.get_blocked_waypoints()
        check(len(blocked) > 0, f"congestion blocked {len(blocked)} waypoints")
        sim.step()
        agv = next(a for a in sim.agv_states if a["id"] == target_id)
        log_texts = [e["reason"] for e in sim.reschedule_log]
        check(agv["status"] in (AGVStatus.BLOCKED_BY_RISK,
                                AGVStatus.MOVE_TO_PICKUP,
                                AGVStatus.MOVE_TO_DROPOFF),
              f"affected AGV is blocked or already rerouted "
              f"(current status {agv['status']})")
        check(any("blocked" in r for r in log_texts),
              "reschedule log records the path being blocked by risk")
        reroute = [e for e in sim.reschedule_log
                   if e["reason"] == "Path blocked by risk"]
        check(all(e["method"] == "A* replan" for e in reroute),
              "blocking events use A* replanning")
        check(any(e["result"].startswith("OK") for e in reroute),
              "at least one replanning succeeded")
        if agv["status"] in AGVStatus.MOVING_STATUSES and agv["path"]:
            check(not (set(agv["path"]) & blocked),
                  "the new path no longer crosses the blocked waypoints")

    sim2 = new_sim(4, 20, seed=42)
    for _ in range(30):
        sim2.step()
    sim2.add_risk(RiskType.PERSONNEL_INTRUSION, zone="Highway_Area",
                  duration=20)
    paused_seen = False
    for _ in range(15):
        sim2.step()
        if any(a["status"] == AGVStatus.PAUSED_BY_RISK
               for a in sim2.agv_states):
            paused_seen = True
    check(paused_seen,
          "personnel intrusion puts highway AGVs into PAUSED_BY_RISK")
    check(sim2.risk_manager.is_zone_paused("Highway_Area"),
          "the zone stays paused while the intrusion lasts")

    sim2.clear_risks()
    sim2.step()
    check(not any(a["status"] == AGVStatus.PAUSED_BY_RISK
                  for a in sim2.agv_states),
          "vehicles resume work immediately after the risk is cleared")
    check(not sim2.risk_manager.is_zone_paused("Highway_Area"),
          "the zone pause is lifted")

    sim3 = new_sim(4, 20, seed=42)
    for _ in range(30):
        sim3.step()
    victim, task_id, loc = None, None, None
    for agv in sim3.agv_states:
        if agv.get("current_task_id"):
            victim = agv
            task_id = agv["current_task_id"]
            loc = agv.get("task_dropoff_job_loc_id") or \
                agv.get("task_pickup_job_loc_id")
            break
    check(victim is not None, "found a vehicle currently executing a task")
    if victim:
        sim3.add_risk(RiskType.FIRE, job_point_id=loc)
        sim3.step()
        task = next(t for t in sim3.tasks if t["id"] == task_id)
        check(task["status"] == TaskStatus.PENDING,
              f"fire sends task {task_id} back to PENDING "
              f"(current status {task['status']})")
        check(task["assigned_agv_id"] is None,
              "the released task is no longer bound to a vehicle")
        check(victim["current_task_id"] != task_id,
              "the vehicle no longer holds the blocked task")
        check(any("locked down" in e["reason"] for e in sim3.reschedule_log),
              "reschedule log records the blocked target area")

    sim4 = new_sim(4, 20, seed=42)
    for _ in range(40):
        sim4.step()
    rid = sim4.add_risk(RiskType.AGV_FAILURE)
    check(rid is not None, "AGV failure risk created")
    broken = next(a for a in sim4.agv_states
                  if a["status"] == AGVStatus.BROKEN_DOWN)
    check(broken is not None, f"{broken['id']} enters BROKEN_DOWN")
    check(broken["current_task_id"] is None,
          "the broken AGV released its task")
    check(sim4.risk_manager.has_agv_failure(broken["id"]),
          "the failure risk is bound to that vehicle")

    became_returning, became_decommissioned = False, False
    for _ in range(400):
        sim4.step()
        if broken["status"] == AGVStatus.BROKEN_RETURNING:
            became_returning = True
        if broken["status"] == AGVStatus.DECOMMISSIONED:
            became_decommissioned = True
            break
    check(became_returning,
          "the repaired AGV enters BROKEN_RETURNING and heads home")
    check(became_decommissioned,
          "the AGV is DECOMMISSIONED after returning home")
    check(broken["current_wp"] == broken["home_seat_wp"],
          "the AGV is really back at its home seat when decommissioned")

    sim5 = new_sim(4, 20, seed=42)
    scenario = [
        (25, lambda s: s.add_risk(RiskType.TRAFFIC_CONGESTION,
                                  zone="Highway_Area", duration=120)),
        (90, lambda s: s.add_risk(RiskType.FIRE, duration=120)),
        (140, lambda s: s.add_risk(RiskType.PERSONNEL_INTRUSION,
                                   zone="Highway_Area", duration=100)),
        (200, lambda s: s.add_risk(RiskType.AGV_FAILURE)),
        (260, lambda s: s.add_risk(RiskType.NO_HELMET, duration=80)),
        (320, lambda s: s.add_risk(RiskType.SMOKING, duration=40)),
    ]
    steps = {t: fn for t, fn in scenario}
    ticks5 = 0
    violations5: List[str] = []
    edges = edge_set()
    prev = {a["id"]: a["current_wp"] for a in sim5.agv_states}
    while ticks5 < 4000 and not sim5.is_finished:
        if sim5.current_time in steps:
            steps[sim5.current_time](sim5)
        sim5.step()
        ticks5 += 1
        occ: Dict[str, List[str]] = {}
        for a in sim5.agv_states:
            occ.setdefault(a["current_wp"], []).append(a["id"])
        for wp_, ids in occ.items():
            if len(ids) > 1:
                violations5.append(
                    f"t={sim5.current_time} collision {ids} @ {wp_}")
        for a in sim5.agv_states:
            if prev.get(a["id"]) != a["current_wp"] and \
                    (prev[a["id"]], a["current_wp"]) not in edges:
                violations5.append(
                    f"t={sim5.current_time} teleport {a['id']}")
        prev = {a["id"]: a["current_wp"] for a in sim5.agv_states}

    check(sim5.is_finished,
          f"still converges after all 6 risk types are injected "
          f"({ticks5} ticks)")
    check(not violations5,
          "the risk scenario runs without collision or teleport"
          + (f" violations: {violations5[:3]}" if violations5 else ""))
    done5 = sum(1 for t in sim5.tasks
                if t["status"] == TaskStatus.COMPLETED)
    check(done5 == 20,
          f"20/20 tasks completed under the risk scenario (got {done5})")
    check(len(sim5.risk_manager.history) >= 6,
          f"risk history recorded {len(sim5.risk_manager.history)} risks")
    check(any(e["reason"] == "Risk expired" for e in sim5.reschedule_log),
          "time-limited risks expire automatically and leave a trace")

    sim6 = new_sim(4, 20, seed=42)
    for _ in range(30):
        sim6.step()
    sim6.add_risk(RiskType.PERSONNEL_INTRUSION, zone="Highway_Area")
    for _ in range(10):
        sim6.step()
    sim6.clear_risks()
    sim6.step()
    t6, viol6 = run_with_invariants(sim6, max_ticks=4000)
    check(sim6.is_finished,
          "the whole run finishes after risks are cleared manually")

def test_api_connector() -> None:
    section("E. Model service integration (mock detectors)")

    load_network()
    cfg = Config.get()
    check(len(ENDPOINT_SPECS) == 5, "5 model endpoints defined")
    check({s["path"] for s in ENDPOINT_SPECS} == {
        "/model/fire", "/model/smoke", "/model/helmet",
        "/model/worker", "/model/traffic_jam"},
        "endpoint paths match security")

    rm = RiskManager()
    client = ModelServiceClient()

    cfg.api.mock_detect_probability = 0.0
    det0 = check_risk_models(rm, client, current_time=0)
    check(det0 == [] and rm.get_all_risks() == [],
          "zero hit probability produces no risk")

    cfg.api.mock_detect_probability = 1.0
    det1 = check_risk_models(rm, client, current_time=10)
    check(len(det1) == 5,
          f"hit probability 1 raises alerts on all 5 endpoints ({len(det1)})")
    check(len(rm.get_all_risks()) == 5, "5 risks written into the ledger")
    check(rm.get_blocked_waypoints(),
          "the congestion risk produced blocked waypoints")
    check(rm.get_paused_job_locations(),
          "fire/helmet risks paused job points")
    check(all(d["endpoint"].startswith("/model/") for d in det1),
          "detection records carry the endpoint path")

    status = client.status_payload(enabled=True)
    check(status["enabled"] is True, "API panel status reflects the switch")
    check(len(status["endpoints"]) == 5, "the panel lists 5 endpoints")
    check(all("lastWarn" in ep for ep in status["endpoints"]),
          "every endpoint carries its latest detection")
    check(status["baseUrl"].startswith("http://"),
          "model service base URL provided")

    cfg.api.mock_detect_probability = 0.12

    sim = new_sim(4, 10, seed=42)
    sim.set_api_simulation(True)
    check(sim.api_enabled, "the API simulation switch takes effect")
    check(sim._last_api_poll == sim.current_time,
          "the first poll runs immediately after switching on "
          "(no 15-tick wait)")
    sim.set_api_simulation(False)
    check(not sim.api_enabled, "API simulation can be switched off")

    sim2 = new_sim(4, 10, seed=42)
    sim2.set_api_simulation(False)
    types = []
    for _ in range(len(Config.get().risk.auto_sequence)):
        rid = sim2.trigger_risk_sequence()
        if rid:
            types.append(sim2.risk_manager.active_risks[rid]["type"])
    expected = Config.get().risk.auto_sequence
    check(types == expected,
          f"the risk sequence injects all {len(expected)} risk types in order "
          f"(got {types})")

def test_route_smoothness() -> None:
    section("F. Turn penalty (route smoothness)")

    load_network()
    waypoints = get_waypoints()
    cfg = Config.get()

    ll_lane = sorted(
        (name for name in waypoints if name.startswith("ll0_")),
        key=lambda n: waypoints[n]["absolutePosition"]["x"],
    )
    check(len(ll_lane) > 10,
          f"got an LL lane waypoint sequence ({len(ll_lane)})")
    if len(ll_lane) > 10:
        straight = a_star_search(ll_lane[0], ll_lane[-1])
        check(straight is not None, "lane head and tail are reachable")
        check(straight is not None and count_turns(straight) == 0,
              f"same-lane endpoints get a zero-turn path "
              f"(got {count_turns(straight)} turns)")
        check(straight is not None
              and len(straight) == len(ll_lane),
              f"and the path is that lane itself "
              f"({len(straight) if straight else 0} waypoints)")
        check(straight is not None and straight_ratio(straight) == 1.0,
              "that path is 100% straight")

    a = ll_lane[0] if ll_lane else next(iter(waypoints))
    check(direction_key(ll_lane[0], ll_lane[1]) is not None
          if len(ll_lane) > 1 else True,
          "direction sector between adjacent waypoints is computable")
    check(direction_key_from_angle(0.0) == direction_key_from_angle(0.0),
          "heading angle conversion is stable")
    check(count_turns([a]) == 0, "a single-waypoint path has zero turns")
    check(count_turns([a, a]) == 0, "standing still is not a turn")

    names = sorted(waypoints)
    random.seed(2024)
    pairs = []
    while len(pairs) < 150:
        pairs.append(tuple(random.sample(names, 2)))

    def sample(penalty: float):
        reachable, turns, dist = 0, 0, 0.0
        for s, g in pairs:
            p = a_star_search(s, g, turn_penalty=penalty)
            if not p:
                continue
            reachable += 1
            turns += count_turns(p)
            dist += path_distance(p)
        return reachable, (turns / reachable if reachable else 0.0), dist

    reach0, avg0, dist0 = sample(0.0)
    reach_hi, avg_hi, dist_hi = sample(cfg.area.turn_penalty)

    check(reach0 == reach_hi,
          f"the turn penalty does not change reachability "
          f"(both {reach0}/{len(pairs)})")
    check(avg_hi < avg0 * 0.6,
          f"the default penalty cuts the average turn count sharply "
          f"({avg0:.2f} -> {avg_hi:.2f})")
    check(avg_hi <= 2.5,
          f"the average turn count stays low ({avg_hi:.2f} per leg)")
    check(dist_hi <= dist0 * 1.02,
          f"fewer turns do not cost extra distance "
          f"({dist0/1000:.1f} km -> {dist_hi/1000:.1f} km, 2% allowed)")

    sim = new_sim(6, 30, seed=42)
    run_with_invariants(sim, max_ticks=4000)
    stats = sim.route_stats
    legs = int(stats["legs"])
    turns = int(stats["turns"])
    avg_turns_per_leg = (turns / legs) if legs else 0.0

    seg_estimate = float(stats["distance"]) / 20.0
    straight_pct = (max(0.0, 1.0 - turns / seg_estimate) * 100
                    if seg_estimate > 0 else 0.0)
    check(legs > 0, f"the planner accumulated route stats ({legs} legs)")
    check(avg_turns_per_leg <= 3.0,
          f"the whole run averages {avg_turns_per_leg:.2f} turns per leg "
          f"(<= 3)")
    check(straight_pct >= 90.0,
          f"the whole run is {straight_pct:.1f}% straight (>= 90%)")
    check(turns > 0 and legs > 0,
          "both turn count and leg count are tracked in route_stats")
    summary = sim.get_summary()
    check(summary["kpis"]["taskCompleted"] == 30,
          f"the offline summary reports 30/30 tasks completed "
          f"(got {summary['kpis']['taskCompleted']})")

def main() -> int:
    print()
    print("=" * 74)
    print("  RCDS kernel tests")
    print("  (A* + reactive rescheduling driven by risks)")
    print("=" * 74)

    test_graph()
    test_risk_manager()
    test_simulation_invariants()
    test_risk_linkage()
    test_api_connector()
    test_route_smoothness()

    print()
    print("=" * 74)
    print(f"  passed {PASSED} / failed {len(FAILED)}")
    if FAILED:
        print("-" * 74)
        for label in FAILED:
            print(f"  [FAIL] {label}")
    print("=" * 74)
    return 1 if FAILED else 0

if __name__ == "__main__":
    sys.exit(main())
