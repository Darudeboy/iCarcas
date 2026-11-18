"""Domain error codes and exceptions."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_VERSION_UNSUPPORTED = "TOOL_VERSION_UNSUPPORTED"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_SELECTION_REQUIRED = "DEVICE_SELECTION_REQUIRED"
    DEVICE_TRUST_REQUIRED = "DEVICE_TRUST_REQUIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    TWO_FACTOR_REQUIRED = "TWO_FACTOR_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    APP_LICENSE_MISSING = "APP_LICENSE_MISSING"
    APP_UNAVAILABLE = "APP_UNAVAILABLE"
    PACKAGE_INVALID = "PACKAGE_INVALID"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    INSTALL_FAILED = "INSTALL_FAILED"
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    UNKNOWN_EXTERNAL_ERROR = "UNKNOWN_EXTERNAL_ERROR"
    INVALID_STATE = "INVALID_STATE"


class RestoreError(Exception):
    """Domain-level failure with a stable error code and safe user message."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        stage: str | None = None,
        details: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.stage = stage
        self.details = details
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"RestoreError(code={self.code!r}, stage={self.stage!r}, "
            f"message={self.message!r})"
        )
