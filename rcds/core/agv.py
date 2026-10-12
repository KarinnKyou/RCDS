from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from rcds.models.config import Config
from rcds.models.logger import get_logger
from rcds.models.models import AGVStatus
from rcds.port.network import calculate_distance, get_waypoints

logger = get_logger("rcds.core.agv")

def initialize_agv_states(num_agvs: int) -> List[Dict[str, Any]]:
    waypoints = get_waypoints()
    if not waypoints:
        return []

    all_wps = list(waypoints.keys())
    ll_candidates = [wp for wp in all_wps if wp.startswith("ll")]
    b_candidates = [wp for wp in all_wps if wp.startswith("b")]

    spawn_points: List[str] = []

    random.shuffle(ll_candidates)
    spawn_points.extend(ll_candidates[:num_agvs])

    if len(spawn_points) < num_agvs:
        random.shuffle(b_candidates)
        occupied_lanes = set()
        for wp in b_candidates:
            if len(spawn_points) >= num_agvs:
                break
            lane_id = wp.split("_")[0]
            if lane_id not in occupied_lanes:
                spawn_points.append(wp)
                occupied_lanes.add(lane_id)

    if len(spawn_points) < num_agvs:
        remaining = num_agvs - len(spawn_points)
        fallback = [wp for wp in all_wps
                    if not wp.startswith("sl") and wp not in spawn_points]
        spawn_points.extend(
            random.sample(fallback, min(remaining, len(fallback))))

    return [create_agv_state(i, spawn_points[i])
            for i in range(min(num_agvs, len(spawn_points)))]

def create_agv_state(index: int, home_wp: str) -> Dict[str, Any]:
    return {
        "id": f"AGV-{index}",
        "home_seat_wp": home_wp,
        "current_wp": home_wp,
        "rotation": math.pi / 2,
        "status": AGVStatus.IDLE,
        "prev_status_before_blocked": None,
        "path": [],
        "path_step": 0,
        "current_task_id": None,
        "task_pickup_job_loc_id": None,
        "task_dropoff_job_loc_id": None,
        "target_drivable_wp": None,
        "locked_yard_access_wp": None,
        "history_path": [home_wp] if home_wp else [],
        "battery": 100.0,
        "handover_timer": 0,
        "recovery_time": -1,
        "stall_ticks": 0,
        "wait_ticks": 0,
        "blocked_by_wp": None,
        "blocked_by_agv": None,
        "distance_traveled": 0.0,
        "time_idle": 0,
        "time_moving_empty": 0,
        "time_moving_loaded": 0,
        "time_blocked": 0,
        "log": ["Simulation started, idle."],
    }

def update_agv_physics(agv: Dict[str, Any]) -> None:
    status = agv["status"]
    if status == AGVStatus.IDLE:
        agv["time_idle"] += 1
    elif status == AGVStatus.MOVE_TO_DROPOFF:
        agv["time_moving_loaded"] += 1
    elif status in (AGVStatus.MOVE_TO_PICKUP, AGVStatus.RETURNING,
                    AGVStatus.BROKEN_RETURNING):
        agv["time_moving_empty"] += 1
    elif status in (AGVStatus.BLOCKED_BY_RISK, AGVStatus.PAUSED_BY_RISK,
                    AGVStatus.WAIT_FOR_PICKUP, AGVStatus.WAIT_FOR_DROPOFF):
        agv["time_blocked"] += 1

def advance_agv_one_step(agv: Dict[str, Any]) -> bool:
    path = agv.get("path") or []
    step = agv.get("path_step", 0)
    if step >= len(path) - 1:
        return False

    prev_wp = agv["current_wp"]
    next_wp = path[step + 1]
    waypoints = get_waypoints()

    segment_m = 0.0
    if prev_wp in waypoints and next_wp in waypoints:
        pos_prev = waypoints[prev_wp]["absolutePosition"]
        pos_next = waypoints[next_wp]["absolutePosition"]
        segment_m = calculate_distance(pos_prev, pos_next)
        agv["distance_traveled"] = agv.get("distance_traveled", 0.0) + segment_m
        set_heading_from_move(agv, pos_prev, pos_next)

    agv["path_step"] = step + 1
    agv["current_wp"] = next_wp

    # Battery drains per metre driven, so a parked vehicle cannot mask a risk.
    range_km = Config.get().simulation.battery_range_km
    agv["battery"] = max(
        0.0, agv["battery"] - segment_m / 1000.0 / range_km * 100.0)

    history = agv["history_path"]
    if not history or history[-1] != next_wp:
        history.append(next_wp)
        if len(history) > 120:
            del history[:-120]

    return True

def set_heading_from_move(agv: Dict[str, Any], pos_prev: Dict[str, float],
                          pos_next: Dict[str, float]) -> None:
    dx = pos_next["x"] - pos_prev["x"]
    dz = pos_next["z"] - pos_prev["z"]
    if abs(dx) < 0.1 and abs(dz) < 0.1:
        return
    agv["rotation"] = math.atan2(dx, dz)

def log_agv(agv: Dict[str, Any], current_time: int, text: str) -> None:
    agv["log"].append(f"T{current_time}: {text}")
    if len(agv["log"]) > 60:
        del agv["log"][:-60]
