"""Comments service for Dida365 API.

API endpoints verified via browser testing at https://dida365.com/webapp/
"""

import logging
import uuid
from typing import Any, Dict, List

from .base import BaseService
from ..constants import CommentDefaults

logger = logging.getLogger(__name__)


class CommentService(BaseService):
    """Service for task comment-related operations."""

    @staticmethod
    def _generate_comment_id() -> str:
        """Generate a client-side comment ID (32 hex chars)."""
        return uuid.uuid4().hex

    async def get_by_task(
        self,
        project_id: str,
        task_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all comments for a task."""
        result = await self._make_request(
            "GET",
            f"/project/{project_id}/task/{task_id}/comments",
        )
        return result if isinstance(result, list) else []

    async def add(
        self,
        project_id: str,
        task_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """Add a comment to a task."""
        data = {
            "id": self._generate_comment_id(),
            "createdTime": self._get_iso_timestamp(),
            "taskId": task_id,
            "projectId": project_id,
            "title": content,
            "userProfile": {"isMyself": CommentDefaults.USER_PROFILE_IS_MYSELF},
            "isNew": CommentDefaults.IS_NEW,
        }
        return await self._make_request(
            "POST",
            f"/project/{project_id}/task/{task_id}/comment",
            data=data,
        )

    async def update(
        self,
        project_id: str,
        task_id: str,
        comment_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """Update a comment."""
        data = {
            "taskId": task_id,
            "projectId": project_id,
            "title": content,
            "id": comment_id,
        }
        return await self._make_request(
            "PUT",
            f"/project/{project_id}/task/{task_id}/comment/{comment_id}",
            data=data,
        )

    async def delete(
        self,
        project_id: str,
        task_id: str,
        comment_id: str,
    ) -> None:
        """Delete a comment."""
        await self._make_request(
            "DELETE",
            f"/project/{project_id}/task/{task_id}/comment/{comment_id}",
        )
