"""Polling connector for the camera analytics model service."""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from rcds.models.config import Config
from rcds.models.logger import get_logger
from rcds.models.models import RiskType
from rcds.safety.risk import RiskManager

logger = get_logger("rcds.safety.api")

ENDPOINT_SPECS: List[Dict[str, Any]] = [
    {
        "key": "fire", "path": "/model/fire", "label": "Fire & Smoke",
        "scope": ["QC_Area", "YARD_Area"], "format": "jpg",
        "riskType": RiskType.FIRE, "metric": "fire_num",
    },
    {
        "key": "smoke", "path": "/model/smoke", "label": "Smoking",
        "scope": ["QC_Area", "YARD_Area"], "format": "jpg",
        "riskType": RiskType.SMOKING, "metric": "smoke_num",
    },
    {
        "key": "helmet", "path": "/model/helmet", "label": "Helmet",
        "scope": ["QC_Area", "YARD_Area"], "format": "jpg",
        "riskType": RiskType.NO_HELMET, "metric": "worker_num",
    },
    {
        "key": "worker", "path": "/model/worker", "label": "Personnel Intrusion",
        "scope": ["Highway_Area"], "format": "mp4",
        "riskType": RiskType.PERSONNEL_INTRUSION, "metric": "worker_num",
    },
    {
        "key": "traffic_jam", "path": "/model/traffic_jam",
        "label": "Traffic Congestion",
        "scope": ["Highway_Area"], "format": "mp4",
        "riskType": RiskType.TRAFFIC_CONGESTION, "metric": "warn",
    },
]

class ModelServiceClient:
    def __init__(self) -> None:
        self.cfg = Config.get()
        self.api = self.cfg.api
        self.last_results: Dict[str, Dict[str, Any]] = {}

    def call(self, endpoint: str, media_urls: List[str],
             media_format: str = "jpg") -> Optional[Dict[str, Any]]:
        if self.api.use_real_api:
            return self._http_call(endpoint, media_urls, media_format)
        return self._mock_call(endpoint)

    def _http_call(self, endpoint: str, media_urls: List[str],
                   media_format: str) -> Optional[Dict[str, Any]]:
        base = self.api.model_server_base_url.rstrip("/")
        query = urllib.parse.urlencode(
            {"format": media_format, "url": media_urls}, doseq=True)
        url = f"{base}{endpoint}?{query}"
        try:
            with urllib.request.urlopen(
                    url, timeout=self.api.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.warning(f"model service call failed {endpoint}: {exc}")
            return None

    def _mock_call(self, endpoint: str) -> Dict[str, Any]:
        hit = random.random() < self.api.mock_detect_probability
        return {
            "status": "success",
            "mock": True,
            "data": [{
                "warn": 1 if hit else 0,
                "fire_num": 1 if hit and endpoint == "/model/fire" else 0,
                "worker_num": 1 if hit and endpoint in
                ("/model/worker", "/model/helmet") else 0,
                "smoke_num": 1 if hit and endpoint == "/model/smoke" else 0,
            }],
        }

    def status_payload(self, enabled: bool) -> Dict[str, Any]:
        endpoints = []
        for spec in ENDPOINT_SPECS:
            last = self.last_results.get(spec["key"], {})
            endpoints.append({
                "key": spec["key"],
                "path": spec["path"],
                "label": spec["label"],
                "scope": spec["scope"],
                "format": spec["format"],
                "riskType": spec["riskType"],
                "lastWarn": last.get("warn"),
                "lastTime": last.get("time"),
                "lastDetail": last.get("detail", ""),
            })
        return {
            "enabled": enabled,
            "realApi": self.api.use_real_api,
            "baseUrl": self.api.model_server_base_url,
            "pollTicks": self.cfg.risk.api_poll_ticks,
            "endpoints": endpoints,
            "cameras": self.api.camera_urls,
        }

def _is_warned(response: Optional[Dict[str, Any]], spec: Dict[str, Any]) -> bool:
    if not response or response.get("status") != "success":
        return False
    data = response.get("data") or [{}]
    first = data[0]
    if first.get("warn", 0) > 0:
        return True
    metric = spec.get("metric")
    return bool(metric and first.get(metric, 0) > 0)

def check_risk_models(
    risk_manager: RiskManager,
    client: ModelServiceClient,
    current_time: int,
) -> List[Dict[str, Any]]:
    """
    Poll every model endpoint and turn hits into risks.

    Returns the detections created by this pass, for the reschedule log and
    the API panel.
    """
    cfg = Config.get()
    job_points = _job_points_by_area()
    detections: List[Dict[str, Any]] = []

    for spec in ENDPOINT_SPECS:
        key = spec["key"]
        scope = spec["scope"]

        zone = scope[0]
        urls = cfg.api.camera_urls.get(zone) or []
        camera_url = urls[0] if urls else f"mock://{zone}"

        response = client.call(spec["path"], [camera_url], spec["format"])
        hit = _is_warned(response, spec)

        detail = ""
        target_jp: Optional[str] = None
        target_zone: Optional[str] = None

        if hit:
            if zone == "Highway_Area":
                target_zone = "Highway_Area"
                detail = "Area-level alert"
            else:

                candidates = []
                for area_zone in scope:
                    candidates.extend(job_points.get(area_zone, []))
                if candidates:
                    target_jp = random.choice(candidates)
                    detail = f"Job point {target_jp}"
                else:
                    target_zone = zone
                    detail = "Area-level alert"

            risk_id = risk_manager.add_risk(
                spec["riskType"],
                zone=target_zone,
                job_point_id=target_jp,
                duration=cfg.risk.api_risk_duration,
                current_time=current_time,
                source="api",
            )
            if risk_id:
                detections.append({
                    "endpoint": spec["path"],
                    "label": spec["label"],
                    "riskType": spec["riskType"],
                    "location": detail,
                })
                logger.info(f"[API] {spec['label']} hit -> {detail}")

        client.last_results[key] = {
            "warn": 1 if hit else 0,
            "time": current_time,
            "detail": detail or "OK",
        }

    return detections

def _job_points_by_area() -> Dict[str, List[str]]:
    from rcds.port.network import get_job_points
    out: Dict[str, List[str]] = {}
    for jp_id, info in get_job_points().items():
        out.setdefault(info["areaNo"], []).append(jp_id)
    return out
