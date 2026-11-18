from __future__ import annotations

import pytest

from ios_restore.domain.errors import ErrorCode, RestoreError
from ios_restore.domain.operations import OperationStage, RestoreWorkflow


def test_happy_path_transitions() -> None:
    wf = RestoreWorkflow()
    sequence = [
        OperationStage.CHECKING_ENVIRONMENT,
        OperationStage.WAITING_FOR_DEVICE,
        OperationStage.WAITING_FOR_USER_AUTH,
        OperationStage.AUTHENTICATING,
        OperationStage.READY,
        OperationStage.DOWNLOADING,
        OperationStage.PACKAGE_READY,
        OperationStage.WAITING_FOR_INSTALL_CONFIRMATION,
        OperationStage.INSTALLING,
        OperationStage.INSTALLATION_REPORTED_SUCCESS,
    ]
    for stage in sequence:
        wf.transition_to(stage)
    assert wf.stage == OperationStage.INSTALLATION_REPORTED_SUCCESS


def test_illegal_transition_raises() -> None:
    wf = RestoreWorkflow()
    with pytest.raises(RestoreError) as exc:
        wf.transition_to(OperationStage.DOWNLOADING)
    assert exc.value.code == ErrorCode.INVALID_STATE


def test_parallel_guard() -> None:
    wf = RestoreWorkflow()
    wf.transition_to(OperationStage.CHECKING_ENVIRONMENT)
    assert wf.is_busy
    with pytest.raises(RestoreError) as exc:
        wf.ensure_can_start_parallel_guard()
    assert exc.value.code == ErrorCode.INVALID_STATE


def test_cancel_from_ready() -> None:
    wf = RestoreWorkflow()
    wf.transition_to(OperationStage.CHECKING_ENVIRONMENT)
    wf.transition_to(OperationStage.WAITING_FOR_DEVICE)
    wf.transition_to(OperationStage.WAITING_FOR_USER_AUTH)
    wf.transition_to(OperationStage.AUTHENTICATING)
    wf.transition_to(OperationStage.READY)
    wf.transition_to(OperationStage.CANCELLED)
    assert wf.stage == OperationStage.CANCELLED
