"""Typed domain models. Missing metadata is represented as None, never invented."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    device_id: str
    display_name: str
    os_version: str | None = None
    connection_type: str | None = None
    available_for_operations: bool = True


@dataclass(frozen=True, slots=True)
class AppReference:
    store_id: str | None = None
    bundle_id: str | None = None
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not self.store_id and not self.bundle_id:
            raise ValueError("AppReference requires store_id or bundle_id")


@dataclass(frozen=True, slots=True)
class PackageInfo:
    local_path: str
    size_bytes: int
    sha256: str
    bundle_id: str | None = None
    version: str | None = None
    minimum_os_version: str | None = None


@dataclass(slots=True)
class OperationResult:
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    status: OperationStatus = OperationStatus.PENDING
    stage: str = "idle"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    user_message: str = ""

    def mark_running(self, stage: str, message: str = "") -> None:
        self.status = OperationStatus.RUNNING
        self.stage = stage
        self.started_at = self.started_at or utc_now()
        self.user_message = message

    def mark_succeeded(self, stage: str, message: str) -> None:
        self.status = OperationStatus.SUCCEEDED
        self.stage = stage
        self.finished_at = utc_now()
        self.error_code = None
        self.user_message = message

    def mark_failed(self, stage: str, error_code: str, message: str) -> None:
        self.status = OperationStatus.FAILED
        self.stage = stage
        self.finished_at = utc_now()
        self.error_code = error_code
        self.user_message = message

    def mark_cancelled(self, stage: str, message: str) -> None:
        self.status = OperationStatus.CANCELLED
        self.stage = stage
        self.finished_at = utc_now()
        self.error_code = "OPERATION_CANCELLED"
        self.user_message = message

    def __repr__(self) -> str:
        return (
            f"OperationResult(operation_id={self.operation_id!r}, "
            f"status={self.status!r}, stage={self.stage!r}, "
            f"error_code={self.error_code!r})"
        )
