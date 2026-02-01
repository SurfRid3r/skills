"""Base HTTP client for Dida365 API."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx

from .exceptions import DidaAPIError

logger = logging.getLogger(__name__)


class HTTPClient:
    """Base HTTP client with shared request handling."""

    DEFAULT_BASE_URL = "https://api.dida365.com"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _build_url(self, endpoint: str, base: Optional[str] = None) -> str:
        """Build full URL from endpoint."""
        if base:
            return f"{base}{endpoint}"
        if endpoint.startswith("/api/"):
            return f"{self.base_url}{endpoint}"
        return f"{self.base_url}/api/v2{endpoint}"

    def _build_cookie_string(self, cookies: Dict[str, str]) -> str:
        """Convert cookies dict to Cookie header string."""
        return '; '.join([f"{k}={v}" for k, v in cookies.items()])

    async def request(
        self,
        method: str,
        endpoint: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        base: Optional[str] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Any:
        """Make authenticated HTTP request."""
        url = self._build_url(endpoint, base)

        if cookies:
            headers['Cookie'] = self._build_cookie_string(cookies)

        try:
            client = await self._get_http_client()

            if method == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()

            if response.status_code == 204 or not response.text:
                return {}

            return response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"API request failed: {e}"
            logger.error(f"{error_msg} - {e.response.text}")
            raise DidaAPIError(error_msg, e.response.status_code) from e
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise DidaAPIError(str(e)) from e


class BaseService(HTTPClient):
    """Base service class for API resources."""

    def __init__(self, auth_provider, base_url: str = None, timeout: float = None):
        super().__init__(
            base_url=base_url or HTTPClient.DEFAULT_BASE_URL,
            timeout=timeout or HTTPClient.DEFAULT_TIMEOUT,
        )
        self.auth = auth_provider
        self._project_group_ids: Optional[Set[str]] = None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        base: Optional[str] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Any:
        """Make authenticated request using auth provider."""
        headers = await self.auth.get_headers()
        cookies = await self.auth.get_cookies()
        return await self.request(method, endpoint, headers, cookies, base, params, data)

    async def _get_project_group_ids(self) -> Set[str]:
        """Get cached project group IDs."""
        if self._project_group_ids is None:
            try:
                sync_data = await self._make_request("GET", "/v3/batch/check/0", base="https://api.dida365.com/api")
                project_groups = sync_data.get('projectGroups', [])
                self._project_group_ids = {
                    g['id'] for g in project_groups
                    if not g.get('deleted')
                }
            except Exception:
                self._project_group_ids = set()
        return self._project_group_ids

    async def _is_project_group(self, project_id: str) -> bool:
        """Check if a project ID is a project group (not a real project)."""
        group_ids = await self._get_project_group_ids()
        return project_id in group_ids

    @staticmethod
    def _build_data(**kwargs) -> Dict[str, Any]:
        """Build request data, filtering None values."""
        return {k: v for k, v in kwargs.items() if v is not None}

    @staticmethod
    def _build_batch_data(
        add: Optional[List] = None,
        update: Optional[List] = None,
        delete: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Build batch operation data payload."""
        return {
            "add": add or [],
            "update": update or [],
            "delete": delete or [],
        }

    @staticmethod
    def _get_iso_timestamp() -> str:
        """Get current time as ISO 8601 timestamp with milliseconds."""
        now = datetime.now(timezone.utc)
        return now.isoformat(timespec='milliseconds').replace('+00:00', '+0000')
