"""Custom exception types for the Eikon render engine."""

from __future__ import annotations


class EikonRenderError(Exception):
    """Base exception for render engine errors."""


class EikonScreenshotError(EikonRenderError):
    """Error during screenshot capture."""

    def __init__(self, message: str, recoverable: bool = False):
        """Initialize screenshot error.

        Args:
            message: Error description
            recoverable: Whether this error is worth retrying
        """
        super().__init__(message)
        self.recoverable = recoverable
