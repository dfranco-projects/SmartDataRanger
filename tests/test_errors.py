"""Exception hierarchy contract tests."""

from __future__ import annotations

import pytest

from smartdataranger.errors import (
    IngestionError,
    MetadataError,
    SmartDataRangerError,
    UnsupportedFormatError,
)


@pytest.mark.parametrize(
    "exc_type",
    [UnsupportedFormatError, IngestionError, MetadataError],
)
def test_subclasses_are_smartdataranger_errors(exc_type: type[Exception]) -> None:
    exc = exc_type("boom")
    assert isinstance(exc, SmartDataRangerError)
    assert isinstance(exc, Exception)


def test_base_error_is_exception() -> None:
    assert issubclass(SmartDataRangerError, Exception)


def test_subclasses_are_catchable_as_base() -> None:
    with pytest.raises(SmartDataRangerError):
        raise IngestionError("cannot read")
