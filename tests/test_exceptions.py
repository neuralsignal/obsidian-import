"""Tests for exception hierarchy."""

from obsidian_import.exceptions import (
    BackendNotAvailableError,
    ConfigError,
    ExtractionError,
    ExtractionTimeoutError,
    ObsidianImportError,
    OutputConflictError,
    UnsupportedFormatError,
)


def test_base_exception_is_exception():
    assert issubclass(ObsidianImportError, Exception)


def test_all_exceptions_inherit_from_base():
    for exc_class in [
        UnsupportedFormatError,
        ExtractionError,
        ExtractionTimeoutError,
        BackendNotAvailableError,
        ConfigError,
        OutputConflictError,
    ]:
        assert issubclass(exc_class, ObsidianImportError)


def test_exception_message():
    exc = ExtractionError("test message")
    assert str(exc) == "test message"


def test_exception_can_be_caught_as_base():
    try:
        raise ExtractionTimeoutError("timed out")
    except ObsidianImportError as exc:
        assert "timed out" in str(exc)
