"""Constants for Dida365 MCP Server.

Centralizes magic numbers and strings used across the codebase.
"""

from typing import Dict


# ================================
# Task Status
# ================================

class TaskStatus:
    """Task status values."""
    INCOMPLETE = 0
    COMPLETED = 2


# ================================
# Priority
# ================================

class Priority:
    """Priority level values."""
    NONE = 0
    LOW = 1
    MEDIUM = 3
    HIGH = 5


PRIORITY_NAMES: Dict[int, str] = {
    Priority.NONE: "none",
    Priority.LOW: "low",
    Priority.MEDIUM: "medium",
    Priority.HIGH: "high",
}

PRIORITY_VALUES: Dict[str, int] = {
    "none": Priority.NONE,
    "low": Priority.LOW,
    "medium": Priority.MEDIUM,
    "high": Priority.HIGH,
}


# ================================
# Habit
# ================================

class HabitType:
    """Habit type values."""
    BOOLEAN = "Boolean"
    COUNTER = "Counter"


class HabitDefaults:
    """Default values for habit creation."""
    COLOR = "#97E38B"
    ICON_RES = "habit_daily_check_in"
    REPEAT_RULE_DAILY = "RRULE:FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA"
    GOAL = 1.0
    STEP = 0.0
    UNIT = "Count"
    TYPE = HabitType.BOOLEAN
    TARGET_DAYS = 0
    SECTION_ID = "-1"
    SORT_ORDER = -1099511627776
    STATUS = 0
    TOTAL_CHECK_INS = 0
    COMPLETED_CYCLES = 0
    CURRENT_STREAK = 0
    STYLE = 1


# ================================
# Comment
# ================================

class CommentDefaults:
    """Default values for comment creation."""
    USER_PROFILE_IS_MYSELF = True
    IS_NEW = True


# ================================
# Project
# ================================

class ProjectKind:
    """Project type values."""
    TASK = "TASK"
    NOTE = "NOTE"


class ViewMode:
    """Project view mode values."""
    LIST = "list"
    KANBAN = "kanban"
    TIMELINE = "timeline"


# ================================
# API
# ================================

class API:
    """API-related constants."""
    BASE_URL = "https://dida365.com"
    API_PREFIX = "/api/v2"
    V3_API_PREFIX = "/api/v3"
