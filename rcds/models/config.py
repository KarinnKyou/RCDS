import os
from dataclasses import dataclass, field
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

DATA_NETWORK_DIR = os.path.join(PROJECT_ROOT, "data", "network")

@dataclass
class NetworkConfig:
    x_step: int = 20
    z_step: int = 20
    num_highway_lanes: int = 60
    highway_area_z_min: float = 100.0
    highway_area_z_max: float = 260.0

    road_file: str = os.path.join(DATA_NETWORK_DIR, "road.json")
    turn_file: str = os.path.join(DATA_NETWORK_DIR, "turn.json")
    point_file: str = os.path.join(DATA_NETWORK_DIR, "point.json")

    @property
    def lane_x_width(self) -> int:
        return (self.num_highway_lanes - 1) * self.x_step

@dataclass
class SimulationConfig:
    num_agvs: int = 5
    handover_time: int = 10
    max_tasks: int = 100
    seed: int = 42
    # Distance one full charge covers per vehicle. At the default 5-AGV scenario a task
    # costs the fleet ~1.8 km (0.36 km per vehicle), so one charge supports ~10 000 tasks.
    battery_range_km: float = 3600.0
    tick_interval_ms: int = 500
    default_speed: float = 1.0

    # Ticks a vehicle may sit "moving without a path" before its task returns to PENDING.
    stall_timeout: int = 60

    max_ticks: int = 20000

@dataclass
class AreaConfig:
    seaside_area_keywords: List[str] = field(
        default_factory=lambda: ["QC_Area"])
    yard_area_keywords: List[str] = field(
        default_factory=lambda: ["YARD_Area"])
    ship_area_keywords: List[str] = field(
        default_factory=lambda: ["Ship_Area"])
    highway_zone: str = "Highway_Area"

    congestion_radius: float = 60.0

    # Extra A* cost for nodes already on another AGV's planned path.
    path_penalty: float = 1000.0

    # Extra A* cost (m) per direction change; keeps routes from zig-zagging.
    turn_penalty: float = 100.0

@dataclass
class RiskConfig:
    api_poll_ticks: int = 15
    api_sequence_seconds: float = 10.0
    agv_recovery_min: int = 30
    agv_recovery_max: int = 60

    default_duration: int = 99999
    api_risk_duration: int = 120
    auto_sequence: List[str] = field(default_factory=lambda: [
        "SMOKING", "FIRE", "NO_HELMET",
        "TRAFFIC_CONGESTION", "PERSONNEL_INTRUSION", "AGV_FAILURE",
    ])

@dataclass
class ApiConfig:
    model_server_base_url: str = "http://127.0.0.1:8800"
    camera_urls: Dict[str, List[str]] = field(default_factory=lambda: {
        "QC_Area": ["http://camera.local/qc_stream.mp4"],
        "YARD_Area": ["http://camera.local/yard_stream.jpg"],
        "Highway_Area": ["http://camera.local/highway_stream.mp4"],
        "General_Area_1": ["http://camera.local/gate1.jpg"],
    })

    use_real_api: bool = False
    timeout_seconds: float = 5.0

    mock_detect_probability: float = 0.12

class Config:

    _instance = None

    def __init__(self):
        self.network = NetworkConfig()
        self.simulation = SimulationConfig()
        self.area = AreaConfig()
        self.risk = RiskConfig()
        self.api = ApiConfig()

        self.base_dir = PROJECT_ROOT
        self.data_dir = DATA_NETWORK_DIR

    @property
    def road_file(self) -> str:
        return self.network.road_file

    @property
    def turn_file(self) -> str:
        return self.network.turn_file

    @property
    def point_file(self) -> str:
        return self.network.point_file

    @classmethod
    def get(cls) -> "Config":
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    @classmethod
    def reset(cls) -> "Config":
        cls._instance = Config()
        return cls._instance

    @classmethod
    def apply_args(cls, args) -> "Config":
        cfg = cls.get()

        agvs = getattr(args, "agvs", None)
        if agvs is not None:
            cfg.simulation.num_agvs = agvs

        tasks = getattr(args, "tasks", None)
        if tasks is not None:
            cfg.simulation.max_tasks = tasks

        if getattr(args, "seed", None) is not None:
            cfg.simulation.seed = args.seed

        if getattr(args, "max_ticks", None) is not None:
            cfg.simulation.max_ticks = args.max_ticks

        if getattr(args, "real_api", False):
            cfg.api.use_real_api = True
        if getattr(args, "model_server", None):
            cfg.api.model_server_base_url = args.model_server

        return cfg

def get_config() -> Config:
    return Config.get()
