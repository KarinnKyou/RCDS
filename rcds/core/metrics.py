from __future__ import annotations

from typing import Any, Dict, List

from rcds.models.models import AGVStatus, TaskStatus

STATUS_LABELS = {
    AGVStatus.IDLE: "Idle",
    AGVStatus.MOVE_TO_PICKUP: "To Pickup",
    AGVStatus.WAIT_FOR_PICKUP: "Waiting at Pickup",
    AGVStatus.HANDOVER_PICKUP: "Pickup Handover",
    AGVStatus.MOVE_TO_DROPOFF: "Carrying",
    AGVStatus.WAIT_FOR_DROPOFF: "Waiting at Drop-off",
    AGVStatus.HANDOVER_DROPOFF: "Drop-off Handover",
    AGVStatus.RETURNING: "Returning",
    AGVStatus.BROKEN_DOWN: "Breakdown",
    AGVStatus.BROKEN_RETURNING: "Breakdown, Returning",
    AGVStatus.DECOMMISSIONED: "Decommissioned",
    AGVStatus.BLOCKED_BY_RISK: "Blocked by Risk",
    AGVStatus.PAUSED_BY_RISK: "Paused by Risk",
}


def _total_time(agv: Dict[str, Any]) -> int:
    return (agv["time_idle"] + agv["time_moving_empty"]
            + agv["time_moving_loaded"] + agv["time_blocked"])


def agv_efficiency(agv_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for agv in agv_states:
        total = _total_time(agv) or 1
        rows.append({
            "id": agv["id"],
            "status": agv["status"],
            "statusLabel": STATUS_LABELS.get(agv["status"], agv["status"]),
            "distanceM": round(agv["distance_traveled"], 1),
            "battery": round(agv["battery"], 1),
            "loadedPct": round(agv["time_moving_loaded"] / total * 100, 1),
            "emptyPct": round(agv["time_moving_empty"] / total * 100, 1),
            "idlePct": round(agv["time_idle"] / total * 100, 1),
            "blockedPct": round(agv["time_blocked"] / total * 100, 1),
            "taskId": agv.get("current_task_id"),
            "totalTime": total,
        })
    return rows


def compute_kpis(agv_states: List[Dict[str, Any]],
                 tasks: List[Dict[str, Any]],
                 current_time: int
                 ) -> Dict[str, Any]:
    total_tasks = len(tasks)
    completed = sum(1 for t in tasks if t["status"] == TaskStatus.COMPLETED)
    failed = sum(1 for t in tasks if t["status"] == TaskStatus.FAILED)
    pending = sum(1 for t in tasks if t["status"] == TaskStatus.PENDING)
    assigned = sum(1 for t in tasks if t["status"] == TaskStatus.ASSIGNED)

    durations = [t["completed_time"] - t["assigned_time"]
                 for t in tasks
                 if t["status"] == TaskStatus.COMPLETED
                 and t.get("assigned_time") is not None
                 and t.get("completed_time") is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    total_dist_m = sum(a["distance_traveled"] for a in agv_states)

    total_time = sum(_total_time(a) for a in agv_states)
    busy_time = sum(a["time_moving_empty"] + a["time_moving_loaded"]
                    + a["time_blocked"] for a in agv_states)
    utilization = (busy_time / total_time * 100) if total_time > 0 else 0.0
    blocked_time = sum(a["time_blocked"] for a in agv_states)
    blocked_ratio = (blocked_time / total_time * 100) if total_time > 0 else 0.0

    return {
        "time": current_time,
        "taskTotal": total_tasks,
        "taskCompleted": completed,
        "taskPending": pending,
        "taskAssigned": assigned,
        "taskFailed": failed,
        "completionRate": round(
            (completed / total_tasks * 100) if total_tasks else 0.0, 1),
        "utilizationRate": round(utilization, 1),
        "blockedRate": round(blocked_ratio, 1),
        "avgTaskDuration": round(avg_duration, 1),
        "totalDistanceKm": round(total_dist_m / 1000.0, 2),
        "avgBattery": round(
            sum(a["battery"] for a in agv_states) / len(agv_states), 1
        ) if agv_states else 0.0,
    }


def status_distribution(agv_states: List[Dict[str, Any]]
                        ) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for agv in agv_states:
        counts[agv["status"]] = counts.get(agv["status"], 0) + 1
    return [{"status": status,
             "label": STATUS_LABELS.get(status, status),
             "count": count}
            for status, count in sorted(counts.items())]
