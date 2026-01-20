"""Data Formatter Utilities

Provides formatting functions for tasks, projects, and other data.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, Dict, List

from api.constants import PRIORITY_NAMES, PRIORITY_VALUES


def format_task(task: Dict[Any, Any]) -> str:
    """Format task data for display.

    Args:
        task: Task data dictionary

    Returns:
        Formatted task string
    """
    lines: List[str] = []

    # Subtasks
    items = task.get("items") or []
    if items:
        lines.append("Subtasks:")
        for idx, sub in enumerate(items, 1):
            fields = "; ".join(
                f"{k}: {v}"
                for k, v in sub.items()
                if v not in (None, "", [], {}) and k != "timeZone"
            )
            lines.append(f"  {idx}. {fields}")

    # Tags
    tags = task.get("tags") or []
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    # Other task fields
    skip = {"items", "tags"}
    for k, v in task.items():
        if k in skip or v in (None, "", [], {}):
            continue

        # Format priority as name
        if k == "priority":
            v = f"{v} ({PRIORITY_NAMES.get(v, 'unknown')})"

        lines.append(f"{k}: {v}")

    # Add current time
    lines.append(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)


def format_project(project: Dict[Any, Any]) -> str:
    """Format project data for display.

    Args:
        project: Project data dictionary

    Returns:
        Formatted project string
    """
    return "\n".join(
        f"{k}: {v}" for k, v in project.items() if v not in (None, "", [], {})
    )


def format_project_tree(projects: List[Dict[str, Any]]) -> str:
    """Render a list/sublist hierarchy based on groupId references.

    Args:
        projects: List of projects

    Returns:
        Formatted tree structure string
    """
    by_id: Dict[str, Dict[str, Any]] = {
        p["id"]: p for p in projects if isinstance(p.get("id"), str)
    }
    children: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    roots: List[Dict[str, Any]] = []

    for project in projects:
        group_id = project.get("groupId")
        if group_id and group_id in by_id:
            children[group_id].append(project)
        else:
            roots.append(project)

    def render(node: Dict[str, Any], depth: int = 0) -> List[str]:
        indent = "  " * depth
        basics = f"{indent}- {node.get('name')} (id={node.get('id')})"
        extras = []

        # Check if this is a project group (not a regular project)
        if node.get("_group"):
            extras.append("GROUP")
        elif node.get("kind"):
            extras.append(node["kind"])

        if node.get("groupId") and node.get("groupId") not in (None, ""):
            extras.append(f"groupId={node['groupId']}")
        if node.get("closed"):
            extras.append("closed")

        detail = f" [{' | '.join(extras)}]" if extras else ""
        lines = [basics + detail]

        for child in sorted(children.get(node.get("id"), []), key=lambda c: c.get("sortOrder", 0)):
            lines.extend(render(child, depth + 1))

        return lines

    rendered: List[str] = []
    for root in sorted(roots, key=lambda r: r.get("sortOrder", 0)):
        rendered.extend(render(root))

    return "\n".join(rendered)
