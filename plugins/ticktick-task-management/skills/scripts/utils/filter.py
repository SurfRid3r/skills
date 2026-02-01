"""Task Filter Utilities

Provides filtering functionality for tasks based on expressions.
"""

from datetime import datetime, timedelta, date
from typing import Any, Callable, Dict, List

# Supported operators
_OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}

# Named priority levels → numeric
_PRIORITY_MAP = {"none": 0, "low": 1, "medium": 3, "high": 5}


def _parse_iso_date(s: str) -> date:
    """Parse ISO date string.
    
    Uses standard library datetime.fromisoformat() for ISO format parsing.
    
    Args:
        s: ISO date string (e.g., "2025-07-02T16:00:00.000+0000")
    
    Returns:
        Parsed date
    """
    try:
        # Handle various ISO formats - normalize timezone format
        normalized = s.replace('Z', '+00:00')
        # Remove milliseconds if present for compatibility
        if '.' in normalized:
            normalized = normalized.split('.')[0] + normalized.split('.')[-1][-6:]
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        # Fallback: try without timezone
        return datetime.fromisoformat(s.split('+')[0].split('Z')[0]).date()


def _resolve_date_keyword(kw: str) -> date:
    """Resolve date keyword to actual date.
    
    Args:
        kw: Date keyword (yesterday, today, tomorrow) or ISO format
    
    Returns:
        Resolved date
    """
    today = datetime.now().date()
    kw_lower = kw.lower()

    if kw_lower == "yesterday":
        return today - timedelta(days=1)
    if kw_lower == "today":
        return today
    if kw_lower == "tomorrow":
        return today + timedelta(days=1)

    # Try parsing as ISO date
    try:
        normalized = kw.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(normalized)
        return parsed.date()
    except ValueError:
        # Fallback to simple date format
        return datetime.strptime(kw, "%Y-%m-%d").date()


def _build_predicate(expr: str) -> Callable[[Dict[Any, Any]], bool]:
    """Build a predicate function from filter expression.

    Args:
        expr: Filter expression like "dueDate == tomorrow"

    Returns:
        Predicate function that returns True/False for each task
    """
    parts = expr.split(maxsplit=2)
    if len(parts) != 3:
        raise ValueError(f"Invalid filter expression: {expr!r}")
    field, op, raw_val = parts

    if op not in _OPERATORS:
        raise ValueError(f"Unsupported operator {op!r} in {expr!r}")

    cmp_fn = _OPERATORS[op]

    def predicate(task: Dict[Any, Any]) -> bool:
        if field not in task:
            return False
        val = task[field]

        # Date fields
        if "date" in field.lower():
            try:
                actual = _parse_iso_date(val)
            except Exception:
                return False
            expected = _resolve_date_keyword(raw_val)
            return cmp_fn(actual, expected)

        # Priority keyword or numeric
        if field.lower() == "priority":
            actual = int(val)
            expected = _PRIORITY_MAP.get(raw_val.lower(), None)
            if expected is None:
                expected = int(raw_val)
            return cmp_fn(actual, expected)

        # Numeric fields
        if isinstance(val, (int, float)):
            return cmp_fn(val, type(val)(raw_val))

        # String comparison
        return cmp_fn(str(val), raw_val)

    return predicate


def filter_task(
    tasks: List[Dict[Any, Any]], filter_fields: List[str]
) -> List[Dict[Any, Any]]:
    """Filter tasks by expressions.

    Returns only tasks for which **all** filter expressions match.

    Args:
        tasks: List of tasks to filter
        filter_fields: List of filter expressions like ["dueDate <= tomorrow", "priority >= high"]

    Returns:
        Filtered list of tasks
    """
    preds = [_build_predicate(expr) for expr in filter_fields]
    return [task for task in tasks if all(pred(task) for pred in preds)]
