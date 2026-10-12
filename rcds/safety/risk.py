"""Risk ledger: maps safety risks to blocked waypoints and paused job points."""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional, Set

from rcds.models.config import Config
from rcds.models.models import RiskType
from rcds.port.network import (
    get_job_points,
    get_waypoints,
    get_waypoints_in_zone,
)

class RiskManager:
    def __init__(self) -> None:
        self.cfg = Config.get()
        self.active_risks: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self.history: List[Dict[str, Any]] = []

    def add_risk(
        self,
        risk_type: str,
        zone: Optional[str] = None,
        job_point_id: Optional[str] = None,
        agv_id: Optional[str] = None,
        duration: Optional[int] = None,
        current_time: int = 0,
        location_wp: Optional[str] = None,
        source: str = "manual",
        message: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add one risk and return its id, or None when it cannot be located.

        Arguments: risk_type is a `RiskType` constant; zone is an area name;
        job_point_id is a job point id; agv_id is the failing vehicle;
        duration is in ticks (None uses the configured default);
        location_wp is the waypoint the risk sits on; source is one of
        "manual" / "api" / "sequence" / "simulation"; message overrides the
        generated alert text.
        """
        if risk_type not in RiskType.ALL:
            return None

        location_wp, display_pos, target_id = self._get_risk_location(
            zone, job_point_id, agv_id, location_wp
        )

        # A vehicle-only risk (AGV failure) has no coordinates; it is drawn at the AGV.
        if not location_wp and not display_pos and not agv_id:
            return None

        risk_id = str(uuid.uuid4())
        self._seq += 1
        risk = {
            "id": risk_id,
            "seq": self._seq,
            "type": risk_type,
            "label": RiskType.LABELS.get(risk_type, risk_type),
            "severity": RiskType.SEVERITY.get(risk_type, "danger"),
            "zone": zone or job_point_id or "",
            "target_id": target_id,
            "agv_id": agv_id,
            "location_wp": location_wp,
            "display_pos": display_pos,
            "duration": (self.cfg.risk.default_duration
                         if duration is None else int(duration)),
            "active": True,
            "created_time": current_time,
            "source": source,
            "affected_waypoints": self._calculate_affected_waypoints(
                location_wp, risk_type
            ),
            "message": message or self._generate_alert_message(
                risk_type, zone or job_point_id or target_id or "unknown location"
            ),
        }
        self.active_risks[risk_id] = risk
        self.history.append({k: v for k, v in risk.items()})
        return risk_id

    def _get_risk_location(
        self,
        zone: Optional[str],
        job_point_id: Optional[str],
        agv_id: Optional[str],
        location_wp: Optional[str],
    ):
        waypoints = get_waypoints()

        if location_wp and location_wp in waypoints:
            return (location_wp,
                    waypoints[location_wp]["absolutePosition"],
                    agv_id or location_wp)

        job_points = get_job_points()
        if job_point_id and job_point_id in job_points:
            info = job_points[job_point_id]
            return job_point_id, info["pos"], job_point_id

        if zone:
            wps_in_zone = get_waypoints_in_zone(zone) or set()
            if wps_in_zone:
                wp = random.choice(list(wps_in_zone))
                return (wp, waypoints[wp]["absolutePosition"], zone)

        if agv_id:

            return None, None, agv_id

        if waypoints:
            wp = random.choice(list(waypoints.keys()))
            return wp, waypoints[wp]["absolutePosition"], "Unknown"

        return None, None, None

    def _calculate_affected_waypoints(self, center_wp: Optional[str],
                                      risk_type: str) -> List[str]:
        affected: Set[str] = set()
        if risk_type != RiskType.TRAFFIC_CONGESTION or not center_wp:
            return []

        waypoints = get_waypoints()
        center = waypoints.get(center_wp, {}).get("absolutePosition")
        if not center:
            return []

        radius = self.cfg.area.congestion_radius
        radius_sq = radius * radius
        for name, info in waypoints.items():
            pos = info.get("absolutePosition")
            if not pos:
                continue
            if ((pos["x"] - center["x"]) ** 2
                    + (pos["z"] - center["z"]) ** 2) < radius_sq:
                affected.add(name)
        return sorted(affected)

    @staticmethod
    def _generate_alert_message(risk_type: str, location_name: str) -> str:
        return {
            RiskType.FIRE:
                f"Fire alert: fire detected at {location_name}.",
            RiskType.PERSONNEL_INTRUSION:
                f"Intrusion alert: unauthorized personnel detected at "
                f"{location_name}.",
            RiskType.TRAFFIC_CONGESTION:
                f"Congestion warning: traffic jam near {location_name}.",
            RiskType.AGV_FAILURE:
                f"AGV failure: vehicle broke down at {location_name}.",
            RiskType.NO_HELMET:
                f"Safety warning: no helmet detected at {location_name}.",
            RiskType.SMOKING:
                f"Smoking warning: smoking detected at {location_name}.",
        }.get(risk_type, "Unknown risk type")

    def get_all_risks(self) -> List[Dict[str, Any]]:
        return sorted(self.active_risks.values(), key=lambda r: r["seq"])

    def get_blocked_waypoints(self) -> Set[str]:
        blocked: Set[str] = set()
        for risk in self.active_risks.values():
            if risk["active"] and risk["type"] == RiskType.TRAFFIC_CONGESTION:
                blocked.update(risk["affected_waypoints"])
        return blocked

    def get_paused_job_locations(self) -> Set[str]:
        paused: Set[str] = set()
        for risk in self.active_risks.values():
            if risk["active"] and risk["type"] in (
                    RiskType.FIRE, RiskType.NO_HELMET):
                paused.add(risk["target_id"])
        return paused

    def is_zone_paused(self, zone_name: str) -> bool:
        for risk in self.active_risks.values():
            if (risk["active"]
                    and risk["type"] == RiskType.PERSONNEL_INTRUSION
                    and risk["zone"] == zone_name):
                return True
        return False

    def has_agv_failure(self, agv_id: str) -> bool:
        return any(r["active"] and r["type"] == RiskType.AGV_FAILURE
                   and r.get("agv_id") == agv_id
                   for r in self.active_risks.values())

    def clear_risk(self, risk_id: str) -> bool:
        risk = self.active_risks.pop(risk_id, None)
        if risk is None:
            return False
        risk["active"] = False
        return True

    def clear_all_risks(self) -> None:
        for risk in self.active_risks.values():
            risk["active"] = False
        self.active_risks = {}

    def clear_agv_failure(self, agv_id: str) -> None:
        for rid, risk in list(self.active_risks.items()):
            if (risk["type"] == RiskType.AGV_FAILURE
                    and risk.get("agv_id") == agv_id):
                self.clear_risk(rid)

    def tick(self, current_time: int) -> List[Dict[str, Any]]:
        expired: List[Dict[str, Any]] = []
        for rid, risk in list(self.active_risks.items()):
            duration = risk.get("duration", self.cfg.risk.default_duration)
            if duration >= self.cfg.risk.default_duration:
                continue
            if current_time - risk["created_time"] >= duration:
                risk["active"] = False
                expired.append(risk)
                self.active_risks.pop(rid, None)
        return expired

    def to_payload(self) -> List[Dict[str, Any]]:
        out = []
        for risk in self.get_all_risks():
            out.append({
                "id": risk["id"],
                "seq": risk["seq"],
                "type": risk["type"],
                "label": risk["label"],
                "severity": risk["severity"],
                "zone": risk["zone"],
                "targetId": risk["target_id"],
                "agvId": risk.get("agv_id"),
                "locationWp": risk["location_wp"],
                "position": risk["display_pos"],
                "message": risk["message"],
                "source": risk["source"],
                "createdTime": risk["created_time"],
                "affectedCount": len(risk["affected_waypoints"]),
                "affectedWaypoints": risk["affected_waypoints"][:400],
            })
        return out
