"""Project service for Dida365 API."""

import logging
from typing import Any, Dict, List, Literal, Optional

from .base import BaseService
from .exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class ProjectService(BaseService):
    """Service for project-related operations."""

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all projects including groups."""
        api_projects = await self._make_request("GET", "/projects")

        try:
            project_group_ids = await self._get_project_group_ids()
            sync_data = await self._make_request("GET", "/v3/batch/check/0", base="https://api.dida365.com/api")

            project_groups = sync_data.get('projectGroups', [])
            for group in project_groups:
                if group.get('deleted') or group.get('id') not in project_group_ids:
                    continue

                group_project = {
                    'id': group['id'],
                    'name': group['name'],
                    'isOwner': True,
                    'kind': 'TASK',
                    'viewMode': group.get('viewMode') or 'list',
                    'inAll': group.get('showAll', True),
                    'closed': None,
                    'sortOrder': group.get('sortOrder', 0),
                    'sortType': group.get('sortType'),
                    '_group': True,
                }
                api_projects.append(group_project)
                logger.debug(f"Added project group: {group['name']} (id={group['id']})")

        except Exception as e:
            logger.warning(f"Failed to get project groups from batch sync: {e}")

        existing_ids = {p.get('id') for p in api_projects if p.get('id')}
        has_inbox = any(pid.startswith('inbox') for pid in existing_ids)

        if not has_inbox:
            try:
                from .tasks import TaskService
                task_service = TaskService(self.auth, self.base_url, self.timeout)
                all_tasks = await task_service.get_all()

                inbox_id = None
                for task in all_tasks:
                    pid = task.get('projectId', '')
                    if pid.startswith('inbox'):
                        inbox_id = pid
                        break

                if inbox_id:
                    inbox_project = {
                        'id': inbox_id,
                        'name': '📥 收集箱',
                        'isOwner': True,
                        'kind': 'TASK',
                        'viewMode': 'list',
                        'inAll': True,
                        'closed': None,
                        'sortOrder': -9999999999999,
                    }
                    api_projects.insert(0, inbox_project)
                    logger.debug(f"Added Inbox project (id={inbox_id}) to project list")

            except Exception as e:
                logger.warning(f"Failed to discover Inbox project: {e}")

        return api_projects

    async def get_by_id(self, project_id: str) -> Dict[str, Any]:
        """Get project by ID."""
        projects = await self.get_all()
        for project in projects:
            if project.get("id") == project_id:
                return project

        if await self._is_project_group(project_id):
            try:
                sync_data = await self._make_request("GET", "/v3/batch/check/0", base="https://api.dida365.com/api")
                project_groups = sync_data.get('projectGroups', [])
                for group in project_groups:
                    if group['id'] == project_id and not group.get('deleted'):
                        return {
                            'id': group['id'],
                            'name': group['name'],
                            'isOwner': True,
                            'kind': 'GROUP',
                            'viewMode': group.get('viewMode') or 'list',
                            'inAll': group.get('showAll', True),
                            'closed': None,
                            'sortOrder': group.get('sortOrder', 0),
                            'sortType': group.get('sortType'),
                            '_group': True,
                        }
            except Exception:
                pass

        raise ResourceNotFoundError(f"Project {project_id} not found")

    async def create(
        self,
        name: str,
        color: Optional[str] = None,
        sort_order: Optional[int] = None,
        view_mode: Optional[Literal["list", "kanban", "timeline"]] = None,
        kind: Optional[Literal["TASK", "NOTE"]] = None,
    ) -> Dict[str, Any]:
        """Create a project."""
        data = self._build_data(
            name=name,
            color=color,
            sortOrder=sort_order,
            viewMode=view_mode,
            kind=kind,
        )
        return await self._make_request("POST", "/project", data=data)

    async def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        sort_order: Optional[int] = None,
        view_mode: Optional[Literal["list", "kanban", "timeline"]] = None,
        kind: Optional[Literal["TASK", "NOTE"]] = None,
    ) -> Dict[str, Any]:
        """Update a project."""
        data = self._build_data(
            id=project_id,
            name=name,
            color=color,
            sortOrder=sort_order,
            viewMode=view_mode,
            kind=kind,
        )

        result = await self._make_request("POST", "/batch/project", data=self._build_batch_data(update=[data]))

        if isinstance(result, dict) and result.get("id2error", {}).get(project_id):
            from .exceptions import DidaAPIError
            raise DidaAPIError(result['id2error'][project_id])

        return await self.get_by_id(project_id)

    async def delete(self, project_id: str) -> Dict[str, Any]:
        """Delete a project."""
        return await self._make_request("DELETE", f"/project/{project_id}")

    async def get_details(
        self, project_id: str, tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get project data with tasks."""
        project = await self.get_by_id(project_id)

        project_tasks = [
            task for task in tasks
            if task.get('projectId') == project_id
        ]

        return {
            "project": project,
            "tasks": project_tasks
        }

    def get_tasks_from_all(
        self, project_id: str, all_tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter tasks for a specific project from all tasks."""
        return [
            task for task in all_tasks
            if task.get('projectId') == project_id
        ]
