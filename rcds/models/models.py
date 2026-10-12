from typing import TypedDict, Optional, List


class AGVStatus:

    IDLE = "IDLE"
    MOVE_TO_PICKUP = "MOVE_TO_PICKUP"
    WAIT_FOR_PICKUP = "WAIT_FOR_PICKUP"
    HANDOVER_PICKUP = "HANDOVER_PICKUP"
    MOVE_TO_DROPOFF = "MOVE_TO_DROPOFF"
    WAIT_FOR_DROPOFF = "WAIT_FOR_DROPOFF"
    HANDOVER_DROPOFF = "HANDOVER_DROPOFF"
    RETURNING = "RETURNING"

    BROKEN_DOWN = "BROKEN_DOWN"
    BROKEN_RETURNING = "BROKEN_RETURNING"
    DECOMMISSIONED = "DECOMMISSIONED"

    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    PAUSED_BY_RISK = "PAUSED_BY_RISK"

    MOVING_STATUSES = {MOVE_TO_PICKUP, MOVE_TO_DROPOFF, RETURNING,
                       BROKEN_RETURNING}

    WORKING_MOVING_STATUSES = {MOVE_TO_PICKUP, MOVE_TO_DROPOFF}

    HOLD_STATUSES = {WAIT_FOR_PICKUP, WAIT_FOR_DROPOFF,
                     HANDOVER_PICKUP, HANDOVER_DROPOFF}

    RISK_STATUSES = {BLOCKED_BY_RISK, PAUSED_BY_RISK}

    INACTIVE_STATUSES = {BROKEN_DOWN, DECOMMISSIONED}


class TaskStatus:
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskType:
    IMPORT = "import"
    EXPORT = "export"


class RiskType:
    FIRE = "FIRE"
    PERSONNEL_INTRUSION = "PERSONNEL_INTRUSION"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    AGV_FAILURE = "AGV_FAILURE"
    NO_HELMET = "NO_HELMET"
    SMOKING = "SMOKING"

    ALL = (FIRE, PERSONNEL_INTRUSION, TRAFFIC_CONGESTION,
           AGV_FAILURE, NO_HELMET, SMOKING)

    LABELS = {
        FIRE: "Fire",
        PERSONNEL_INTRUSION: "Personnel Intrusion",
        TRAFFIC_CONGESTION: "Traffic Congestion",
        AGV_FAILURE: "AGV Failure",
        NO_HELMET: "No Helmet",
        SMOKING: "Smoking",
    }

    SEVERITY = {
        FIRE: "danger",
        PERSONNEL_INTRUSION: "primary",
        TRAFFIC_CONGESTION: "info",
        AGV_FAILURE: "dark",
        NO_HELMET: "warning",
        SMOKING: "secondary",
    }

RISK_LABELS = RiskType.LABELS


class Position(TypedDict):
    x: float
    y: float
    z: float


class WaypointInfo(TypedDict, total=False):
    name: str
    absolutePosition: Position


class AGVState(TypedDict, total=False):
    id: str
    home_seat_wp: str
    current_wp: str
    rotation: float
    status: str
    path: List[str]
    path_step: int
    current_task_id: Optional[str]
    task_pickup_job_loc_id: Optional[str]
    task_dropoff_job_loc_id: Optional[str]
    target_drivable_wp: Optional[str]
    locked_yard_access_wp: Optional[str]
    prev_status_before_blocked: Optional[str]
    history_path: List[str]
    battery: float
    handover_timer: int
    recovery_time: int
    distance_traveled: float
    time_idle: int
    time_moving_empty: int
    time_moving_loaded: int
    time_blocked: int
    log: List[str]


class TaskInfo(TypedDict, total=False):
    id: str
    type: str
    pickup_loc_id: str
    dropoff_loc_id: str
    status: str
    assigned_agv_id: Optional[str]
    created_time: int
    assigned_time: Optional[int]
    completed_time: Optional[int]
