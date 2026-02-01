"""Habits service for Dida365 API.

API endpoints verified via browser testing at https://dida365.com/webapp/
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseService
from ..constants import HabitDefaults, HabitType

logger = logging.getLogger(__name__)


class HabitService(BaseService):
    """Service for habit-related operations."""

    async def list_all(self) -> List[Dict[str, Any]]:
        """Get all habits."""
        result = await self._make_request("GET", "/habits")
        return result if isinstance(result, list) else []

    async def get_sections(self) -> List[Dict[str, Any]]:
        """Get all habit sections/groups."""
        result = await self._make_request("GET", "/habitSections")
        return result if isinstance(result, list) else []

    async def query_checkins(
        self,
        habit_ids: List[str],
        after_stamp: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Query check-in records for specific habits."""
        if after_stamp is None:
            after_stamp = int(datetime.now().strftime("%Y%m%d"))

        data = {
            "habitIds": habit_ids,
            "afterStamp": after_stamp,
        }
        return await self._make_request("POST", "/habitCheckins/query", data=data)

    async def get_records(
        self,
        habit_ids: List[str],
        after_stamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get habit records with detailed information."""
        if after_stamp is None:
            after_stamp = int(datetime.now().strftime("%Y%m%d"))

        data = {
            "habitIds": habit_ids,
            "afterStamp": after_stamp,
        }
        return await self._make_request("POST", "/getHabitRecords", data=data)

    async def create(
        self,
        name: str,
        color: str = HabitDefaults.COLOR,
        icon_res: str = HabitDefaults.ICON_RES,
        repeat_rule: str = HabitDefaults.REPEAT_RULE_DAILY,
        goal: float = HabitDefaults.GOAL,
        step: float = HabitDefaults.STEP,
        unit: str = HabitDefaults.UNIT,
        habit_type: str = HabitDefaults.TYPE,
        target_days: int = HabitDefaults.TARGET_DAYS,
        section_id: str = HabitDefaults.SECTION_ID,
        reminders: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new habit."""
        now = self._get_iso_timestamp()
        habit_id = f"{int(time.time() * 1000):x}{uuid.uuid4().hex[:12]}"

        habit_data = {
            "id": habit_id,
            "name": name,
            "color": color,
            "iconRes": icon_res,
            "createdTime": now,
            "modifiedTime": now,
            "encouragement": "",
            "etag": "",
            "goal": goal,
            "step": step,
            "unit": unit,
            "type": habit_type,
            "repeatRule": repeat_rule,
            "sortOrder": HabitDefaults.SORT_ORDER,
            "status": HabitDefaults.STATUS,
            "totalCheckIns": HabitDefaults.TOTAL_CHECK_INS,
            "sectionId": section_id,
            "targetDays": target_days,
            "targetStartDate": int(datetime.now().strftime("%Y%m%d")),
            "completedCycles": HabitDefaults.COMPLETED_CYCLES,
            "exDates": [],
            "recordEnable": False,
            "reminders": reminders or [],
            "currentStreak": HabitDefaults.CURRENT_STREAK,
            "style": HabitDefaults.STYLE,
        }

        return await self._make_request("POST", "/habits/batch", data=self._build_batch_data(add=[habit_data]))

    async def update(
        self,
        habit_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        goal: Optional[float] = None,
        repeat_rule: Optional[str] = None,
        reminders: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update an existing habit."""
        habits = await self.list_all()
        current_habit = next((h for h in habits if h["id"] == habit_id), None)
        if not current_habit:
            raise ValueError(f"Habit {habit_id} not found")

        update_data = {**current_habit}
        if name is not None:
            update_data["name"] = name
        if color is not None:
            update_data["color"] = color
        if goal is not None:
            update_data["goal"] = goal
        if repeat_rule is not None:
            update_data["repeatRule"] = repeat_rule
        if reminders is not None:
            update_data["reminders"] = reminders

        for key, value in kwargs.items():
            if value is not None and key in update_data:
                update_data[key] = value

        update_data["modifiedTime"] = self._get_iso_timestamp()

        return await self._make_request("POST", "/habits/batch", data=self._build_batch_data(update=[update_data]))

    async def delete(self, habit_id: str) -> None:
        """Delete a habit."""
        await self._make_request("POST", "/habits/batch", data=self._build_batch_data(delete=[habit_id]))

    async def batch_operations(
        self,
        add: Optional[List[Dict[str, Any]]] = None,
        update: Optional[List[Dict[str, Any]]] = None,
        delete: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Perform batch operations on habits."""
        return await self._make_request("POST", "/habits/batch", data=self._build_batch_data(add, update, delete))
