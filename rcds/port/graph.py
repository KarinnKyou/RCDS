"""A* path planning over the terminal road network."""

from __future__ import annotations

import heapq
import math
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from rcds.models.config import Config
from rcds.port.network import calculate_distance, get_adjacency, get_waypoints

_YARD_ACCESS_CACHE: Dict[str, List[str]] = {}

_EDGE_DIR: Dict[Tuple[str, str], int] = {}

_DIR_SECTORS = 8
_SECTOR_RAD = math.pi / 4

def _dir_of(dx: float, dz: float) -> Optional[int]:
    if abs(dx) < 1e-6 and abs(dz) < 1e-6:
        return None
    return int(round(math.atan2(dx, dz) / _SECTOR_RAD)) % _DIR_SECTORS

def _ensure_edge_dirs() -> Dict[Tuple[str, str], int]:
    if _EDGE_DIR:
        return _EDGE_DIR
    waypoints = get_waypoints()
    for u, neighbours in get_adjacency().items():
        pu = waypoints.get(u, {}).get("absolutePosition")
        if not pu:
            continue
        for v, _dist in neighbours:
            pv = waypoints.get(v, {}).get("absolutePosition")
            if not pv:
                continue
            key = _dir_of(pv["x"] - pu["x"], pv["z"] - pu["z"])
            if key is not None:
                _EDGE_DIR[(u, v)] = key
    return _EDGE_DIR

def direction_key(from_wp: str, to_wp: str) -> Optional[int]:
    return _ensure_edge_dirs().get((from_wp, to_wp))

def direction_key_from_angle(theta: float) -> int:
    return int(round(theta / _SECTOR_RAD)) % _DIR_SECTORS

def count_turns(path: Optional[List[str]]) -> int:
    if not path or len(path) < 3:
        return 0
    edge_dirs = _ensure_edge_dirs()
    dirs: List[int] = []
    for a, b in zip(path, path[1:]):
        key = edge_dirs.get((a, b))
        if key is not None:
            dirs.append(key)
    return sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1])

def straight_ratio(path: Optional[List[str]]) -> float:
    if not path or len(path) < 2:
        return 1.0
    return max(0.0, 1.0 - count_turns(path) / (len(path) - 1))

def heuristic(wp_a: str, wp_b: str) -> float:
    waypoints = get_waypoints()
    if wp_a not in waypoints or wp_b not in waypoints:
        return float("inf")
    pa = waypoints[wp_a]["absolutePosition"]
    pb = waypoints[wp_b]["absolutePosition"]
    return math.sqrt((pa["x"] - pb["x"]) ** 2 + (pa["z"] - pb["z"]) ** 2)

def find_closest_drivable_waypoint(target_pos: Dict[str, float],
                                   candidates: Optional[Iterable[str]] = None
                                   ) -> Optional[str]:
    waypoints = get_waypoints()
    if not waypoints or not target_pos:
        return None

    names = candidates if candidates is not None else waypoints.keys()
    best_name, best_dist = None, float("inf")
    tx, tz = target_pos.get("x"), target_pos.get("z")
    for name in names:
        info = waypoints.get(name)
        if not info:
            continue
        pos = info.get("absolutePosition")
        if not pos:
            continue
        dist = (pos["x"] - tx) ** 2 + (pos["z"] - tz) ** 2
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name

def path_distance(path: List[str]) -> float:
    waypoints = get_waypoints()
    total = 0.0
    for a, b in zip(path, path[1:]):
        pa, pb = waypoints.get(a), waypoints.get(b)
        if not pa or not pb:
            continue
        total += calculate_distance(pa["absolutePosition"],
                                    pb["absolutePosition"])
    return total

def a_star_search(
    start: str,
    goal: str,
    blocked_waypoints: Optional[Set[str]] = None,
    other_agv_paths: Optional[List[List[str]]] = None,
    initial_direction: Optional[int] = None,
    turn_penalty: Optional[float] = None,
    trace: Optional[Callable[[str, float, float], None]] = None,
) -> Optional[List[str]]:
    """
    A* search with turn cost.

    trace, when given, is called as trace(node, g, f) for every expanded node
    and is used by the demo video to record the real search process.
    """
    waypoints = get_waypoints()
    adjacency = get_adjacency()

    if start not in waypoints or goal not in waypoints:
        return None
    if start == goal:
        return [start]

    blocked = blocked_waypoints or set()
    if start in blocked or goal in blocked:
        return None

    cfg = Config.get()
    penalty = float(cfg.area.path_penalty)
    turn_cost = (float(cfg.area.turn_penalty)
                 if turn_penalty is None else float(turn_penalty))
    edge_dirs = _ensure_edge_dirs() if turn_cost > 0 else {}

    penalty_wps: Set[str] = set()
    if other_agv_paths:
        for path in other_agv_paths:
            penalty_wps.update(path)
    penalty_wps.discard(start)

    start_state: Tuple[str, int] = (
        start, -1 if initial_direction is None else initial_direction)
    g_score: Dict[Tuple[str, int], float] = {start_state: 0.0}
    came_from: Dict[Tuple[str, int], Tuple[str, int]] = {}
    heap: List[Tuple[float, float, Tuple[str, int]]] = [
        (heuristic(start, goal), 0.0, start_state)
    ]
    closed: Set[Tuple[str, int]] = set()

    while heap:
        _f, cost, state = heapq.heappop(heap)
        if state in closed:
            continue
        closed.add(state)
        if trace is not None:
            trace(state[0], cost, _f)

        node, dir_in = state
        if node == goal:
            path = [node]
            while state in came_from:
                state = came_from[state]
                path.append(state[0])
            path.reverse()
            return path

        for neighbour, distance in adjacency.get(node, ()):
            if neighbour not in waypoints or neighbour in blocked:
                continue

            step = distance
            if neighbour in penalty_wps:
                step += penalty

            dir_out = edge_dirs.get((node, neighbour)) if turn_cost > 0 else None
            if (turn_cost > 0 and dir_in != -1 and dir_out is not None
                    and dir_out != dir_in):
                step += turn_cost

            next_state = (neighbour, dir_out if dir_out is not None else dir_in)
            tentative = cost + step
            if tentative < g_score.get(next_state, float("inf")):
                came_from[next_state] = state
                g_score[next_state] = tentative
                heapq.heappush(heap, (tentative + heuristic(neighbour, goal),
                                      tentative, next_state))

    return None

def get_yard_access_points(bay_id: str) -> List[str]:
    if not bay_id:
        return []
    if bay_id in _YARD_ACCESS_CACHE:
        return _YARD_ACCESS_CACHE[bay_id]

    digits = bay_id[1:] if len(bay_id) > 1 else ""
    if not bay_id.upper().startswith("Y") or not digits.isdigit():
        _YARD_ACCESS_CACHE[bay_id] = []
        return []

    prefix = f"a{digits}_"
    deepest: Dict[str, Tuple[float, str]] = {}
    for name, info in get_waypoints().items():
        if not name.startswith(prefix):
            continue
        parts = name.split("_")
        if len(parts) < 3:
            continue
        lane = parts[1]
        z = info["absolutePosition"]["z"]
        cur = deepest.get(lane)
        if cur is None or z < cur[0]:
            deepest[lane] = (z, name)

    result = [deepest[lane][1] for lane in sorted(deepest)]
    _YARD_ACCESS_CACHE[bay_id] = result
    return result

def clear_caches() -> None:
    _YARD_ACCESS_CACHE.clear()
    _EDGE_DIR.clear()
