"""Explicit operation state machine for the restore workflow."""

from __future__ import annotations

from enum import StrEnum

from ios_restore.domain.errors import ErrorCode, RestoreError


class OperationStage(StrEnum):
    IDLE = "IDLE"
    CHECKING_ENVIRONMENT = "CHECKING_ENVIRONMENT"
    WAITING_FOR_DEVICE = "WAITING_FOR_DEVICE"
    WAITING_FOR_USER_AUTH = "WAITING_FOR_USER_AUTH"
    AUTHENTICATING = "AUTHENTICATING"
    READY = "READY"
    DOWNLOADING = "DOWNLOADING"
    PACKAGE_READY = "PACKAGE_READY"
    WAITING_FOR_INSTALL_CONFIRMATION = "WAITING_FOR_INSTALL_CONFIRMATION"
    INSTALLING = "INSTALLING"
    INSTALLATION_REPORTED_SUCCESS = "INSTALLATION_REPORTED_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_ALLOWED_TRANSITIONS: dict[OperationStage, frozenset[OperationStage]] = {
    OperationStage.IDLE: frozenset(
        {
            OperationStage.CHECKING_ENVIRONMENT,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.CHECKING_ENVIRONMENT: frozenset(
        {
            OperationStage.WAITING_FOR_DEVICE,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.WAITING_FOR_DEVICE: frozenset(
        {
            OperationStage.WAITING_FOR_USER_AUTH,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.WAITING_FOR_USER_AUTH: frozenset(
        {
            OperationStage.AUTHENTICATING,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.AUTHENTICATING: frozenset(
        {
            OperationStage.READY,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.READY: frozenset(
        {
            OperationStage.DOWNLOADING,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.DOWNLOADING: frozenset(
        {
            OperationStage.PACKAGE_READY,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.PACKAGE_READY: frozenset(
        {
            OperationStage.WAITING_FOR_INSTALL_CONFIRMATION,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.WAITING_FOR_INSTALL_CONFIRMATION: frozenset(
        {
            OperationStage.INSTALLING,
            OperationStage.CANCELLED,
            OperationStage.FAILED,
        }
    ),
    OperationStage.INSTALLING: frozenset(
        {
            OperationStage.INSTALLATION_REPORTED_SUCCESS,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }
    ),
    OperationStage.INSTALLATION_REPORTED_SUCCESS: frozenset(
        {
            OperationStage.IDLE,
        }
    ),
    OperationStage.FAILED: frozenset(
        {
            OperationStage.IDLE,
        }
    ),
    OperationStage.CANCELLED: frozenset(
        {
            OperationStage.IDLE,
        }
    ),
}


class RestoreWorkflow:
    """Tracks a single-account / single-device restore operation."""

    def __init__(self) -> None:
        self._stage = OperationStage.IDLE
        self._busy = False

    @property
    def stage(self) -> OperationStage:
        return self._stage

    @property
    def is_busy(self) -> bool:
        return self._busy

    def transition_to(self, new_stage: OperationStage) -> None:
        allowed = _ALLOWED_TRANSITIONS[self._stage]
        if new_stage not in allowed:
            raise RestoreError(
                ErrorCode.INVALID_STATE,
                f"Переход {self._stage.value} → {new_stage.value} недопустим.",
                stage=self._stage.value,
            )
        self._stage = new_stage
        self._busy = new_stage not in {
            OperationStage.IDLE,
            OperationStage.READY,
            OperationStage.PACKAGE_READY,
            OperationStage.WAITING_FOR_INSTALL_CONFIRMATION,
            OperationStage.WAITING_FOR_DEVICE,
            OperationStage.WAITING_FOR_USER_AUTH,
            OperationStage.INSTALLATION_REPORTED_SUCCESS,
            OperationStage.FAILED,
            OperationStage.CANCELLED,
        }

    def reset(self) -> None:
        self._stage = OperationStage.IDLE
        self._busy = False

    def force_failed(self) -> None:
        """Enter FAILED without transition table (used when an unexpected mid-step error occurs)."""
        self._stage = OperationStage.FAILED
        self._busy = False

    def force_cancelled(self) -> None:
        self._stage = OperationStage.CANCELLED
        self._busy = False

    def ensure_can_start_parallel_guard(self) -> None:
        if self._busy:
            raise RestoreError(
                ErrorCode.INVALID_STATE,
                "Другая операция уже выполняется для этого аккаунта и устройства.",
                stage=self._stage.value,
            )
