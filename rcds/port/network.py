"""
Port road network loading and management.

Responsibilities:
- load the JSON road network files
- build the adjacency list
- expose waypoint / job point queries

Waypoint naming: [lane type][index]_x[X]_z[Z], for example sl0_x0_z500,
b15_x300_z325, a0_0_x200_z25. Physical junctions between SL/LL and B/A lanes
are already de-duplicated by the generator, so no special handling is needed.
"""

import json
import math
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any, Optional
from rcds.models.config import Config
from rcds.models.logger import get_logger

logger = get_logger("network.graph")

class _GraphState:
    def __init__(self):
        self.waypoints: Dict[str, Any] = {}
        self.adjacency: Dict[str, List[Tuple[str, float]]] = {}
        self.waypoint_names: List[str] = []
        self.job_points: Dict[str, Any] = {}
        self.annotations: List[Any] = []
        self.error: str = ""
        self.loaded: bool = False

_state = _GraphState()

LANE_CHANGE_PENALTY = 0.0

def get_waypoints() -> Dict[str, Any]:
    return _state.waypoints

def get_adjacency() -> Dict[str, List[Tuple[str, float]]]:
    return _state.adjacency

def get_waypoint_names() -> List[str]:
    return _state.waypoint_names

def get_job_points() -> Dict[str, Any]:
    return _state.job_points

def get_annotations() -> List[Any]:
    return _state.annotations

def get_load_error() -> str:
    return _state.error

def is_loaded() -> bool:
    return _state.loaded

def get_waypoints_in_zone(zone_name: str) -> Set[str]:
    cfg = Config.get()
    result = set()

    if not _state.waypoints:
        return result

    if zone_name == "Highway_Area":
        for name, info in _state.waypoints.items():
            pos = info.get("absolutePosition")
            if pos and cfg.network.highway_area_z_min <= pos.get("z", 0) < cfg.network.highway_area_z_max:
                result.add(name)

    return result

def load_network(
    road_file: Optional[str] = None,
    turn_file: Optional[str] = None,
    point_file: Optional[str] = None
) -> bool:
    global _state

    cfg = Config.get()
    road_file = road_file or cfg.road_file
    turn_file = turn_file or cfg.turn_file
    point_file = point_file or cfg.point_file

    _state = _GraphState()

    if not _load_job_points(point_file):
        logger.warning("Job points data load failed")

    try:
        with open(road_file, "r", encoding="utf-8") as f:
            road_data = json.load(f)
    except Exception as e:
        _state.error = f"Road file error: {e}"
        logger.error(_state.error)
        return False

    turn_data = None
    if turn_file:
        try:
            with open(turn_file, "r", encoding="utf-8") as f:
                turn_data = json.load(f)
        except Exception as e:
            logger.warning(f"Turn file load warning: {e}")

    try:
        adjacency, waypoints = _parse_network(road_data, turn_data)
        _state.adjacency = adjacency
        _state.waypoints = waypoints
        _state.waypoint_names = sorted(list(waypoints.keys()))
        _state.loaded = True

        logger.info(
            f"Network loaded: {len(_state.waypoint_names)} waypoints, "
            f"{sum(len(v) for v in _state.adjacency.values())} edges"
        )
        return True

    except Exception as e:
        _state.error = f"Network parsing error: {e}"
        logger.error(_state.error)
        return False

def calculate_distance(pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
    dx = pos1["x"] - pos2["x"]
    dy = pos1["y"] - pos2["y"]
    dz = pos1["z"] - pos2["z"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def _load_job_points(point_file: str) -> bool:
    try:
        with open(point_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        job_points = {}
        annotations = []

        for area_info in data:
            area_no = area_info.get("areaNo")
            if not area_no:
                continue

            for bay_info in area_info.get("bays", []):
                bay_no = bay_info.get("bay")
                pos = bay_info.get("pos")
                if bay_no and pos:
                    jp_id = f"{area_no}_{bay_no}"
                    job_points[jp_id] = {
                        "id": jp_id,
                        "pos": pos,
                        "areaNo": str(area_no),
                        "bay": str(bay_no),
                        "width": bay_info.get("width", 10),
                        "height": bay_info.get("height", 10),
                    }

            annotations.extend(area_info.get("annotations", []))

        _state.job_points = job_points
        _state.annotations = annotations
        return True

    except FileNotFoundError:
        logger.warning(f"Point file not found: {point_file}")
        return False
    except Exception as e:
        logger.warning(f"Point file parse error: {e}")
        return False

# SL lanes run towards decreasing X, LL lanes towards increasing X.
def _is_direction_allowed(
    wp_start: str,
    wp_end: str,
    start_pos: Dict,
    end_pos: Dict
) -> bool:

    if wp_start.startswith("sl"):
        if end_pos["x"] - start_pos["x"] > 0.1:
            return False

    if wp_start.startswith("ll"):
        if end_pos["x"] - start_pos["x"] < -0.1:
            return False

    return True

def _add_edge(
    graph: Dict[str, List],
    u: str,
    v: str,
    dist: float
) -> None:
    if u not in graph:
        graph[u] = []
    if not any(neighbor == v for neighbor, _ in graph[u]):
        graph[u].append((v, dist))

def _parse_network(
    road_data: List[Dict],
    turn_data: Optional[List[Dict]]
) -> Tuple[Dict, Dict]:
    graph = defaultdict(list)
    waypoints = {}

    if not road_data:
        raise ValueError("Road data is empty")

    for road_segment in road_data:
        for lane_obj in road_segment.get("lanes", []):
            lane_wps = lane_obj.get("wayPoints", [])

            for wp in lane_wps:
                name = wp.get("name")
                pos = wp.get("absolutePosition")
                if name and pos:
                    waypoints[name] = wp

            for i in range(len(lane_wps) - 1):
                wp1, wp2 = lane_wps[i], lane_wps[i + 1]
                name1, name2 = wp1["name"], wp2["name"]
                pos1 = wp1.get("absolutePosition")
                pos2 = wp2.get("absolutePosition")

                if pos1 and pos2:
                    dist = calculate_distance(pos1, pos2)
                    if _is_direction_allowed(name1, name2, pos1, pos2):
                        _add_edge(graph, name1, name2, dist)
                    if _is_direction_allowed(name2, name1, pos2, pos1):
                        _add_edge(graph, name2, name1, dist)

    if turn_data:
        for turn in turn_data:
            from_wp = turn.get("from")
            to_wp = turn.get("to")

            if from_wp in waypoints and to_wp in waypoints:
                pos1 = waypoints[from_wp].get("absolutePosition")
                pos2 = waypoints[to_wp].get("absolutePosition")

                if pos1 and pos2:
                    dist = calculate_distance(pos1, pos2)
                    if _is_direction_allowed(from_wp, to_wp, pos1, pos2):
                        _add_edge(graph, from_wp, to_wp, dist)

    return dict(graph), waypoints

load_all_graph_data = load_network
get_all_waypoints_info = get_waypoints
get_graph_adjacency = get_adjacency
get_job_points_data = get_job_points
get_annotations_data = get_annotations
get_data_load_error = get_load_error
