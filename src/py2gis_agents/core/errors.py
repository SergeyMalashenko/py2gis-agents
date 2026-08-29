"""Stable conversion of internal and upstream exceptions to tool errors."""

from __future__ import annotations

import logging
import re

import httpx
from pydantic import ValidationError

from .schemas import ToolError

logger = logging.getLogger(__name__)


class DgisServiceError(RuntimeError):
    """A sanitized error returned by the 2GIS application API."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def sanitize_error_message(value: object) -> str:
    """Remove a 2GIS key from an exception that contains a request URL."""

    return re.sub(
        r"([?&]key=)[^&\s'\"]+",
        r"\1***",
        str(value),
        flags=re.IGNORECASE,
    )


def exception_to_tool_error(exc: Exception) -> ToolError:
    """Map implementation exceptions to a small public error vocabulary."""

    if isinstance(exc, ValidationError):
        return ToolError(code="invalid_arguments", message=str(exc), retryable=False)
    if isinstance(exc, DgisServiceError):
        return ToolError(code=exc.code, message=exc.message, retryable=exc.retryable)
    if isinstance(exc, httpx.TimeoutException):
        return ToolError(
            code="upstream_timeout",
            message="2GIS Search API did not respond before the timeout",
            retryable=True,
        )
    if isinstance(exc, httpx.NetworkError):
        return ToolError(
            code="upstream_unavailable",
            message="Could not connect to 2GIS Search API",
            retryable=True,
        )
    logger.exception("Unexpected 2GIS tool failure: %s", sanitize_error_message(exc))
    return ToolError(
        code="internal_error",
        message="Unexpected error while executing the 2GIS tool",
        retryable=False,
    )
