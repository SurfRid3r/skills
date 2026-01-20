"""Task service for Dida365 API."""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseService
from .exceptions import ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)


class TaskService(BaseService):
    """Service for task-related operations."""

    async def _get_all_tasks_v3(self, since: Optional[str] = None) -> Dict[str, Any]:
        """Get all tasks using v3 batch endpoint."""
        endpoint = f"/api/v3/batch/check/{since}" if since else "/api/v3/batch/check/0"
        return await self._make_request("GET", endpoint, base=self.base_url)

    async def get_by_id(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """Get task by project and task ID."""
        result = await self._get_all_tasks_v3()

        if 'syncTaskBean' in result and 'update' in result['syncTaskBean']:
            for task in result['syncTaskBean']['update']:
                if task.get('id') == task_id and task.get('projectId') == project_id:
                    return task

        raise ResourceNotFoundError(f"Task {task_id} not found in project {project_id}")

    async def find(
        self, task_id: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find a task optionally across projects."""
        if project_id:
            task = await self.get_by_id(project_id, task_id)
            return {"projectId": project_id, "task": task}

        from .projects import ProjectService
        project_service = ProjectService(self.auth, self.base_url, self.timeout)
        projects = await project_service.get_all()

        for project in projects:
            pid = project.get("id")
            if not pid:
                continue
            try:
                task = await self.get_by_id(pid, task_id)
                return {"projectId": pid, "task": task}
            except ResourceNotFoundError:
                continue

        raise ResourceNotFoundError(f"Task {task_id} not found")

    async def list_in_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all tasks in a project."""
        all_tasks = await self._get_all_tasks_v3()
        tasks = []

        if 'syncTaskBean' in all_tasks and 'update' in all_tasks['syncTaskBean']:
            for task in all_tasks['syncTaskBean']['update']:
                if task.get('projectId') == project_id:
                    tasks.append(task)

        return tasks

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all tasks across all projects."""
        result = await self._get_all_tasks_v3()
        if 'syncTaskBean' in result and 'update' in result['syncTaskBean']:
            return result['syncTaskBean']['update']
        return []

    @staticmethod
    def _ensure_content_with_items(
        title: Optional[str], content: Optional[str], items: Optional[list]
    ) -> Optional[str]:
        """Ensure content exists when items are present."""
        if not items:
            return content
        if content and str(content).strip():
            return content

        summary_title = title or "Task"
        summary_lines = [f"{summary_title} 包含以下步骤："]
        for item in items:
            label = item.get("title") or "(未命名子任务)"
            summary_lines.append(f"- {label}")
        return "\n".join(summary_lines)

    @staticmethod
    def _validate_items_for_update(items: Optional[list]) -> None:
        """Validate items have ids for update."""
        if not items:
            return
        missing = [item for item in items if not item.get("id")]
        if missing:
            raise ValidationError(
                "update_task requires checklist items to include 'id'. "
                "Fetch the existing task first, merge items with their ids, "
                "and pass the full list back."
            )

    async def create(
        self,
        project_id: str,
        title: str,
        content: Optional[str] = None,
        is_all_day: Optional[bool] = None,
        start_date: Optional[str] = None,
        due_date: Optional[str] = None,
        time_zone: Optional[str] = None,
        reminders: Optional[list] = None,
        repeat_flag: Optional[str] = None,
        priority: Optional[int] = None,
        sort_order: Optional[int] = None,
        tags: Optional[list] = None,
        items: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Create a task."""
        if await self._is_project_group(project_id):
            raise ValidationError(
                f"Cannot create task in project group '{project_id}'. "
                "Project groups are containers for organizing projects, not for storing tasks. "
                "Please create the task in a specific project instead."
            )

        content = self._ensure_content_with_items(title, content, items)

        data = self._build_data(
            projectId=project_id,
            title=title,
            desc=content,
            isAllDay=is_all_day,
            startDate=start_date,
            dueDate=due_date,
            timeZone=time_zone,
            reminders=reminders,
            repeatFlag=repeat_flag,
            priority=priority,
            sortOrder=sort_order,
            tags=tags,
            items=items,
        )

        return await self._make_request("POST", "/task", data=data)

    async def update(
        self,
        task_id: str,
        project_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        is_all_day: Optional[bool] = None,
        start_date: Optional[str] = None,
        due_date: Optional[str] = None,
        time_zone: Optional[str] = None,
        reminders: Optional[list] = None,
        repeat_flag: Optional[str] = None,
        priority: Optional[int] = None,
        sort_order: Optional[int] = None,
        tags: Optional[list] = None,
        items: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Update a task."""
        self._validate_items_for_update(items)
        content = self._ensure_content_with_items(title, content, items)

        data = self._build_data(
            id=task_id,
            projectId=project_id,
            title=title,
            desc=content,
            isAllDay=is_all_day,
            startDate=start_date,
            dueDate=due_date,
            timeZone=time_zone,
            reminders=reminders,
            repeatFlag=repeat_flag,
            priority=priority,
            sortOrder=sort_order,
            tags=tags,
            items=items,
        )

        return await self._make_request("POST", f"/task/{task_id}", data=data)

    async def complete(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """Complete a task."""
        from .exceptions import TaskStatus

        update_data = {
            "id": task_id,
            "projectId": project_id,
            "status": TaskStatus.COMPLETED
        }

        return await self._make_request("POST", "/batch/task", data=self._build_batch_data(update=[update_data]))

    async def delete(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        delete_data = [{"taskId": task_id, "projectId": project_id}]
        return await self._make_request("POST", "/batch/task", data=self._build_batch_data(delete=delete_data))

    async def move(
        self,
        task_id: str,
        from_project_id: str,
        to_project_id: str,
    ) -> Dict[str, Any]:
        """Move a task by cloning then deleting."""
        if await self._is_project_group(to_project_id):
            raise ValidationError(
                f"Cannot move task to project group '{to_project_id}'. "
                "Project groups are containers for organizing projects, not for storing tasks. "
                "Please move the task to a specific project instead."
            )

        task = await self.get_by_id(from_project_id, task_id)

        new_task = await self.create(
            to_project_id,
            title=task.get("title") or "",
            content=task.get("desc"),
            is_all_day=task.get("isAllDay"),
            start_date=task.get("startDate"),
            due_date=task.get("dueDate"),
            time_zone=task.get("timeZone"),
            reminders=task.get("reminders"),
            repeat_flag=task.get("repeatFlag"),
            priority=task.get("priority"),
            sort_order=task.get("sortOrder"),
            tags=task.get("tags"),
            items=self._clone_items(task.get("items")),
        )

        if not isinstance(new_task, dict) or not new_task.get("id"):
            from .exceptions import DidaAPIError
            raise DidaAPIError("Failed to recreate task in destination project")

        await self.delete(from_project_id, task_id)

        return new_task

    @staticmethod
    def _clone_items(items: Optional[list]) -> Optional[list]:
        """Clone task items, keeping only safe fields."""
        if not items:
            return None

        safe_fields = {"title", "isAllDay", "startDate", "dueDate", "timeZone", "sortOrder"}
        return [
            {k: v for k, v in item.items() if k in safe_fields}
            for item in items
        ]

    async def search(self, keywords: str) -> Dict[str, Any]:
        """Full-text search for tasks."""
        return await self._make_request("GET", f"/search/all?keywords={keywords}")

    async def get_completed_tasks(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: str = "Completed",
    ) -> List[Dict[str, Any]]:
        """Get completed tasks."""
        params = {"from": from_date or "", "to": to_date or "", "status": status}
        result = await self._make_request("GET", "/project/all/closed", params=params)
        return result if isinstance(result, list) else []

    async def get_completed_in_all(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get completed tasks statistics across all projects."""
        from datetime import datetime

        to = to_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        endpoint = f"/project/all/completedInAll/?from={from_date or ''}&to={to}&limit={limit}"
        return await self._make_request("GET", endpoint)

    async def batch_update_tasks(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update tasks."""
        return await self._make_request("POST", "/batch/task", data=self._build_batch_data(update=updates))

    async def batch_delete_tasks(self, deletes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch delete tasks."""
        return await self._make_request("POST", "/batch/task", data=self._build_batch_data(delete=deletes))

    async def batch_move(
        self,
        task_moves: List[Dict[str, Any]],
        to_project_id: str,
    ) -> List[Dict[str, Any]]:
        """Batch move tasks to a different project."""
        moved_tasks = []
        for move_info in task_moves:
            task_id = move_info.get("taskId")
            from_project_id = move_info.get("projectId")
            if not task_id or not from_project_id:
                continue
            new_task = await self.move(task_id, from_project_id, to_project_id)
            moved_tasks.append(new_task)
        return moved_tasks
