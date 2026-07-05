class SmartDataRangerError(Exception):
    """Base for all package errors."""


class UnsupportedFormatError(SmartDataRangerError):
    """File extension has no registered reader."""


class IngestionError(SmartDataRangerError):
    """A file could not be read or extracted."""


class MetadataError(SmartDataRangerError):
    """metadata.json is missing, malformed, or references unknown readers."""
