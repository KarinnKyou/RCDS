from __future__ import annotations

import random
from typing import Any, Dict, List

from rcds.models.config import Config
from rcds.models.logger import get_logger
from rcds.models.models import TaskStatus, TaskType
from rcds.port.network import get_job_points

logger = get_logger("rcds.core.tasks")


class TaskManager:

    def __init__(self) -> None:
        self.cfg = Config.get()
        self._task_id_counter = 0

    def generate_tasks(self, num_tasks: int,
                       current_time: int = 0) -> List[Dict[str, Any]]:
        job_points = get_job_points()
        if not job_points:
            logger.warning("Job points not loaded, cannot generate tasks")
            return []

        seaside = [jp for jp, info in job_points.items()
                   if any(kw in info.get("areaNo", "")
                          for kw in self.cfg.area.seaside_area_keywords)]
        yard = [jp for jp, info in job_points.items()
                if any(kw in info.get("areaNo", "")
                       for kw in self.cfg.area.yard_area_keywords)]

        if not seaside or not yard:
            logger.warning(
                "Incomplete job points (need both QC_Area and YARD_Area), "
                "cannot generate tasks")
            return []

        tasks: List[Dict[str, Any]] = []
        for _ in range(max(0, int(num_tasks))):
            task_type = random.choice([TaskType.IMPORT, TaskType.EXPORT])
            if task_type == TaskType.IMPORT:
                pickup, dropoff = random.choice(seaside), random.choice(yard)
            else:
                pickup, dropoff = random.choice(yard), random.choice(seaside)
            tasks.append(self._create_task(task_type, pickup, dropoff,
                                           current_time))

        logger.info(f"Generated {len(tasks)} tasks "
                    f"({len(seaside)} seaside job points / "
                    f"{len(yard)} yard job points)")
        return tasks

    def _create_task(self, task_type: str, pickup: str, dropoff: str,
                     created_time: int) -> Dict[str, Any]:
        task = {
            "id": f"Task-{self._task_id_counter}",
            "type": task_type,
            "pickup_loc_id": pickup,
            "dropoff_loc_id": dropoff,
            "status": TaskStatus.PENDING,
            "assigned_agv_id": None,
            "created_time": created_time,
            "assigned_time": None,
            "completed_time": None,
        }
        self._task_id_counter += 1
        return task

    def reset(self) -> None:
        self._task_id_counter = 0
