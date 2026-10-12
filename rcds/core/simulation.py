from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Set, Tuple

from rcds.core.agv import (
    advance_agv_one_step,
    initialize_agv_states,
    log_agv,
    update_agv_physics,
)
from rcds.core.metrics import (
    STATUS_LABELS,
    agv_efficiency,
    compute_kpis,
    status_distribution,
)
from rcds.core.tasks import TaskManager
from rcds.models.config import Config
from rcds.models.logger import get_logger
from rcds.models.models import AGVStatus, RiskType, TaskStatus
from rcds.port.graph import (
    a_star_search,
    count_turns,
    direction_key,
    find_closest_drivable_waypoint,
    get_yard_access_points,
    heuristic,
    path_distance,
)
from rcds.port.network import (
    get_job_points,
    get_waypoints,
    get_waypoints_in_zone,
    is_loaded,
    load_network,
)
from rcds.safety.api_connector import ModelServiceClient, check_risk_models
from rcds.safety.risk import RiskManager

logger = get_logger("rcds.core.simulation")

MAX_LOG_ENTRIES = 300
WAIT_TIMEOUT_TICKS = 40
WAIT_LOG_INTERVAL = 20

def initialize_job_location_states() -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    for jp_id in get_job_points():
        states[jp_id] = {"status": "FREE", "agv_id": None, "type": "job_point"}
        if "YARD_Area" in jp_id:
            bay = get_job_points()[jp_id].get("bay")
            for access_wp in get_yard_access_points(str(bay)):
                states[access_wp] = {"status": "FREE", "agv_id": None,
                                     "type": "access_wp"}
    return states

class PortSimulation:

    def __init__(self) -> None:
        self.cfg = Config.get()

        self.num_agvs: int = self.cfg.simulation.num_agvs
        self.num_tasks: int = self.cfg.simulation.max_tasks
        self.seed: int = self.cfg.simulation.seed

        self.agv_states: List[Dict[str, Any]] = []
        self.tasks: List[Dict[str, Any]] = []
        self.job_location_states: Dict[str, Dict[str, Any]] = {}

        self.risk_manager = RiskManager()
        self.model_client = ModelServiceClient()
        self.task_manager = TaskManager()

        self.current_time: int = 0
        self.is_running: bool = False
        self.is_planned: bool = False
        self.speed: float = self.cfg.simulation.default_speed

        self.api_enabled: bool = False
        self._sequence_step: int = 0
        self._last_api_poll: int = -1

        self.reschedule_log: List[Dict[str, Any]] = []
        self._log_seq: int = 0
        self._log_cursor: int = 0

        self.route_stats: Dict[str, float] = {
            "legs": 0, "turns": 0, "distance": 0.0, "replans": 0,
        }

    def initialize(self, num_agvs: Optional[int] = None,
                   num_tasks: Optional[int] = None,
                   seed: Optional[int] = None) -> None:
        if num_agvs is not None:
            self.num_agvs = max(1, int(num_agvs))
        if num_tasks is not None:
            self.num_tasks = max(0, int(num_tasks))
        if seed is not None:
            self.seed = int(seed)

        seed = self.seed

        if not is_loaded() and not load_network():
            raise RuntimeError(
                "Failed to load port road network from data/network/*.json")

        random.seed(seed)

        random.seed(seed)
        self.agv_states = initialize_agv_states(self.num_agvs)

        random.seed(seed)
        self.task_manager.reset()
        self.tasks = self.task_manager.generate_tasks(self.num_tasks,
                                                      current_time=0)

        self.job_location_states = initialize_job_location_states()

        self.risk_manager.clear_all_risks()
        self.model_client = ModelServiceClient()
        self.reschedule_log = []
        self._log_seq = 0
        self._log_cursor = 0
        self._sequence_step = 0
        self._last_api_poll = -1
        self.api_enabled = False
        self.route_stats = {"legs": 0, "turns": 0, "distance": 0.0,
                            "replans": 0}

        self.current_time = 0
        self.is_running = False
        self.is_planned = True

        logger.info(
            f"[SIM] ready: {len(self.agv_states)} AGVs x "
            f"{len(self.tasks)} tasks | {len(self.job_location_states)} "
            f"job location slots"
        )

    def reset_clock(self) -> None:
        for agv in self.agv_states:
            home = agv["home_seat_wp"]
            agv.update(
                current_wp=home, status=AGVStatus.IDLE, path=[], path_step=0,
                current_task_id=None, task_pickup_job_loc_id=None,
                task_dropoff_job_loc_id=None, target_drivable_wp=None,
                locked_yard_access_wp=None, prev_status_before_blocked=None,
                history_path=[home], battery=100.0, distance_traveled=0.0,
                handover_timer=0, recovery_time=-1,
                time_idle=0, time_moving_empty=0, time_moving_loaded=0,
                time_blocked=0, log=["Simulation reset."],
            )
        for task in self.tasks:
            task.update(status=TaskStatus.PENDING, assigned_agv_id=None,
                        assigned_time=None, completed_time=None)
        self.job_location_states = initialize_job_location_states()
        self.risk_manager.clear_all_risks()
        self.current_time = 0
        self.is_running = False

    def add_risk(self, risk_type: str, zone: Optional[str] = None,
                 job_point_id: Optional[str] = None,
                 agv_id: Optional[str] = None,
                 source: str = "manual",
                 duration: Optional[int] = None,
                 location_wp: Optional[str] = None) -> Optional[str]:
        if risk_type == RiskType.AGV_FAILURE:
            return self.fail_agv(agv_id, source=source)

        job_points = list(get_job_points().keys())
        if risk_type in (RiskType.FIRE, RiskType.NO_HELMET,
                         RiskType.SMOKING) and not job_point_id \
                and not location_wp:
            if job_points:
                job_point_id = random.choice(job_points)
        if risk_type in (RiskType.PERSONNEL_INTRUSION,
                         RiskType.TRAFFIC_CONGESTION) and not zone \
                and not location_wp:
            zone = self.cfg.area.highway_zone

        risk_id = self.risk_manager.add_risk(
            risk_type, zone=zone, job_point_id=job_point_id,
            current_time=self.current_time, source=source,
            duration=duration, location_wp=location_wp,
        )
        if risk_id:
            risk = self.risk_manager.active_risks[risk_id]
            self._log(current_time=self.current_time, agv_id="SYS",
                      reason="Risk injected",
                      method="Manual" if source == "manual" else "Model service",
                      result=f"{risk['label']} @ {risk['zone'] or risk['target_id']}")
        return risk_id

    def fail_agv(self, agv_id: Optional[str] = None,
                 source: str = "manual") -> Optional[str]:
        working = [a for a in self.agv_states
                   if a["status"] not in (AGVStatus.IDLE,
                                          AGVStatus.BROKEN_DOWN,
                                          AGVStatus.BROKEN_RETURNING,
                                          AGVStatus.DECOMMISSIONED)]
        idle = [a for a in self.agv_states
                if a["status"] not in (AGVStatus.BROKEN_DOWN,
                                       AGVStatus.DECOMMISSIONED)]
        eligible = working or idle
        if not eligible:
            return None

        target = None
        if agv_id:
            target = next((a for a in eligible if a["id"] == agv_id), None)
        if target is None:
            target = random.choice(eligible)

        current_task = self._find_task(target.get("current_task_id"))
        if current_task and current_task["status"] == TaskStatus.ASSIGNED:
            current_task.update(status=TaskStatus.PENDING,
                                assigned_agv_id=None, assigned_time=None)
            self._log(current_time=self.current_time, agv_id=target["id"],
                      reason="AGV failure", method="Task reassigned",
                      result=f"Task {current_task['id']} released")
        self._release_job_locations(target)
        target.update(current_task_id=None, task_pickup_job_loc_id=None,
                      task_dropoff_job_loc_id=None, target_drivable_wp=None,
                      path=[], path_step=0)

        target["status"] = AGVStatus.BROKEN_DOWN
        target["recovery_time"] = -1
        log_agv(target, self.current_time, "AGV failure.")
        risk_id = self.risk_manager.add_risk(
            RiskType.AGV_FAILURE, zone=f"at {target['current_wp']}",
            agv_id=target["id"], location_wp=target["current_wp"],
            current_time=self.current_time, source=source,
        )
        self._log(current_time=self.current_time, agv_id=target["id"],
                  reason="AGV failure", method="Event-triggered",
                  result=f"Awaiting rescue @ {target['current_wp']}")
        return risk_id

    def clear_risks(self) -> None:
        self.risk_manager.clear_all_risks()
        self._sequence_step = 0
        self._log(current_time=self.current_time, agv_id="SYS",
                  reason="Risks cleared", method="Manual", result="All risks cleared")

    def set_api_simulation(self, enabled: bool) -> None:
        self.api_enabled = bool(enabled)
        if self.api_enabled:
            self._last_api_poll = self.current_time - \
                self.cfg.risk.api_poll_ticks
            self._poll_model_service()
        self._log(current_time=self.current_time, agv_id="SYS",
                  reason="Model service connected",
                  method="Model service",
                  result="connected, polling started" if enabled else "disconnected")

    def trigger_risk_sequence(self) -> Optional[str]:
        sequence = self.cfg.risk.auto_sequence
        if not sequence:
            return None
        if self._sequence_step >= len(sequence):
            self._sequence_step = 0
        risk_type = sequence[self._sequence_step]
        self._sequence_step += 1
        return self.add_risk(risk_type, source="sequence")

    @property
    def makespan(self) -> int:
        return self.current_time

    @property
    def is_finished(self) -> bool:
        return self._all_done()

    def step(self) -> None:
        self._poll_model_service()
        self._update_agvs(self.current_time)
        self._tick_risks()
        self.current_time += 1
        if self._all_done() or self.current_time >= self.cfg.simulation.max_ticks:
            self.is_running = False

    def finalize(self) -> None:
        self.is_running = False

    def run_to_completion(self, max_ticks: Optional[int] = None) -> int:
        limit = max_ticks or self.cfg.simulation.max_ticks
        while not self._all_done() and self.current_time < limit:
            self.step()
        return self.current_time

    def _poll_model_service(self) -> None:
        if not self.api_enabled:
            return
        interval = max(1, self.cfg.risk.api_poll_ticks)
        if self.current_time - self._last_api_poll < interval:
            return
        self._last_api_poll = self.current_time

        detections = check_risk_models(self.risk_manager, self.model_client,
                                       self.current_time)
        for det in detections:
            self._log(current_time=self.current_time, agv_id="AI",
                      reason="Model hit", method=det["label"],
                      result=f"{det['riskType']} @ {det['location']}")

    def _tick_risks(self) -> None:
        for risk in self.risk_manager.tick(self.current_time):
            self._log(current_time=self.current_time, agv_id="SYS",
                      reason="Risk expired", method="Timeout",
                      result=f"{risk['label']} @ {risk['zone'] or risk['target_id']}")

    def _update_agvs(self, current_time: int) -> None:
        cfg = self.cfg
        agv_map = {agv["id"]: agv for agv in self.agv_states}
        job_states = self.job_location_states

        blocked_wps: Set[str] = self.risk_manager.get_blocked_waypoints()
        paused_locations = self.risk_manager.get_paused_job_locations()
        highway_paused = self.risk_manager.is_zone_paused(cfg.area.highway_zone)
        highway_wps = (get_waypoints_in_zone(cfg.area.highway_zone)
                       if highway_paused else set())

        for agv in self.agv_states:
            if agv["status"] == AGVStatus.BROKEN_DOWN:
                blocked_wps.add(agv["current_wp"])

        all_other_paths: List[List[str]] = []
        for other in self.agv_states:
            remaining = (other.get("path") or [])[other.get("path_step", 0):]
            all_other_paths.append(remaining or [other["current_wp"]])

        pending_tasks = sorted(
            [t for t in self.tasks if t["status"] == TaskStatus.PENDING],
            key=lambda t: t["created_time"])

        for agv_id, agv in agv_map.items():
            if agv["status"] == AGVStatus.DECOMMISSIONED:
                continue

            update_agv_physics(agv)

            if agv["status"] == AGVStatus.BROKEN_DOWN:
                self._handle_broken(agv, agv_id, current_time, blocked_wps,
                                    all_other_paths)
                continue

            if (highway_paused and agv["current_wp"] in highway_wps
                    and agv["status"] != AGVStatus.PAUSED_BY_RISK):
                agv["prev_status_before_blocked"] = agv["status"]
                agv["status"] = AGVStatus.PAUSED_BY_RISK
                log_agv(agv, current_time, "Paused: area locked down (intrusion).")
            elif not highway_paused and agv["status"] == AGVStatus.PAUSED_BY_RISK:
                agv["status"] = (agv.get("prev_status_before_blocked")
                                 or AGVStatus.IDLE)
                log_agv(agv, current_time, "Lockdown lifted, resuming.")

            if agv["status"] == AGVStatus.PAUSED_BY_RISK:
                continue

            if agv["current_task_id"]:
                task = self._find_task(agv["current_task_id"])
                if task and (task["pickup_loc_id"] in paused_locations
                             or task["dropoff_loc_id"] in paused_locations):
                    blocked_loc = (task["pickup_loc_id"]
                                   if task["pickup_loc_id"] in paused_locations
                                   else task["dropoff_loc_id"])
                    self._release_task(agv, task, current_time,
                                       reason=f"Target area {blocked_loc} locked down",
                                       method="Task reassigned")
                    self._release_yard_access(agv)

            is_moving = agv["status"] in AGVStatus.MOVING_STATUSES
            remaining = agv["path"][agv["path_step"]:]
            if is_moving and remaining and any(w in blocked_wps
                                               for w in remaining):
                self._log(current_time=current_time, agv_id=agv_id,
                          reason="Path blocked by risk", method="A* replan",
                          result="pending")
                agv["prev_status_before_blocked"] = agv["status"]
                agv["status"] = AGVStatus.BLOCKED_BY_RISK
                agv["path"] = []
                agv["path_step"] = 0

            status = agv["status"]
            current_wp = agv["current_wp"]

            if agv["path"] and agv["path_step"] >= len(agv["path"]) - 1:
                agv["path"] = []
                agv["path_step"] = 0
                if status == AGVStatus.MOVE_TO_PICKUP:
                    agv["status"] = AGVStatus.WAIT_FOR_PICKUP
                elif status == AGVStatus.MOVE_TO_DROPOFF:
                    agv["status"] = AGVStatus.WAIT_FOR_DROPOFF
                elif status == AGVStatus.RETURNING:
                    agv["status"] = AGVStatus.IDLE
                    agv["history_path"] = [current_wp]
                elif status == AGVStatus.BROKEN_RETURNING:
                    agv["status"] = AGVStatus.DECOMMISSIONED
                    log_agv(agv, current_time, "Returned to depot, decommissioned.")

            status = agv["status"]

            if status in (AGVStatus.MOVE_TO_PICKUP,
                          AGVStatus.MOVE_TO_DROPOFF) and not agv["path"]:
                agv["stall_ticks"] = agv.get("stall_ticks", 0) + 1
                if agv["stall_ticks"] > cfg.simulation.stall_timeout:
                    task = self._find_task(agv["current_task_id"])
                    if task:
                        self._release_task(
                            agv, task, current_time,
                            reason="Destination unreachable", method="Task reassigned")
                    agv["stall_ticks"] = 0
                elif status == AGVStatus.MOVE_TO_DROPOFF:
                    self._plan_to_dropoff(agv, current_time, blocked_wps,
                                          job_states, all_other_paths)
                status = agv["status"]
            else:
                agv["stall_ticks"] = 0

            if status == AGVStatus.WAIT_FOR_PICKUP:
                loc_id = agv["task_pickup_job_loc_id"]
                if loc_id in job_states and job_states[loc_id]["status"] == "FREE":
                    job_states[loc_id].update(status="BUSY", agv_id=agv_id)
                    agv["status"] = AGVStatus.HANDOVER_PICKUP
                    agv["handover_timer"] = cfg.simulation.handover_time

            elif status == AGVStatus.WAIT_FOR_DROPOFF:
                loc_id = agv["task_dropoff_job_loc_id"]
                if loc_id in job_states and job_states[loc_id]["status"] == "FREE":
                    job_states[loc_id].update(status="BUSY", agv_id=agv_id)
                    agv["status"] = AGVStatus.HANDOVER_DROPOFF
                    agv["handover_timer"] = cfg.simulation.handover_time

            elif status == AGVStatus.HANDOVER_PICKUP:
                agv["handover_timer"] -= 1
                if agv["handover_timer"] <= 0:
                    loc_id = agv["task_pickup_job_loc_id"]
                    if loc_id in job_states:
                        job_states[loc_id]["status"] = "FREE"
                        job_states[loc_id]["agv_id"] = None
                    self._release_yard_access(agv)
                    self._plan_to_dropoff(agv, current_time, blocked_wps,
                                          job_states, all_other_paths)

            elif status == AGVStatus.HANDOVER_DROPOFF:
                agv["handover_timer"] -= 1
                if agv["handover_timer"] <= 0:
                    loc_id = agv["task_dropoff_job_loc_id"]
                    if loc_id in job_states:
                        job_states[loc_id]["status"] = "FREE"
                        job_states[loc_id]["agv_id"] = None
                    self._release_yard_access(agv)
                    task = self._find_task(agv["current_task_id"])
                    if task:
                        task.update(status=TaskStatus.COMPLETED,
                                    completed_time=current_time)
                    agv.update(status=AGVStatus.IDLE, current_task_id=None,
                               task_pickup_job_loc_id=None,
                               task_dropoff_job_loc_id=None,
                               target_drivable_wp=None,
                               history_path=[current_wp])

            elif status == AGVStatus.IDLE:
                self._assign_task(agv, agv_id, current_time, pending_tasks,
                                  paused_locations, blocked_wps, job_states,
                                  all_other_paths)

            elif status == AGVStatus.BLOCKED_BY_RISK:
                self._reroute_blocked(agv, agv_id, current_time, blocked_wps,
                                      all_other_paths)

        self._resolve_movement(current_time, blocked_wps, all_other_paths)

    def _find_task(self, task_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not task_id:
            return None
        return next((t for t in self.tasks if t["id"] == task_id), None)

    @staticmethod
    # Feeds A* as initial_direction so the first turn is charged too; None when parked.
    def _heading_dir(agv: Dict[str, Any]) -> Optional[int]:

        hist = agv.get("history_path") or []
        if len(hist) >= 2 and hist[-1] != hist[-2]:
            return direction_key(hist[-2], hist[-1])
        return None

    def _plan(self, agv: Dict[str, Any], goal: str,
              blocked_wps: Optional[Set[str]] = None,
              other_agv_paths: Optional[List[List[str]]] = None,
              count_as_leg: bool = True) -> Optional[List[str]]:
        path = a_star_search(
            agv["current_wp"], goal,
            blocked_waypoints=blocked_wps,
            other_agv_paths=other_agv_paths,
            initial_direction=self._heading_dir(agv),
        )
        if path:
            if count_as_leg:
                self.route_stats["legs"] += 1
                self.route_stats["turns"] += count_turns(path)
                self.route_stats["distance"] += path_distance(path)
            else:
                self.route_stats["replans"] += 1
        return path

    def _log(self, current_time: int, agv_id: str, reason: str,
             method: str, result: str) -> Dict[str, Any]:
        self._log_seq += 1
        entry = {"seq": self._log_seq, "time": current_time,
                 "agvId": agv_id, "reason": reason,
                 "method": method, "result": result}
        self.reschedule_log.append(entry)
        if len(self.reschedule_log) > MAX_LOG_ENTRIES:
            del self.reschedule_log[:-MAX_LOG_ENTRIES]
        return entry

    def _release_yard_access(self, agv: Dict[str, Any]) -> None:
        wp = agv.get("locked_yard_access_wp")
        if wp and wp in self.job_location_states:
            self.job_location_states[wp]["status"] = "FREE"
            self.job_location_states[wp]["agv_id"] = None
        agv["locked_yard_access_wp"] = None

    def _release_job_locations(self, agv: Dict[str, Any]) -> None:
        for wp, state in self.job_location_states.items():
            if state.get("agv_id") == agv["id"]:
                state["status"] = "FREE"
                state["agv_id"] = None
        agv["locked_yard_access_wp"] = None

    def _release_task(self, agv: Dict[str, Any], task: Dict[str, Any],
                      current_time: int, reason: str, method: str) -> None:
        task.update(status=TaskStatus.PENDING, assigned_agv_id=None,
                    assigned_time=None)
        self._log(current_time=current_time, agv_id=agv["id"],
                  reason=reason, method=method,
                  result=f"Task {task['id']} released")
        self._release_job_locations(agv)
        agv.update(status=AGVStatus.IDLE, path=[], path_step=0,
                   current_task_id=None, task_pickup_job_loc_id=None,
                   task_dropoff_job_loc_id=None, target_drivable_wp=None)

    def _handle_broken(self, agv: Dict[str, Any], agv_id: str,
                       current_time: int, blocked_wps: Set[str],
                       all_other_paths: List[List[str]]) -> None:
        if agv.get("current_task_id"):
            task = self._find_task(agv["current_task_id"])
            if task and task["status"] == TaskStatus.ASSIGNED:
                task.update(status=TaskStatus.PENDING, assigned_agv_id=None,
                            assigned_time=None)
                log_agv(agv, current_time,
                        "Task released due to AGV failure.")
                self._log(current_time=current_time, agv_id=agv_id,
                          reason="AGV failure", method="Task reassigned",
                          result=f"Task {task['id']} released")
            self._release_job_locations(agv)
            agv.update(current_task_id=None, task_pickup_job_loc_id=None,
                       task_dropoff_job_loc_id=None, target_drivable_wp=None)

        if agv.get("recovery_time", -1) == -1:
            agv["recovery_time"] = current_time + random.randint(
                self.cfg.risk.agv_recovery_min,
                self.cfg.risk.agv_recovery_max)
        elif current_time >= agv["recovery_time"]:
            agv.update(status=AGVStatus.BROKEN_RETURNING,
                       prev_status_before_blocked=None)
            log_agv(agv, current_time, "Recovered, returning to depot.")
            self.risk_manager.clear_agv_failure(agv_id)

            temp_blocked = set(blocked_wps)
            temp_blocked.discard(agv["current_wp"])
            path_home = self._plan(agv, agv["home_seat_wp"], temp_blocked, all_other_paths)
            if path_home:
                agv.update(path=path_home, path_step=0,
                           target_drivable_wp=agv["home_seat_wp"])
                self._log(current_time=current_time, agv_id=agv_id,
                          reason="AGV recovered", method="A* planning",
                          result=f"OK (return path {len(path_home)} steps)")
            else:
                agv.update(path=[], path_step=0, target_drivable_wp=None)
                log_agv(agv, current_time, "CRITICAL: no return path found.")
                self._log(current_time=current_time, agv_id=agv_id,
                          reason="AGV recovered", method="A* planning",
                          result="FAILED (no return path)")

    def _plan_to_dropoff(self, agv: Dict[str, Any], current_time: int,
                         blocked_wps: Set[str],
                         job_states: Dict[str, Dict[str, Any]],
                         all_other_paths: Optional[List[List[str]]] = None
                         ) -> None:
        job_points = get_job_points()
        dropoff_loc = agv["task_dropoff_job_loc_id"]
        current_wp = agv["current_wp"]
        target_wp, path = None, None

        if dropoff_loc and "YARD_Area" in dropoff_loc:
            occupied = {wp for wp, s in job_states.items()
                        if s["status"] == "BUSY" and s["type"] == "access_wp"}
            bay = job_points.get(dropoff_loc, {}).get("bay")
            candidates = [wp for wp in get_yard_access_points(str(bay))
                          if wp not in occupied]
            candidates.sort(key=lambda wp: heuristic(current_wp, wp))
            for access_wp in candidates:
                candidate_path = self._plan(agv, access_wp, blocked_wps,
                                            all_other_paths)
                if candidate_path:
                    target_wp, path = access_wp, candidate_path
                    agv["locked_yard_access_wp"] = access_wp
                    job_states[access_wp]["status"] = "BUSY"
                    job_states[access_wp]["agv_id"] = agv["id"]
                    break
        elif dropoff_loc:
            target_wp = find_closest_drivable_waypoint(
                job_points[dropoff_loc]["pos"])
            if target_wp:
                path = self._plan(agv, target_wp, blocked_wps,
                                  all_other_paths)

        if not path:
            return

        agv.update(status=AGVStatus.MOVE_TO_DROPOFF,
                   history_path=[current_wp],
                   path=path, path_step=0, target_drivable_wp=target_wp)

    def _assign_task(self, agv: Dict[str, Any], agv_id: str,
                     current_time: int, pending_tasks: List[Dict[str, Any]],
                     paused_locations: Set[str], blocked_wps: Set[str],
                     job_states: Dict[str, Dict[str, Any]],
                     all_other_paths: Optional[List[List[str]]] = None
                     ) -> None:

        job_points = get_job_points()
        current_wp = agv["current_wp"]
        assignable = [t for t in pending_tasks
                      if t["pickup_loc_id"] not in paused_locations
                      and t["dropoff_loc_id"] not in paused_locations]

        for task in assignable:
            pickup_loc = task["pickup_loc_id"]
            target_wp, path = None, None

            if "YARD_Area" in pickup_loc:
                occupied = {wp for wp, s in job_states.items()
                            if s["status"] == "BUSY"
                            and s["type"] == "access_wp"}
                bay = job_points.get(pickup_loc, {}).get("bay")
                candidates = [wp for wp in get_yard_access_points(str(bay))
                              if wp not in occupied]
                candidates.sort(key=lambda wp: heuristic(current_wp, wp))
                for access_wp in candidates:
                    candidate_path = self._plan(agv, access_wp, blocked_wps,
                                                all_other_paths)
                    if candidate_path:
                        target_wp, path = access_wp, candidate_path
                        agv["locked_yard_access_wp"] = access_wp
                        job_states[access_wp]["status"] = "BUSY"
                        job_states[access_wp]["agv_id"] = agv_id
                        break
            else:
                target_wp = find_closest_drivable_waypoint(
                    job_points[pickup_loc]["pos"])
                if target_wp:
                    path = self._plan(agv, target_wp, blocked_wps,
                                      all_other_paths)

            if path:
                pending_tasks.remove(task)
                task.update(status=TaskStatus.ASSIGNED,
                            assigned_agv_id=agv_id,
                            assigned_time=current_time)
                agv.update(status=AGVStatus.MOVE_TO_PICKUP, path=path,
                           path_step=0, current_task_id=task["id"],
                           task_pickup_job_loc_id=task["pickup_loc_id"],
                           task_dropoff_job_loc_id=task["dropoff_loc_id"],
                           target_drivable_wp=target_wp)
                return

        if current_wp != agv["home_seat_wp"]:
            path_home = self._plan(agv, agv["home_seat_wp"], blocked_wps)
            if path_home:
                agv.update(status=AGVStatus.RETURNING, path=path_home,
                           path_step=0, target_drivable_wp=agv["home_seat_wp"])

    def _reroute_blocked(self, agv: Dict[str, Any], agv_id: str,
                         current_time: int, blocked_wps: Set[str],
                         all_other_paths: List[List[str]]) -> None:
        target_wp = agv.get("target_drivable_wp")
        if not target_wp:
            agv["status"] = AGVStatus.IDLE
            agv["blocked_by_agv"] = None
            return

        hard_blocked = set(blocked_wps)
        partner_id = agv.get("blocked_by_agv")
        if partner_id:
            partner = next((a for a in self.agv_states
                            if a["id"] == partner_id), None)
            if partner is not None:
                hard_blocked.add(partner["current_wp"])

        path = self._plan(agv, target_wp, hard_blocked, all_other_paths, count_as_leg=False)
        pending_entry = next(
            (e for e in reversed(self.reschedule_log)
             if e["agvId"] == agv_id and e["result"] == "pending"), None)

        if path:
            agv.update(status=agv.get("prev_status_before_blocked",
                                      AGVStatus.IDLE),
                       path=path, path_step=0,
                       blocked_by_agv=None, blocked_by_wp=None)
            if pending_entry:
                pending_entry["result"] = f"OK (new path {len(path)} steps)"
        else:
            keep_waiting = ("waiting for right-of-way" if partner_id
                            else "waiting for risk clearance")
            if pending_entry:
                pending_entry["result"] = f"FAILED (no route available, {keep_waiting})"
                log_agv(agv, current_time,
                        f"Replan failed, staying to {keep_waiting}.")

    # A vehicle may enter a node only once its occupant really leaves this tick (fixed point).
    def _resolve_movement(self, current_time: int, blocked_wps: Set[str],
                          all_other_paths: List[List[str]]) -> None:
        agv_map = {agv["id"]: agv for agv in self.agv_states}

        intended: Dict[str, Dict[str, str]] = {}
        for agv in self.agv_states:
            if not agv["path"] or agv["status"] not in AGVStatus.MOVING_STATUSES:
                continue
            if agv["path_step"] < len(agv["path"]) - 1:
                intended[agv["id"]] = {
                    "from": agv["current_wp"],
                    "to": agv["path"][agv["path_step"] + 1],
                }

        processed: Set[str] = set()
        for agv_id, move in intended.items():
            if agv_id in processed:
                continue
            for other_id, other in intended.items():
                if agv_id == other_id:
                    continue
                if (other["to"] == move["from"]
                        and other["from"] == move["to"]):
                    loser_id = max(agv_id, other_id,
                                   key=lambda x: int(x.split("-")[1]))
                    winner_id = min(agv_id, other_id,
                                    key=lambda x: int(x.split("-")[1]))
                    loser = agv_map[loser_id]
                    winner = agv_map[winner_id]
                    reason = f"Head-on conflict with {winner_id}"

                    still_pending = any(
                        e["agvId"] == loser_id and e["reason"] == reason
                        and e["result"] == "pending"
                        for e in self.reschedule_log[-80:]
                    )
                    if not still_pending:
                        self._log(current_time=current_time, agv_id=loser_id,
                                  reason=reason,
                                  method="A* replan", result="pending")
                    loser.update(status=AGVStatus.BLOCKED_BY_RISK,
                                 prev_status_before_blocked=loser["status"],
                                 path=[], path_step=0,
                                 blocked_by_agv=winner_id,
                                 blocked_by_wp=winner["current_wp"])
                    log_agv(loser, current_time,
                            f"Head-on conflict with {winner_id}, yielding and replanning.")
                    processed.add(agv_id)
                    processed.add(other_id)
                    break

        stayers: Set[str] = set()
        for agv in self.agv_states:
            if agv["id"] not in intended \
                    or agv["status"] == AGVStatus.BLOCKED_BY_RISK:
                stayers.add(agv["id"])

        occupant_of: Dict[str, List[str]] = {}
        for agv in self.agv_states:
            occupant_of.setdefault(agv["current_wp"], []).append(agv["id"])

        approved: Set[str] = set()
        taken_targets: Set[str] = set()
        order = sorted(intended.keys(), key=lambda x: int(x.split("-")[1]))

        progress = True
        while progress:
            progress = False
            for agv_id in order:
                if agv_id in approved or agv_id in stayers:
                    continue
                to_wp = intended[agv_id]["to"]
                if to_wp in taken_targets:
                    stayers.add(agv_id)
                    progress = True
                    continue
                occupants = [oid for oid in occupant_of.get(to_wp, [])
                             if oid != agv_id]
                if all(oid in approved for oid in occupants):
                    approved.add(agv_id)
                    taken_targets.add(to_wp)
                    progress = True

        for agv_id in order:
            agv = agv_map[agv_id]
            if agv_id in approved:
                agv["wait_ticks"] = 0
                agv["blocked_by_wp"] = None
                agv["blocked_by_agv"] = None
                continue
            agv["wait_ticks"] = agv.get("wait_ticks", 0) + 1
            agv["blocked_by_wp"] = intended[agv_id]["to"]
            if agv["wait_ticks"] in (1, WAIT_LOG_INTERVAL):
                log_agv(agv, current_time,
                        f"Waiting, waypoint {intended[agv_id]['to']} is occupied.")

        for agv in self.agv_states:
            if agv["id"] not in intended or agv["id"] in approved:
                continue
            if agv.get("wait_ticks", 0) < WAIT_TIMEOUT_TICKS:
                continue
            blocker = agv.get("blocked_by_wp")
            if not blocker:
                continue
            hard_blocked = set(blocked_wps) | {blocker}
            target = agv.get("target_drivable_wp")
            detour = (self._plan(agv, target, hard_blocked, all_other_paths, count_as_leg=False)
                      if target else None)
            if detour and len(detour) > 1:
                agv.update(path=detour, path_step=0, wait_ticks=0,
                           blocked_by_wp=None)
                log_agv(agv, current_time,
                        f"Wait timeout, replanning around {blocker}.")
                self._log(current_time=current_time, agv_id=agv["id"],
                          reason=f"Timeout waiting for {blocker}", method="A* replan",
                          result=f"OK (detour {len(detour)} steps)")
            elif agv["wait_ticks"] == WAIT_TIMEOUT_TICKS:
                self._log(current_time=current_time, agv_id=agv["id"],
                          reason=f"Timeout waiting for {blocker}", method="A* replan",
                          result="FAILED (no detour, still waiting)")

        for agv in self.agv_states:
            if agv["id"] in approved:
                advance_agv_one_step(agv)

    def _all_done(self) -> bool:
        if not self.tasks:
            return True
        if any(t["status"] not in (TaskStatus.COMPLETED, TaskStatus.FAILED)
               for t in self.tasks):
            return False
        return all(
            agv["status"] in (AGVStatus.IDLE, AGVStatus.DECOMMISSIONED)
            and agv["current_wp"] == agv["home_seat_wp"]
            for agv in self.agv_states
        )

    def get_frontend_state(self) -> Dict[str, Any]:
        waypoints = get_waypoints()
        agvs = []
        for agv in self.agv_states:
            pos = waypoints.get(agv["current_wp"], {}).get(
                "absolutePosition", {"x": 0.0, "y": 0.0, "z": 0.0})
            agvs.append({
                "id": agv["id"],
                "position": pos,
                "rotation": agv.get("rotation", 0.0),
                "status": agv["status"],
                "statusLabel": STATUS_LABELS.get(agv["status"],
                                                         agv["status"]),
                "battery": round(agv.get("battery", 100.0), 1),
                "taskId": agv.get("current_task_id"),
                "currentWp": agv["current_wp"],
                "targetWp": agv.get("target_drivable_wp"),
                "pickupLoc": agv.get("task_pickup_job_loc_id"),
                "dropoffLoc": agv.get("task_dropoff_job_loc_id"),
                "handoverTimer": agv.get("handover_timer", 0),
                "distanceM": round(agv.get("distance_traveled", 0.0), 1),
                "path": (agv.get("path") or [])[agv.get("path_step", 0):],
                "historyPath": agv.get("history_path", [])[-40:],
                "log": agv.get("log", [])[-20:],
                "broken": agv["status"] in (AGVStatus.BROKEN_DOWN,
                                            AGVStatus.BROKEN_RETURNING),
            })

        completed = sum(1 for t in self.tasks
                        if t["status"] == TaskStatus.COMPLETED)
        active = sum(1 for a in self.agv_states
                     if a["status"] not in (AGVStatus.IDLE,
                                            AGVStatus.DECOMMISSIONED))

        return {
            "time": self.current_time,
            "agvs": agvs,
            "tasks": self.tasks,
            "risks": self.risk_manager.to_payload(),
            "rescheduleLog": self.reschedule_log[-120:],
            "jobLocationStates": self.job_location_states,
            "kpis": compute_kpis(self.agv_states, self.tasks,
                                 self.current_time),
            "agvEfficiency": agv_efficiency(self.agv_states),
            "statusDistribution": status_distribution(self.agv_states),
            "apiStatus": self.model_client.status_payload(self.api_enabled),
            "stats": {
                "totalTasks": len(self.tasks),
                "completedTasks": completed,
                "activeAgvs": active,
            },
            "isRunning": self.is_running,
            "makespan": self.current_time,
            "finished": self._all_done(),
        }

    def get_network_data(self) -> Dict[str, Any]:
        from rcds.port.network import get_adjacency
        waypoints = get_waypoints()
        nodes = [
            {
                "id": name,
                "position": info.get("absolutePosition",
                                     {"x": 0, "y": 0, "z": 0}),
                "type": next((p for p in ("sl", "ll", "b", "a")
                              if name.startswith(p)), "other"),
            }
            for name, info in waypoints.items()
        ]
        edges = [
            {"from": fn, "to": tn, "distance": d}
            for fn, nbrs in get_adjacency().items()
            for tn, d in nbrs
        ]
        return {"nodes": nodes, "edges": edges}

    def get_job_points_data(self) -> Dict[str, Any]:
        data = {
            jp_id: {
                "id": info["id"],
                "pos": info["pos"],
                "areaNo": info["areaNo"],
                "bay": info["bay"],
                "width": info.get("width", 10),
                "height": info.get("height", 10),
            }
            for jp_id, info in get_job_points().items()
        }
        return data

    def get_summary(self) -> Dict[str, Any]:
        kpis = compute_kpis(self.agv_states, self.tasks,
                            self.current_time)
        risk_history = self.risk_manager.history
        return {
            "time": self.current_time,
            "finished": self._all_done(),
            "agvs": len(self.agv_states),
            "tasks": len(self.tasks),
            "kpis": kpis,
            "riskTotal": len(risk_history),
            "riskActive": len(self.risk_manager.active_risks),
            "riskByType": self._risk_type_counts(risk_history),
            "rescheduleEvents": len(self.reschedule_log),
        }

    @staticmethod
    def _risk_type_counts(history: List[Dict[str, Any]]
                          ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for risk in history:
            counts[risk["type"]] = counts.get(risk["type"], 0) + 1
        return counts
