"""Web Authentication Module for Dida365/TickTick

Implements password-based login with token persistence.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages authentication token persistence."""

    def __init__(self, token_path: Optional[Path] = None):
        """Initialize token manager.

        Args:
            token_path: Path to store token file. Defaults to .dida_token.json in project root
        """
        if token_path is None:
            # Default to .dida_token.json in project root (same directory as .env)
            token_path = Path(os.getenv(
                "DIDA_TOKEN_PATH",
                Path.cwd() / ".dida_token.json"
            ))
        self.token_path = Path(token_path).expanduser()
        self.tokens = self._load_tokens()

    def save_token(
        self,
        auth_token: str,
        csrf_token: str,
        expires_in: Optional[int] = None
    ) -> None:
        """Save authentication tokens.

        Args:
            auth_token: The authentication token
            csrf_token: The CSRF token
            expires_in: Optional expiration time in seconds (None = no expiration)
        """
        self.tokens['web'] = {
            'auth_token': auth_token,
            'csrf_token': csrf_token,
            'expires_at': time.time() + expires_in if expires_in else None
        }
        self._persist_tokens()
        logger.info("Token saved successfully")

    def get_token(self) -> Optional[dict]:
        """Get valid token.

        Returns:
            Token data dict or None if not found/expired
        """
        token_data = self.tokens.get('web')
        if not token_data:
            return None

        # Check expiration
        if token_data.get('expires_at') and time.time() > token_data['expires_at']:
            del self.tokens['web']
            self._persist_tokens()
            return None

        return token_data

    def clear_token(self) -> None:
        """Clear stored tokens."""
        if 'web' in self.tokens:
            del self.tokens['web']
            self._persist_tokens()

    def _load_tokens(self) -> dict:
        """Load tokens from file."""
        if self.token_path.exists():
            try:
                with open(self.token_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load token: {e}")
        return {}

    def _persist_tokens(self) -> None:
        """Persist tokens to file."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, 'w') as f:
            json.dump(self.tokens, f, indent=2)


class WebAuth:
    """Web API authentication using username and password."""

    BASE_URL = "https://api.dida365.com"
    LOGIN_URL = f"{BASE_URL}/api/v2/user/signon"

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token_manager: Optional[TokenManager] = None,
        token_path: Optional[str] = None,
    ):
        """Initialize web authentication.

        Args:
            username: Email or phone number (defaults to DIDA_USERNAME env var)
            password: Account password (defaults to DIDA_PASSWORD env var)
            token_manager: Optional custom token manager
            token_path: Optional path for token storage (defaults to ~/.dida/token.json)
        """
        self.username = username or os.getenv("DIDA_USERNAME")
        self.password = password or os.getenv("DIDA_PASSWORD")

        # Set token path before creating TokenManager
        if token_path:
            os.environ["DIDA_TOKEN_PATH"] = token_path

        self.token_manager = token_manager or TokenManager()

        self.auth_token: Optional[str] = None
        self.csrf_token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

        if not self.username or not self.password:
            raise ValueError(
                "DIDA_USERNAME and DIDA_PASSWORD must be set in environment or .env file"
            )

    async def ensure_authenticated(self) -> None:
        """Ensure authentication is valid.

        Loads from storage or performs password login if needed.
        """
        # Check if already valid
        if self.is_valid():
            logger.debug("Already authenticated")
            return

        # Try loading from storage
        token_data = self.token_manager.get_token()
        if token_data:
            self.auth_token = token_data['auth_token']
            self.csrf_token = token_data['csrf_token']
            logger.info("Loaded saved tokens")
            return

        # Perform password login
        await self._password_login()

    def is_valid(self) -> bool:
        """Check if current authentication is valid."""
        return bool(self.auth_token and self.csrf_token)

    async def get_headers(self) -> dict:
        """Get request headers with authentication.

        Returns:
            Dictionary of request headers
        """
        await self.ensure_authenticated()

        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/json',
            'Origin': 'https://dida365.com',
            'Referer': 'https://dida365.com/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
            'x-csrftoken': self.csrf_token or '',
            'X-Device': '{"platform":"web","os":"macOS 10.15.7","device":"Chrome 143.0.0.0","name":"","version":8005,"id":"695d80c0925f8726b939ab5a","channel":"website","campaign":"","websocket":""}',
            'Hl': 'zh_CN',
            'X-Tz': 'Asia/Shanghai',
            'Traceid': self._generate_traceid(),
        }

    async def get_cookies(self) -> dict:
        """Get cookies for authentication.

        Returns:
            Dictionary of cookies
        """
        await self.ensure_authenticated()

        return {
            't': self.auth_token or '',
            '_csrf_token': self.csrf_token or ''
        }

    def _generate_traceid(self) -> str:
        """Generate trace ID for requests."""
        return f'{int(time.time() * 1000):x}{uuid.uuid4().hex[:8]}'

    async def close(self) -> None:
        """Close the HTTP client if it exists."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _password_login(self) -> None:
        """Perform password login."""
        logger.info(f"Logging in with username: {self.username}")

        login_url = f"{self.LOGIN_URL}?wc=true&remember=true"

        # Build browser-like headers (must match working dida implementation)
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://dida365.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://dida365.com/',
            'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
            'x-csrftoken': '',
            'x-device': '{"platform":"web","os":"macOS 10.15.7","device":"Chrome 143.0.0.0","name":"","version":8005,"id":"695d80c0925f8726b939ab5a","channel":"website","campaign":"","websocket":""}',
            'x-requested-with': 'XMLHttpRequest',
        }

        login_data = {
            "username": self.username,
            "password": self.password
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(login_url, headers=headers, json=login_data)

            logger.info(f"Login response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()

                if 'token' in result:
                    self.auth_token = result['token']

                    # Get csrf_token from response cookies
                    self.csrf_token = response.cookies.get('_csrf_token', '')

                    # Prioritize x-csrftoken from response headers
                    if 'x-csrftoken' in response.headers:
                        self.csrf_token = response.headers['x-csrftoken']

                    # Save tokens (Dida tokens are typically long-lived)
                    self.token_manager.save_token(
                        self.auth_token,
                        self.csrf_token,
                        expires_in=None  # No expiration
                    )

                    logger.info("Password login successful")
                    return

            # Login failed
            logger.error(f"Password login failed: {response.status_code} - {response.text}")
            raise RuntimeError(
                f"Login failed: {response.status_code}. "
                f"Please check your username and password."
            )
