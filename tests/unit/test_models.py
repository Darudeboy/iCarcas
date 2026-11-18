from __future__ import annotations

import pytest

from ios_restore.domain.models import AppReference, OperationResult


def test_app_reference_requires_id() -> None:
    with pytest.raises(ValueError):
        AppReference(display_name="x")


def test_operation_result_repr_has_no_secrets() -> None:
    result = OperationResult()
    result.mark_failed("DOWNLOADING", "DOWNLOAD_FAILED", "password=should-not-matter")
    text = repr(result)
    assert "password" not in text
    assert result.operation_id in text
