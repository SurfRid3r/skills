"""Tag service for Dida365 API."""

import logging
from typing import Any, Callable, Dict, List, Optional

from .base import BaseService
from .exceptions import DidaAPIError

logger = logging.getLogger(__name__)


class TagService(BaseService):
    """Service for tag-related operations."""

    async def _scan_tasks_with_tag(
        self, tag_filter: Callable[[List[str]], bool]
    ) -> List[Dict[str, Any]]:
        """Scan all tasks and return those matching the tag filter.

        Args:
            tag_filter: Function that takes task tags list and returns True if task should be included

        Returns:
            List of tasks matching the filter
        """
        from .tasks import TaskService
        from .projects import ProjectService

        task_service = TaskService(self.auth, self.base_url, self.timeout)
        project_service = ProjectService(self.auth, self.base_url, self.timeout)

        try:
            projects = await project_service.get_all()
            matching_tasks = []

            for project in projects:
                project_id = project.get("id")
                if not project_id:
                    continue
                tasks = await task_service.list_in_project(project_id)
                matching_tasks.extend(
                    task for task in tasks
                    if tag_filter(task.get("tags") or [])
                )

            return matching_tasks
        finally:
            await task_service.close()
            await project_service.close()

    async def list_all(self) -> List[str]:
        """List all tags by scanning tasks.

        Returns:
            Sorted list of tag names
        """
        tags = set()
        tasks_with_tags = await self._scan_tasks_with_tag(lambda tags: True)

        for task in tasks_with_tags:
            for tag in task.get("tags") or []:
                tags.add(tag)

        return sorted(tags)

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all tags by scanning tasks.

        Note: The GET /tag API endpoint is not available in Dida365,
        so we use task scanning as the primary method.

        Returns:
            List of tag objects with name, color, parent, etc.
        """
        tag_names = await self.list_all()
        return [{"name": tag, "color": None, "parent": None} for tag in tag_names]

    async def upsert(self, name: str, **kwargs) -> Dict[str, Any]:
        """Create or update a tag.

        Args:
            name: Tag name
            **kwargs: Additional tag properties (color, parent, etc.)

        Returns:
            Updated tag object
        """
        data = self._build_data(name=name, **kwargs)
        result = await self._make_request("POST", "/tag", data=data)
        return result

    async def update(self, old_name: str, new_name: str, **kwargs) -> Dict[str, Any]:
        """Update an existing tag by renaming it across all tasks.

        Note: This operation will find all tasks with the old tag name
        and update them to use the new tag name.

        Args:
            old_name: Current tag name
            new_name: New tag name
            **kwargs: Additional properties (currently not supported by API)

        Returns:
            Summary of updated tasks
        """
        from .tasks import TaskService

        task_service = TaskService(self.auth, self.base_url, self.timeout)

        try:
            tasks_to_update = await self._scan_tasks_with_tag(lambda tags: old_name in tags)

            for task in tasks_to_update:
                tags = task.get("tags") or []
                task["tags"] = [new_name if t == old_name else t for t in tags]

            if tasks_to_update:
                await task_service.batch_update_tasks(tasks_to_update)

            return {"updated_count": len(tasks_to_update), "old_name": old_name, "new_name": new_name}
        finally:
            await task_service.close()

    async def delete(self, tag_name: str) -> None:
        """Delete a tag by removing it from all tasks.

        This will find all tasks with the specified tag and remove it.

        Args:
            tag_name: The name of the tag to delete
        """
        from .tasks import TaskService

        task_service = TaskService(self.auth, self.base_url, self.timeout)

        try:
            tasks_to_update = await self._scan_tasks_with_tag(lambda tags: tag_name in tags)

            for task in tasks_to_update:
                tags = task.get("tags") or []
                task["tags"] = [t for t in tags if t != tag_name]

            if tasks_to_update:
                await task_service.batch_update_tasks(tasks_to_update)
        finally:
            await task_service.close()

    async def delete_from_api(self, tag_name: str) -> None:
        """Delete a tag using the DELETE /tag/{name} API endpoint.

        This directly deletes the tag from the account.

        Args:
            tag_name: The name of the tag to delete
        """
        await self._make_request("DELETE", f"/tag/{tag_name}")

    async def merge_tags(self, source_tag: str, target_tag: str) -> None:
        """Merge one tag into another.

        All tasks with the source tag will have the target tag added,
        and the source tag will be removed.

        Args:
            source_tag: The tag to be merged (will be deleted)
            target_tag: The tag to merge into
        """
        data = self._build_data(fromTag=source_tag, toTag=target_tag)
        await self._make_request("POST", "/tag/merge", data=data)
