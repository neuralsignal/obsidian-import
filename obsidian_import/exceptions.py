"""Custom exceptions for obsidian-import."""


class ObsidianImportError(Exception):
    """Base exception for obsidian-import."""


class UnsupportedFormatError(ObsidianImportError):
    """File format has no registered backend."""


class ExtractionError(ObsidianImportError):
    """Extraction failed for a specific file."""


class ExtractionTimeoutError(ObsidianImportError):
    """Extraction exceeded the configured timeout."""


class BackendNotAvailableError(ObsidianImportError):
    """A backend's optional dependency is not installed."""


class ConfigError(ObsidianImportError):
    """Configuration is invalid or missing required fields."""


class OutputConflictError(ObsidianImportError):
    """Output file would overwrite an existing file."""
