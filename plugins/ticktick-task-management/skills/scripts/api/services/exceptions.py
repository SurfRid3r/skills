"""Custom exceptions for Dida365 API client."""


class DidaAPIError(Exception):
    """Base exception for Dida365 API errors."""

    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(DidaAPIError):
    """Raised when authentication fails."""

    pass


class ResourceNotFoundError(DidaAPIError):
    """Raised when a resource is not found."""

    pass


class ValidationError(DidaAPIError):
    """Raised when request validation fails."""

    pass


# Import TaskStatus from constants for backward compatibility
from ..constants import TaskStatus  # noqa: E402
